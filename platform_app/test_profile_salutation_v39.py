import json
from django.contrib.auth.models import User
from django.test import TestCase
from platform_app.mobile_api import _token_for
from platform_app.models import UserProfile


class SelfServiceSalutationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="legacy-customer@example.de", password="test123")
        self.profile = UserProfile.objects.create(
            user=self.user, salutation="", phone="+491701234567",
            marketing_consent=True, onboarding_required=False
        )
        self.headers = {"HTTP_AUTHORIZATION": "Bearer " + _token_for(self.user)}

    def test_setting_anrede_does_not_reset_phone_marketing_or_legacy_access(self):
        response = self.client.post("/api/mobile/profile/",
            data=json.dumps({"salutation": "herr"}),
            content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.salutation, "herr")
        self.assertEqual(self.profile.phone, "+491701234567")
        self.assertTrue(self.profile.marketing_consent)
        self.assertFalse(self.profile.onboarding_required)
        self.assertEqual(response.json()["profile"]["salutation"], "herr")

    def test_invalid_choice_cannot_change_profile(self):
        response = self.client.post("/api/mobile/profile/",
            data=json.dumps({"salutation": "invalid"}),
            content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.salutation, "")

    def test_profile_get_does_not_write_anrede(self):
        response = self.client.get("/api/mobile/profile/", **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profile"]["salutation"], "")
