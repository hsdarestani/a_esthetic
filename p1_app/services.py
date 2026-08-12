import hashlib

from django.db import transaction

from platform_app.models import Appointment

from .models import AftercareTaskStatus, AftercareTemplate, AssignedAftercare


def sha256_upload(upload):
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def ensure_aftercare_assignments(user):
    """Attach approved active aftercare templates to the user's completed appointments.

    Nothing is generated medically: staff must create and approve the template first.
    """
    appointments = Appointment.objects.filter(user=user, status="completed").select_related("service")
    for appointment in appointments:
        templates = AftercareTemplate.objects.filter(service=appointment.service, active=True)
        for template in templates:
            with transaction.atomic():
                assigned, _ = AssignedAftercare.objects.get_or_create(
                    user=user,
                    appointment=appointment,
                    template=template,
                )
                existing = set(assigned.task_statuses.values_list("task_id", flat=True))
                AftercareTaskStatus.objects.bulk_create(
                    [AftercareTaskStatus(assigned=assigned, task=task) for task in template.tasks.all() if task.pk not in existing],
                    ignore_conflicts=True,
                )
