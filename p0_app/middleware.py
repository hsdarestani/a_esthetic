import hashlib

from django.http import JsonResponse
from django.utils import timezone

from platform_app import mobile_api as legacy_mobile_api

from .models import DeviceSession


class MobileDeviceSessionMiddleware:
    EXEMPT_PATHS = {
        "/api/mobile/status/",
        "/api/mobile/login/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/mobile/") or request.path in self.EXEMPT_PATHS:
            return self.get_response(request)

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return self.get_response(request)

        raw_token = header[7:].strip()
        user = legacy_mobile_api._user_from_request(request)
        if not user:
            return self.get_response(request)

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        defaults = {
            "user": user,
            "device_name": user_agent[:180] or "A+ Esthetic App",
            "user_agent": user_agent,
            "ip_address": ip_address,
            "last_seen_at": timezone.now(),
        }
        session, _ = DeviceSession.objects.get_or_create(token_hash=token_hash, defaults=defaults)
        if session.user_id != user.pk:
            return JsonResponse({"ok": False, "error": "authentication_required"}, status=401)
        if session.revoked_at:
            return JsonResponse({"ok": False, "error": "session_revoked"}, status=401)

        DeviceSession.objects.filter(pk=session.pk).update(
            device_name=defaults["device_name"],
            user_agent=defaults["user_agent"],
            ip_address=defaults["ip_address"],
            last_seen_at=defaults["last_seen_at"],
        )
        request.mobile_device_session = session
        return self.get_response(request)
