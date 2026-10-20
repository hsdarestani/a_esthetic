from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from platform_app.models import UserProfile


USERNAME = 'doctor.qamar.hameed'
GROUP_NAME = 'aesthetic_qamar_doctor'


class Command(BaseCommand):
    help = 'Ensure Qamar Hameed has a doctor-only identity (never create a public password).'

    @transaction.atomic
    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=GROUP_NAME)
        user = User.objects.filter(username=USERNAME).first()

        if not user:
            candidates = User.objects.filter(
                first_name__iexact='Qamar', last_name__iexact='Hameed',
            ).select_related('profile').order_by('pk')
            for candidate in candidates:
                role = getattr(getattr(candidate, 'profile', None), 'role', 'customer')
                if candidate.is_staff or candidate.is_superuser or role in {'admin', 'manager', 'specialist'}:
                    user = candidate
                    break

        created = user is None
        if created:
            user = User(username=USERNAME)
            user.set_unusable_password()

        user.first_name = 'Qamar'
        user.last_name = 'Hameed'
        user.is_active = True
        # Do not grant Django management privileges to a doctor.
        user.is_staff = False
        user.is_superuser = False
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = 'specialist'
        profile.onboarding_required = False
        profile.save(update_fields=['role', 'onboarding_required'])

        # No inherited groups or per-user permissions from an earlier admin account.
        user.groups.clear()
        user.user_permissions.clear()
        user.groups.add(group)

        self.stdout.write(self.style.SUCCESS(
            f'Qamar doctor account: {"created" if created else "existing secured"}; '
            f'username={user.username}; usable_password={user.has_usable_password()}'
        ))
