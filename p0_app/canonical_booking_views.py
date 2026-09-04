from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api


@csrf_exempt
@require_http_methods(["GET"])
def mobile_dashboard(request):
    """Return Customer Club dashboard data without ever reading legacy appointments.

    The web/native shell merges the canonical next appointment directly from
    book.a-esthetic.de. Keeping this endpoint appointment-free prevents stale
    platform_app.Appointment rows from leaking into Home if the direct book call
    is temporarily unavailable.
    """
    response = legacy_mobile_api.dashboard(request)
    if response.status_code != 200:
        return response

    import json
    try:
        payload = json.loads(response.content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return response
    payload["next_appointment"] = None
    payload["appointments_source"] = "book"
    return JsonResponse(payload)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def retired_mobile_booking(request):
    """Block the old Customer Club booking database from being used accidentally."""
    return JsonResponse({
        "ok": False,
        "error": "booking_moved_to_canonical_service",
        "canonical_api": "https://book.a-esthetic.de/api/mobile/booking/",
    }, status=410)
