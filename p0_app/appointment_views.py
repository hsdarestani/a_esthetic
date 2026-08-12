import json
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import Appointment, AuditLog, Reminder, StaffMember

from .services import available_slots


CHANGE_DEADLINE_HOURS = 24


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _auth(request):
    return legacy_mobile_api._auth(request)


def _deadline_passed(appointment):
    return timezone.now() > appointment.starts_at - timedelta(hours=CHANGE_DEADLINE_HOURS)


@csrf_exempt
@require_http_methods(["POST"])
def mobile_appointment_change(request, appointment_id):
    user, error = _auth(request)
    if error:
        return error

    data = _json(request)
    action = str(data.get("action") or "").strip().lower()
    if action not in {"cancel", "reschedule"}:
        return JsonResponse({"ok": False, "error": "invalid_change_action"}, status=400)

    with transaction.atomic():
        appointment = (
            Appointment.objects.select_for_update()
            .select_related("service", "staff")
            .filter(pk=appointment_id, user=user)
            .first()
        )
        if not appointment:
            return JsonResponse({"ok": False, "error": "appointment_not_found"}, status=404)
        if appointment.status not in {"requested", "confirmed"}:
            return JsonResponse({"ok": False, "error": "appointment_not_changeable"}, status=409)
        if _deadline_passed(appointment):
            return JsonResponse({
                "ok": False,
                "error": "change_deadline_passed",
                "deadline_hours": CHANGE_DEADLINE_HOURS,
            }, status=409)

        if action == "cancel":
            appointment.status = "cancelled"
            appointment.save(update_fields=["status", "updated_at"])
            Reminder.objects.filter(
                user=user,
                related_type="appointment",
                related_id=str(appointment.pk),
                status="scheduled",
            ).update(status="cancelled")
            AuditLog.objects.create(
                actor=user,
                action="Termin über Mobile App storniert",
                entity_type="Appointment",
                entity_id=str(appointment.pk),
                metadata={"previous_start": appointment.starts_at.isoformat()},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            return JsonResponse({"ok": True, "action": "cancel", "status": appointment.status})

        starts_at = parse_datetime(str(data.get("starts_at") or ""))
        if not starts_at:
            return JsonResponse({"ok": False, "error": "invalid_start_time"}, status=400)
        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
        if starts_at < timezone.now() + timedelta(hours=1):
            return JsonResponse({"ok": False, "error": "start_time_too_soon"}, status=400)

        service = appointment.service
        eligible = StaffMember.objects.filter(active=True, services=service).distinct().order_by("display_name")
        staff_id = data.get("staff_id") or appointment.staff_id
        staff = eligible.filter(pk=staff_id).first() if staff_id else None
        if not staff:
            return JsonResponse({"ok": False, "error": "staff_not_found"}, status=400)

        locked_staff = StaffMember.objects.select_for_update().get(pk=staff.pk)
        local_day = starts_at.astimezone(timezone.get_current_timezone()).date()
        if starts_at not in available_slots(
            service,
            locked_staff,
            local_day,
            exclude_appointment_id=appointment.pk,
        ):
            return JsonResponse({"ok": False, "error": "time_not_available"}, status=409)

        previous_start = appointment.starts_at
        previous_staff = appointment.staff_id
        duration = timedelta(minutes=service.duration_minutes + service.buffer_minutes)
        appointment.staff = locked_staff
        appointment.starts_at = starts_at
        appointment.ends_at = starts_at + duration
        appointment.status = "requested" if service.requires_medical_confirmation else "confirmed"
        appointment.full_clean()
        appointment.save(update_fields=["staff", "starts_at", "ends_at", "status", "updated_at"])

        Reminder.objects.filter(
            user=user,
            related_type="appointment",
            related_id=str(appointment.pk),
            status="scheduled",
        ).update(status="cancelled")
        Reminder.objects.create(
            user=user,
            title="Termin aktualisiert",
            body=f"{service.name} am {timezone.localtime(starts_at):%d.%m.%Y um %H:%M}",
            scheduled_for=max(timezone.now(), starts_at - timedelta(days=1)),
            channel="inapp",
            status="scheduled",
            related_type="appointment",
            related_id=str(appointment.pk),
        )
        AuditLog.objects.create(
            actor=user,
            action="Termin über Mobile App verschoben",
            entity_type="Appointment",
            entity_id=str(appointment.pk),
            metadata={
                "previous_start": previous_start.isoformat(),
                "new_start": starts_at.isoformat(),
                "previous_staff_id": previous_staff,
                "new_staff_id": locked_staff.pk,
            },
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    return JsonResponse({
        "ok": True,
        "action": "reschedule",
        "appointment": {
            "id": appointment.pk,
            "status": appointment.status,
            "starts_at": appointment.starts_at.isoformat(),
            "staff": appointment.staff.display_name,
        },
    })
