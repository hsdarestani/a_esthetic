import base64
import json
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from platform_app.mobile_api import _token_for
from platform_app.models import UserProfile
from p0_app.ops_models import DashboardBanner


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="aplus-banner-tests-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DashboardBannerUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user("banner-admin", password="secret", is_staff=True)
        profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        profile.role = "admin"
        profile.save(update_fields=["role"])
        self.auth = f"Bearer {_token_for(self.admin)}"

    def post(self, payload):
        return self.client.post(
            "/api/mobile/admin/dashboard-banners/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth,
        )

    def test_admin_can_upload_and_fetch_banner_cover(self):
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"test-cover").decode("ascii")
        response = self.post({
            "title": "Herbst Special",
            "cover_type": "image/png",
            "cover_name": "cover.png",
            "cover_data": png,
        })
        self.assertEqual(response.status_code, 200)
        payload = next(row for row in response.json()["banners"] if row["title"] == "Herbst Special")
        self.assertIn("/api/mobile/banner-cover/", payload["image_url"])
        banner = DashboardBanner.objects.get()
        self.assertTrue(banner.cover_image.name.endswith(".png"))
        cover = self.client.get(f"/api/mobile/banner-cover/{banner.pk}/")
        self.assertEqual(cover.status_code, 200)
        self.assertEqual(b"".join(cover.streaming_content), b"\x89PNG\r\n\x1a\n" + b"test-cover")

    def test_cover_rejects_unsupported_content_type(self):
        before = DashboardBanner.objects.count()
        response = self.post({
            "title": "Unsafe",
            "cover_type": "text/html",
            "cover_data": base64.b64encode(b"<script>alert(1)</script>").decode("ascii"),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_cover_type")
        self.assertEqual(DashboardBanner.objects.count(), before)
