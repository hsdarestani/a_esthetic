from django.utils import timezone

from .models import DeviceSession


class DeviceSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated and request.session.session_key:
            user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip_address = (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None
            device_name = user_agent[:180] or "Browser"
            DeviceSession.objects.update_or_create(
                session_key=request.session.session_key,
                defaults={
                    "user": request.user,
                    "device_name": device_name,
                    "user_agent": user_agent,
                    "ip_address": ip_address,
                    "last_seen_at": timezone.now(),
                },
            )
        return response
