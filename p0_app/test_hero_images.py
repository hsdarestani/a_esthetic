import base64
import io
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from platform_app.mobile_api import _token_for
from platform_app.models import UserProfile
from .ops_models import DashboardHeroImage


def test_photo_bytes():
    image = Image.new("RGB", (1200, 700), (206, 182, 141))
    stream = io.BytesIO()
    image.save(stream, format="JPEG")
    return stream.getvalue()


class DashboardHeroTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="aesthetic-hero-tests-")
        self.storage_override = override_settings(MEDIA_ROOT=self.temp_dir)
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

        self.admin = User.objects.create_superuser(
            username="hero-admin", email="hero-admin@example.de", password="test-password"
        )
        self.user = User.objects.create_user(
            username="hero-customer", email="customer@example.de", password="test-password"
        )
        self.profile = UserProfile.objects.create(user=self.user, salutation="frau")
        self.admin_auth = {"HTTP_AUTHORIZATION": "Bearer " + _token_for(self.admin)}

    def put_hero(self, slot, *, actor=True, image_data=None):
        return self.client.post(
            "/api/mobile/admin/dashboard-hero/",
            data={
                "variant": slot,
                "action": "save",
                "image_type": "image/jpeg",
                "image_data": image_data or base64.b64encode(test_photo_bytes()).decode("ascii"),
            },
            content_type="application/json",
            **(self.admin_auth if actor else {}),
        )

    def dashboard_for_customer(self):
        with patch("p0_app.canonical_booking_views.legacy_mobile_api._auth", return_value=(self.user, None)):
            return self.client.get("/api/mobile/dashboard/")

    def test_three_slots_admin_can_upload_and_replace(self):
        for variant in ("frau", "herr", "default"):
            response = self.put_hero(variant)
            self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(DashboardHeroImage.objects.count(), 3)
        item = DashboardHeroImage.objects.get(variant="frau")
        old_name = item.image.name
        self.put_hero("frau")
        item.refresh_from_db()
        self.assertNotEqual(item.image.name, old_name)
        self.assertFalse(item.image.storage.exists(old_name))

    def test_api_selects_frau_herr_or_default_from_explicit_salutation(self):
        self.put_hero("frau")
        self.put_hero("herr")
        self.put_hero("default")
        for salutation, expected in (("frau", "frau"), ("herr", "herr"), ("divers", "default"), ("", "default")):
            self.profile.salutation = salutation
            self.profile.save(update_fields=["salutation"])
            response = self.dashboard_for_customer()
            self.assertEqual(response.status_code, 200, response.content)
            self.assertIn("/dashboard-hero/" + expected + "/", response.json()["hero_image_url"])

    def test_default_photo_only_for_unspecified_salutation(self):
        self.put_hero("default")
        self.assertEqual(self.dashboard_for_customer().json()["hero_image_url"], "")
        self.profile.salutation = ""
        self.profile.save(update_fields=["salutation"])
        result = self.dashboard_for_customer().json()
        self.assertEqual(result["hero_variant"], "default")
        self.assertIn("/dashboard-hero/default/", result["hero_image_url"])

    def test_male_image_missing_does_not_show_female_default(self):
        self.put_hero("default")
        self.put_hero("frau")
        self.profile.salutation = "herr"
        self.profile.save(update_fields=["salutation"])
        result = self.dashboard_for_customer().json()
        self.assertEqual(result["hero_variant"], "herr")
        self.assertEqual(result["hero_image_url"], "")

    def test_fallback_to_bundled_image_when_none_uploaded(self):
        self.assertEqual(self.dashboard_for_customer().json()["hero_image_url"], "")

    def test_public_photo_url_and_cache_control(self):
        self.put_hero("frau")
        response = self.client.get("/api/mobile/dashboard-hero/frau/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("max-age", response["Cache-Control"])
        self.assertEqual(b"".join(response.streaming_content), test_photo_bytes())
        self.assertEqual(self.client.get("/api/mobile/dashboard-hero/invalid/").status_code, 404)

    def test_upload_requires_admin(self):
        response = self.put_hero("frau", actor=False)
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(DashboardHeroImage.objects.exists())

    def test_reject_invalid_content_and_variant(self):
        response = self.put_hero("frau", image_data=base64.b64encode(b"<svg>bad</svg>").decode("ascii"))
        self.assertEqual(response.status_code, 400)
        response = self.put_hero("unknown")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DashboardHeroImage.objects.exists())

    def test_can_clear_only_selected_slot(self):
        self.put_hero("frau")
        self.put_hero("herr")
        response = self.client.post(
            "/api/mobile/admin/dashboard-hero/",
            data={"action": "clear", "variant": "frau"},
            content_type="application/json",
            **self.admin_auth,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DashboardHeroImage.objects.filter(variant="frau").exists())
        self.assertTrue(DashboardHeroImage.objects.filter(variant="herr").exists())
