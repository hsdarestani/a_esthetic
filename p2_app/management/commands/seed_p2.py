from django.core.management.base import BaseCommand

from platform_app.models import FeatureModule


MODULES = [
    {
        "key": "wallet-pass",
        "name_de": "Mitgliedskarte & Wallet",
        "description_de": "Digitale A+ Mitgliedskarte mit QR sowie Apple-/Google-Wallet-Bereitschaft.",
        "sort_order": 60,
    },
    {
        "key": "beauty-cabinet",
        "name_de": "Beauty Cabinet",
        "description_de": "Eigene Produkte, Öffnungs-/Ablaufdaten und persönliche Routinen organisieren.",
        "sort_order": 70,
    },
    {
        "key": "shop-orders",
        "name_de": "A+ Shop & Bestellungen",
        "description_de": "Nicht verschreibungspflichtige Produkte bestellen und Status verfolgen.",
        "sort_order": 80,
    },
]


class Command(BaseCommand):
    help = "Initialisiert die produktionssicheren P2 Feature-Module."

    def handle(self, *args, **options):
        for module in MODULES:
            FeatureModule.objects.update_or_create(
                key=module["key"],
                defaults={
                    "name_de": module["name_de"],
                    "description_de": module["description_de"],
                    "enabled": True,
                    "customer_visible": True,
                    "sort_order": module["sort_order"],
                },
            )
        self.stdout.write(self.style.SUCCESS("A+ Esthetic P2 initialisiert."))
