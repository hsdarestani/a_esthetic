from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import MemberPackage, Reminder

from .ops_models import DashboardBanner


def _iso(value):
    return value.isoformat() if value else None


def _banner_payload(item):
    return {
        "id": item.pk,
        "title": item.title,
        "text": item.text,
        "image_url": item.image_url,
        "cta_label": item.cta_label,
        "cta_url": item.cta_url,
        "starts_at": _iso(item.starts_at),
        "ends_at": _iso(item.ends_at),
    }


@csrf_exempt
@require_http_methods(["GET"])
def mobile_dashboard(request):
    """Premium patient home data; canonical appointments still come from book."""
    user, error = legacy_mobile_api._auth(request)
    if error:
        return error

    now = timezone.now()
    reminders = Reminder.objects.filter(user=user, status="scheduled").order_by("scheduled_for")[:4]
    packages = MemberPackage.objects.filter(user=user, status="active").select_related("definition")[:4]
    banners = DashboardBanner.objects.filter(active=True, starts_at__lte=now).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=now)
    )[:8]
    member = legacy_mobile_api._member_payload(user)
    return JsonResponse({
        "ok": True,
        "member": member,
        "points": int(member.get("coins") or 0),
        "next_appointment": None,
        "last_appointment": None,
        "appointments_source": "book",
        "contact": {
            "phone": "+496971417012",
            "phone_label": "069 71417012",
            "whatsapp": "+491729907936",
            "instagram_url": "https://www.instagram.com/aplus.esthetic/",
            "instagram_label": "@aplus.esthetic",
        },
        "campaigns": [_banner_payload(item) for item in banners],
        "reminders": [
            {"id": item.pk, "title": item.title, "body": item.body, "scheduled_for": _iso(item.scheduled_for)}
            for item in reminders
        ],
        "packages": [
            {
                "id": item.pk,
                "name": item.definition.name,
                "remaining_sessions": item.remaining_sessions,
                "expires_at": item.expires_at.isoformat(),
            }
            for item in packages
        ],
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def retired_mobile_booking(request):
    return JsonResponse({
        "ok": False,
        "error": "booking_moved_to_canonical_service",
        "canonical_api": "https://book.a-esthetic.de/api/mobile/booking/",
    }, status=410)
