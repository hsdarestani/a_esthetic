from django.db import migrations


ADMIN_EMAIL = 'app@a-esthetic.de'
ADMIN_USERNAME = 'app_admin'
ADMIN_PASSWORD_HASH = 'pbkdf2_sha256$1200000$DNknBYzWkMDVRpuHB6UGKB$BlJkdZnBAtsHsJ5bDvCepXjDc35C8Z2BdqJkflyWZw8='


def provision_app_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('platform_app', 'UserProfile')
    MemberAccount = apps.get_model('platform_app', 'MemberAccount')
    WalletAccount = apps.get_model('platform_app', 'WalletAccount')

    user = User.objects.filter(email__iexact=ADMIN_EMAIL).first()
    if user is None:
        user = User.objects.filter(username=ADMIN_USERNAME).first()
    if user is None:
        user = User(username=ADMIN_USERNAME)

    user.username = ADMIN_USERNAME
    user.email = ADMIN_EMAIL
    user.first_name = 'A+ Esthetic'
    user.last_name = 'Admin'
    user.is_active = True
    user.is_staff = True
    user.is_superuser = False
    user.password = ADMIN_PASSWORD_HASH
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = 'admin'
    profile.save(update_fields=['role'])

    # Keep this identity administration-only; it must not become a Customer Club member.
    MemberAccount.objects.filter(user=user).delete()
    WalletAccount.objects.filter(user=user).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('platform_app', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(provision_app_admin, migrations.RunPython.noop),
    ]
