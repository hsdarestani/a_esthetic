from django.core.management.base import BaseCommand

from platform_app.models import FeatureModule


MODULES = [
    {
        "key": "gamification",
        "name_de": "Challenges & Achievements",
        "description_de": "Pflege-, Lern- und Community-Challenges, Achievements und freigegebene Quiz-Inhalte ohne Behandlungsanreize.",
        "sort_order": 90,
    },
    {
        "key": "events",
        "name_de": "A+ Events",
        "description_de": "Events entdecken, Plätze reservieren, Warteliste nutzen und bestätigte Termine in den Kalender übernehmen.",
        "sort_order": 100,
    },
    {
        "key": "concierge",
        "name_de": "Concierge & Kommunikation",
        "description_de": "Organisatorische Concierge-Anfragen und sichere Unterhaltungen mit dem A+ Team.",
        "sort_order": 110,
    },
]


class Command(BaseCommand):
    help = "Initialisiert die produktionssicheren P3 Feature-Module."

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
        self.stdout.write(self.style.SUCCESS("A+ Esthetic P3 initialisiert."))
