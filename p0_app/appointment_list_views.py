from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import Appointment, StaffMember

from .appointment_views import CHANGE_DEADLINE_HOURS


@csrf_exempt
@require_http_methods(["GET"])
def mobile_manageable_appointments(request):
    user, error = legacy_mobile_api._auth(request)
    if error:
        return error

    appointments = (
        Appointment.objects.filter(
            user=user,
            status__in=["requested", "confirmed"],
            starts_at__gt=timezone.now(),
        )
        .select_related("service", "staff")
        .order_by("starts_at")[:20]
    )
    staff = StaffMember.objects.filter(active=True).prefetch_related("services").order_by("display_name")

    return JsonResponse({
        "ok": True,
        "change_deadline_hours": CHANGE_DEADLINE_HOURS,
        "appointments": [
            {
                "id": item.pk,
                "service_id": item.service_id,
                "service": item.service.name,
                "staff_id": item.staff_id,
                "staff": item.staff.display_name if item.staff else "",
                "starts_at": item.starts_at.isoformat(),
                "status": item.status,
                "change_allowed": timezone.now() <= item.starts_at - timedelta(hours=CHANGE_DEADLINE_HOURS),
            }
            for item in appointments
        ],
        "staff": [
            {
                "id": member.pk,
                "name": member.display_name,
                "service_ids": list(member.services.filter(active=True, bookable_in_app=True).values_list("id", flat=True)),
            }
            for member in staff
        ],
    })
