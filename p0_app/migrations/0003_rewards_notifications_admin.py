from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def bootstrap_ops(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("platform_app", "UserProfile")
    FeatureModule = apps.get_model("platform_app", "FeatureModule")

    for user in User.objects.filter(is_superuser=True):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.role != "admin":
            profile.role = "admin"
            profile.save(update_fields=["role"])

    FeatureModule.objects.update_or_create(
        key="shop",
        defaults={
            "name_de": "Shop",
            "description_de": "Shop ist bis zur bewussten Freigabe deaktiviert.",
            "enabled": False,
            "customer_visible": False,
            "sort_order": 900,
        },
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("platform_app", "0001_initial"),
        ("p0_app", "0002_package_booking_bridge"),
    ]

    operations = [
        migrations.CreateModel(
            name="PushDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(max_length=512, unique=True)),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS")], max_length=12)),
                ("app_version", models.CharField(blank=True, max_length=40)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="push_devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-last_seen_at"]},
        ),
        migrations.CreateModel(
            name="AppNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("body", models.TextField(blank=True)),
                ("category", models.CharField(choices=[("general", "Allgemein"), ("reward", "Reward"), ("referral", "Empfehlung"), ("booking", "Termin"), ("campaign", "Kampagne"), ("system", "System")], default="general", max_length=20)),
                ("deeplink", models.CharField(blank=True, max_length=240)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("push_attempted_at", models.DateTimeField(blank=True, null=True)),
                ("push_result", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="app_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="RewardRedemption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fulfillment_code", models.CharField(max_length=32, unique=True)),
                ("coin_cost", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("pending", "Offen"), ("processing", "In Bearbeitung"), ("fulfilled", "Erfüllt"), ("cancelled", "Storniert")], default="pending", max_length=16)),
                ("customer_note", models.TextField(blank=True)),
                ("admin_note", models.TextField(blank=True)),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("fulfilled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="fulfilled_reward_redemptions", to=settings.AUTH_USER_MODEL)),
                ("reward", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="redemptions", to="platform_app.reward")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reward_redemptions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-requested_at"]},
        ),
        migrations.AddIndex(
            model_name="appnotification",
            index=models.Index(fields=["user", "read_at", "created_at"], name="p0_app_appn_user_id_8ce2ef_idx"),
        ),
        migrations.RunPython(bootstrap_ops, noop_reverse),
    ]
