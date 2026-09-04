from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("platform_app", "0001_initial"),
        ("p0_app", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PackageBookingService",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("service_slug", models.SlugField(max_length=160)),
                ("service_name", models.CharField(blank=True, max_length=180)),
                ("active", models.BooleanField(default=True)),
                ("auto_created", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("package_definition", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="booking_service_mappings", to="platform_app.packagedefinition")),
            ],
            options={"ordering": ["package_definition_id", "service_slug"]},
        ),
        migrations.CreateModel(
            name="PackageBookingRedemption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("booking_public_id", models.CharField(max_length=64, unique=True)),
                ("service_slug", models.SlugField(max_length=160)),
                ("status", models.CharField(choices=[("reserved", "Reserviert"), ("released", "Freigegeben")], default="reserved", max_length=16)),
                ("reserved_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("member_package", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="booking_redemptions", to="platform_app.memberpackage")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="package_booking_redemptions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-reserved_at"]},
        ),
        migrations.AlterUniqueTogether(
            name="packagebookingservice",
            unique_together={("package_definition", "service_slug")},
        ),
    ]
