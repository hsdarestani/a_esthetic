from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from platform_app.models import UserProfile


USERNAME = 'qamar'
OLD_USERNAME = 'doctor.qamar.hameed'
LOGIN_EMAIL = 'qamar@a-esthetic.de'
GROUP_NAME = 'aesthetic_qamar_doctor'


class Command(BaseCommand):
    help = 'Ensure Qamar Hameed has a doctor-only identity (never create a public password).'

    @transaction.atomic
    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name=GROUP_NAME)
        user = User.objects.filter(username=OLD_USERNAME).first()
        if not user:
            existing_short = User.objects.filter(username=USERNAME).first()
            if existing_short and not existing_short.groups.filter(name=GROUP_NAME).exists():
                raise ValueError('Username qamar belongs to an unrelated account')
            user = existing_short

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

        if User.objects.filter(username=USERNAME).exclude(pk=user.pk if user.pk else None).exists():
            raise ValueError('Username qamar is already in use')
        if User.objects.filter(email__iexact=LOGIN_EMAIL).exclude(pk=user.pk if user.pk else None).exists():
            raise ValueError('Login email is already in use')
        user.username = USERNAME
        user.email = LOGIN_EMAIL
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
