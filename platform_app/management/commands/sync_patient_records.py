from django.core.management.base import BaseCommand

from platform_app.models import ConsentRecord
from platform_app.patient_sync import sync_consent_record


class Command(BaseCommand):
    help = 'Synchronisiert digitale Einwilligungen idempotent in die zentrale A+Esthetic Patientenakte.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        limit = max(1, min(int(options['limit'] or 500), 5000))
        records = (
            ConsentRecord.objects.select_related('user', 'template')
            .filter(accepted=True)
            .order_by('pk')[:limit]
        )
        ok = 0
        failed = 0
        for record in records:
            if sync_consent_record(record):
                ok += 1
            else:
                failed += 1
        self.stdout.write(f'Patientenakten-Sync: {ok} erfolgreich/idempotent, {failed} noch offen.')
