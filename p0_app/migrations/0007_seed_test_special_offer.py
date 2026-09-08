from django.db import migrations
from django.utils import timezone


def seed_special_offer(apps, schema_editor):
    DashboardBanner = apps.get_model("p0_app", "DashboardBanner")
    DashboardBanner.objects.update_or_create(
        title="Autumn Glow Special",
        defaults={
            "text": "Ein eleganter Herbst-Preview im A+ Esthetic Patient Dashboard. Termin sichern und das aktuelle Special entdecken.",
            "image_url": "",
            "cta_label": "Termin sichern",
            "cta_url": "https://book.a-esthetic.de/",
            "active": True,
            "starts_at": timezone.now(),
            "ends_at": None,
            "sort_order": 10,
        },
    )


def remove_special_offer(apps, schema_editor):
    DashboardBanner = apps.get_model("p0_app", "DashboardBanner")
    DashboardBanner.objects.filter(title="Autumn Glow Special").delete()


class Migration(migrations.Migration):
    dependencies = [("p0_app", "0006_dashboard_banner")]

    operations = [migrations.RunPython(seed_special_offer, remove_special_offer)]
