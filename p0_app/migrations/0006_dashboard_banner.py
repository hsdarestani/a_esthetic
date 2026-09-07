from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("p0_app", "0005_google_review_activity")]

    operations = [
        migrations.CreateModel(
            name="DashboardBanner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("text", models.TextField(blank=True)),
                ("image_url", models.URLField(blank=True, max_length=500)),
                ("cta_label", models.CharField(blank=True, max_length=80)),
                ("cta_url", models.URLField(blank=True, max_length=500)),
                ("active", models.BooleanField(default=True)),
                ("starts_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Dashboard-Kampagne",
                "verbose_name_plural": "Dashboard-Kampagnen",
                "ordering": ["sort_order", "-created_at"],
            },
        )
    ]
