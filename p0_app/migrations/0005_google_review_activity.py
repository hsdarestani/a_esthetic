from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("p0_app", "0004_promote_app_admin"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleReviewActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("place_id", models.CharField(default="ChIJadEwN8QPvUcRyczqX4YoWxY", max_length=128)),
                ("status", models.CharField(choices=[("opened", "Google geöffnet"), ("submitted", "Als abgegeben markiert"), ("verified", "Verifiziert")], default="opened", max_length=16)),
                ("rating", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("review_text", models.TextField(blank=True)),
                ("google_review_url", models.URLField(blank=True)),
                ("opened_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="google_review_activities", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
