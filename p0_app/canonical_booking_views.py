from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import MemberPackage, Reminder


def _iso(value):
    return value.isoformat() if value else None


@csrf_exempt
@require_http_methods(["GET"])
def mobile_dashboard(request):
    """Customer Club Home data; appointments are supplied directly by book."""
    user, error = legacy_mobile_api._auth(request)
    if error:
        return error

    reminders = Reminder.objects.filter(user=user, status="scheduled").order_by("scheduled_for")[:4]
    packages = MemberPackage.objects.filter(user=user, status="active").select_related("definition")[:4]
    return JsonResponse({
        "ok": True,
        "member": legacy_mobile_api._member_payload(user),
        "next_appointment": None,
        "appointments_source": "book",
        "reminders": [
            {
                "id": item.pk,
                "title": item.title,
                "body": item.body,
                "scheduled_for": _iso(item.scheduled_for),
            }
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
    """Block the old Customer Club booking database from being used accidentally."""
    return JsonResponse({
        "ok": False,
        "error": "booking_moved_to_canonical_service",
        "canonical_api": "https://book.a-esthetic.de/api/mobile/booking/",
    }, status=410)
