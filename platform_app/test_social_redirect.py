from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .adapters import AestheticAccountAdapter
from .middleware import MobileSocialRedirectMiddleware


class MobileSocialRedirectTests(TestCase):
    def _request(self, path):
        request = RequestFactory().get(path)
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = AnonymousUser()
        return request

    def test_google_app_login_marks_session_and_adapter_returns_finish_bridge(self):
        request = self._request(
            "/accounts/google/login/?process=login&next=%2Fmobile-social%2Ffinish%2F"
        )
        MobileSocialRedirectMiddleware(lambda req: None)(request)

        self.assertTrue(request.session.get("aesthetic_mobile_social"))
        self.assertEqual(
            AestheticAccountAdapter().get_login_redirect_url(request),
            "/mobile-social/finish/",
        )

    def test_regular_login_keeps_normal_redirect(self):
        request = self._request("/accounts/google/login/?process=login")
        MobileSocialRedirectMiddleware(lambda req: None)(request)
        self.assertFalse(request.session.get("aesthetic_mobile_social", False))


    def test_mobile_dispatch_returns_app_deep_link(self):
        user = User.objects.create_user(
            "dispatch-google",
            "dispatch-google@example.com",
            "StrongPass-123!",
        )
        self.client.force_login(user)
        session = self.client.session
        session["aesthetic_mobile_social"] = True
        session.save()

        response = self.client.get("/mobile-social/dispatch/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("de.aplusesthetic.app://social-login?code=", response.content.decode())
        self.assertNotIn("aesthetic_mobile_social", self.client.session)

    def test_regular_dispatch_preserves_web_social_flow(self):
        user = User.objects.create_user(
            "dispatch-web",
            "dispatch-web@example.com",
            "StrongPass-123!",
        )
        self.client.force_login(user)

        response = self.client.get("/mobile-social/dispatch/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/?social=1")


    def test_mobile_oauth_root_redirect_is_rewritten_to_finish(self):
        request = self._request(
            "/accounts/google/login/?process=login&next=%2Fmobile-social%2Ffinish%2F"
        )
        middleware = MobileSocialRedirectMiddleware(
            lambda req: HttpResponseRedirect("/?social=1")
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/mobile-social/finish/")
        self.assertTrue(request.session.get("aesthetic_mobile_social"))

    def test_authenticated_mobile_oauth_root_page_is_recovered(self):
        user = User.objects.create_user(
            "root-recovery",
            "root-recovery@example.com",
            "StrongPass-123!",
        )
        request = self._request("/")
        request.user = user
        request.session["aesthetic_mobile_social"] = True
        request.session.save()

        response = MobileSocialRedirectMiddleware(
            lambda req: HttpResponse("plain root")
        )(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/mobile-social/finish/")


    def test_finish_page_has_explicit_app_button(self):
        user = User.objects.create_user(
            "handoff-button",
            "handoff-button@example.com",
            "StrongPass-123!",
        )
        self.client.force_login(user)

        response = self.client.get("/mobile-social/finish/")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("A+ Esthetic App öffnen", body)
        self.assertIn("de.aplusesthetic.app://social-login?code=", body)
        # iOS blocks unsupported schemes in Safari; never trigger an invalid
        # navigation automatically before the user can tap the app link.
        self.assertNotIn("window.location.href", body)
        self.assertIn("Tippen Sie auf die Schaltfläche", body)

    @override_settings(GOOGLE_IOS_CLIENT_ID="")
    def test_ios_google_user_can_set_app_password_without_rebuild(self):
        user = User.objects.create_user(
            "google-ios-fallback", "google-fallback@example.com"
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        self.client.force_login(user)
        response = self.client.get(
            "/mobile-social/finish/", HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit"
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Jetzt ohne Update anmelden", body)
        self.assertIn(reverse("account_set_password"), body)
        self.assertIn("App Passwort festlegen", body)
        self.assertIn("dieselbe Google E Mail", body)
        # Showing the recovery instructions must not silently change credentials.
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

    @override_settings(GOOGLE_IOS_CLIENT_ID="")
    def test_ios_existing_password_shows_manual_login_instructions(self):
        user = User.objects.create_user(
            "google-existing", "google-existing@example.com", "ExistingStrong-123!"
        )
        self.client.force_login(user)
        response = self.client.get(
            "/mobile-social/finish/", HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)"
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Ohne Update anmelden", body)
        self.assertIn("bereits eingerichtete Passwort", body)
        self.assertNotIn("App Passwort festlegen", body)

    @override_settings(GOOGLE_IOS_CLIENT_ID="")
    def test_android_browser_flow_still_uses_app_return_link(self):
        user = User.objects.create_user(
            "google-android", "google-android@example.com"
        )
        self.client.force_login(user)
        response = self.client.get(
            "/mobile-social/finish/", HTTP_USER_AGENT="Mozilla/5.0 (Linux; Android 16)"
        )
        body = response.content.decode()
        self.assertIn("de.aplusesthetic.app://social-login?code=", body)
        self.assertNotIn("Ohne Update anmelden", body)
        self.assertNotIn("Jetzt ohne Update anmelden", body)
