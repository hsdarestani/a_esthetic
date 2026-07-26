from django.conf import settings


def integration_ui(request):
    providers = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})
    return {
        "google_login_enabled": "google" in providers,
        "apple_login_enabled": "apple" in providers,
        "webpush_enabled": bool(getattr(settings, "WEBPUSH_VAPID_PUBLIC_KEY", "")),
    }
