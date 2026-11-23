"""Retry Book transfer of already persisted signed intake forms.

Safe to rerun: Book uses public_id idempotency, and forms never return to the public user.
Usage: python manage.py sync_office_intake_forms --limit 100
"""
from django.core.management.base import BaseCommand
from platform_app.models import OfficeIntakeSubmission
from platform_app.public_intake import sync_submission


class Command(BaseCommand):
    help = 'Retry pending/error Aufnahmebogen transfers to the canonical Book patient file.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit=max(1,min(options['limit'],1000))
        rows=list(OfficeIntakeSubmission.objects.filter(sync_status__in=('pending','error'))
            .order_by('created_at')[:limit])
        success=0
        for row in rows:
            if sync_submission(row):success+=1
        self.stdout.write('Aufnahmebogen sync: checked=%d successful=%d pending=%d'%(
            len(rows),success,len(rows)-success))
