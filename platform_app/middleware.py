from django.http import HttpResponse
from django.shortcuts import redirect

from .models import AuditLog


class MobileApiCorsMiddleware:
    ALLOWED_ORIGINS = {
        'capacitor://localhost',
        'https://localhost',
        'http://localhost',
        'https://app.a-esthetic.de',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_mobile_api = request.path.startswith('/api/mobile/')
        origin = request.headers.get('Origin', '')

        if is_mobile_api and request.method == 'OPTIONS':
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if is_mobile_api and origin in self.ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
            response['Access-Control-Max-Age'] = '86400'
            response['Vary'] = 'Origin'

        return response


class AuditRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and response.status_code < 400:
            try:
                AuditLog.objects.create(
                    actor=request.user,
                    action=f'{request.method} {request.path}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    metadata={'status': response.status_code},
                )
            except Exception:
                pass
        return response


class MobileSocialRedirectMiddleware:
    """Remember Android app social OAuth so allauth returns to the app bridge."""

    GOOGLE_LOGIN_PATH = "/accounts/google/login/"
    MOBILE_FINISH_PATH = "/mobile-social/finish/"
    SESSION_KEY = "aesthetic_mobile_social"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path == self.GOOGLE_LOGIN_PATH
            and request.GET.get("next") == self.MOBILE_FINISH_PATH
        ):
            request.session[self.SESSION_KEY] = True
            request.session.modified = True

        response = self.get_response(request)

        if response is None or not request.session.get(self.SESSION_KEY):
            return response

        # django-allauth can prefer its stored post-login redirect over our
        # adapter hook. If that happens, rewrite the redirect before Chrome
        # ever reaches the plain Django root page.
        location = str(response.get("Location") or "")
        if response.status_code in {301, 302, 303, 307, 308} and location in {
            "/",
            "/?social=1",
            "https://esthetic.smarbiz.sbs/",
            "https://esthetic.smarbiz.sbs/?social=1",
        }:
            return redirect(self.MOBILE_FINISH_PATH)

        # Recovery for the exact failure observed on Android: OAuth completed,
        # the browser is authenticated, but allauth already rendered the root.
        user = getattr(request, "user", None)
        if (
            request.path == "/"
            and user is not None
            and user.is_authenticated
        ):
            return redirect(self.MOBILE_FINISH_PATH)

        return response
