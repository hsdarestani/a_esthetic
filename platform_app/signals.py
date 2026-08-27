import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ConsentRecord
from .patient_sync import sync_consent_record

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ConsentRecord, dispatch_uid='aesthetic_sync_consent_to_patient_file')
def sync_consent_to_patient_file(sender, instance, **kwargs):
    record_id = instance.pk

    def run():
        try:
            sync_consent_record(record_id)
        except Exception:
            # Consent capture must never fail because the secondary patient-file
            # synchronization is temporarily unavailable. The retry command/timer
            # will pick the record up again.
            logger.exception('Einwilligung konnte nicht in die Patientenakte synchronisiert werden')

    transaction.on_commit(run)
