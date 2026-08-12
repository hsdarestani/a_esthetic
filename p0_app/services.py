from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from platform_app.models import Appointment, BlockedPeriod, Reminder, StaffMember, WorkingHour


def available_slots(service, staff, day, *, step_minutes=15):
    if not service.active or not service.bookable_in_app or not staff.active:
        return []
    if not staff.services.filter(pk=service.pk).exists():
        return []

    duration = timedelta(minutes=service.duration_minutes + service.buffer_minutes)
    tz = timezone.get_current_timezone()
    slots = []
    working_hours = WorkingHour.objects.filter(
        staff=staff,
        weekday=day.weekday(),
        active=True,
    ).order_by("start_time")

    for working in working_hours:
        cursor = timezone.make_aware(datetime.combine(day, working.start_time), tz)
        end_of_work = timezone.make_aware(datetime.combine(day, working.end_time), tz)
        while cursor + duration <= end_of_work:
            slot_end = cursor + duration
            if cursor >= timezone.now() + timedelta(hours=1):
                blocked = BlockedPeriod.objects.filter(
                    staff=staff,
                    starts_at__lt=slot_end,
                    ends_at__gt=cursor,
                ).exists()
                conflict = Appointment.objects.filter(
                    staff=staff,
                    status__in=["requested", "confirmed"],
                    starts_at__lt=slot_end,
                    ends_at__gt=cursor,
                ).exists()
                if not blocked and not conflict:
                    slots.append(cursor)
            cursor += timedelta(minutes=step_minutes)
    return slots


def create_slot_appointment(*, user, service, staff, starts_at, notes="", consent=False):
    duration = timedelta(minutes=service.duration_minutes + service.buffer_minutes)
    with transaction.atomic():
        locked_staff = StaffMember.objects.select_for_update().get(pk=staff.pk, active=True)
        local_day = starts_at.astimezone(timezone.get_current_timezone()).date()
        if starts_at not in available_slots(service, locked_staff, local_day):
            raise ValueError("time_not_available")
        appointment = Appointment(
            user=user,
            service=service,
            staff=locked_staff,
            starts_at=starts_at,
            ends_at=starts_at + duration,
            status="requested" if service.requires_medical_confirmation else "confirmed",
            source="app",
            notes_customer=notes[:3000],
            consent_acknowledged=bool(consent),
        )
        appointment.full_clean()
        appointment.save()

    Reminder.objects.create(
        user=user,
        title="Termin gespeichert",
        body=f"{service.name} am {timezone.localtime(starts_at):%d.%m.%Y um %H:%M}",
        scheduled_for=max(timezone.now(), starts_at - timedelta(days=1)),
        channel="inapp",
        status="scheduled",
        related_type="appointment",
        related_id=str(appointment.pk),
    )
    return appointment
