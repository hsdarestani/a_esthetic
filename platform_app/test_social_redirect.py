from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

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
