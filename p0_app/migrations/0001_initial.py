from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountDeletionRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requested_email", models.EmailField(blank=True, max_length=254)),
                ("source", models.CharField(choices=[("mobile_app", "Mobile App"), ("public_web", "Öffentliche Webseite"), ("authenticated_web", "Angemeldete Webseite"), ("support", "Support")], default="mobile_app", max_length=24)),
                ("status", models.CharField(choices=[("requested", "Angefordert"), ("identity_check", "Identitätsprüfung"), ("scheduled", "Vorgemerkt"), ("completed", "Abgeschlossen"), ("cancelled", "Storniert"), ("partially_retained", "Teilweise gesetzlich aufbewahrt")], default="requested", max_length=24)),
                ("reason", models.TextField(blank=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("scheduled_for", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("retention_note", models.TextField(blank=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="p0_deletion_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-requested_at"]},
        ),
        migrations.CreateModel(
            name="DataExportRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("requested", "Angefordert"), ("processing", "In Bearbeitung"), ("ready", "Bereit"), ("expired", "Abgelaufen"), ("failed", "Fehlgeschlagen")], default="requested", max_length=16)),
                ("requested_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p0_data_exports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-requested_at"]},
        ),
        migrations.CreateModel(
            name="DeviceSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("device_name", models.CharField(blank=True, max_length=180)),
                ("user_agent", models.CharField(blank=True, max_length=500)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p0_device_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-last_seen_at"]},
        ),
    ]
