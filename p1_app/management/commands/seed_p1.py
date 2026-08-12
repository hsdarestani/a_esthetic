from pathlib import Path
import re

from django.core.management.base import BaseCommand

from platform_app.models import FeatureModule, Service
from p1_app.models import AftercareTask, AftercareTemplate


class Command(BaseCommand):
    help = "Aktiviert die P1 Customer-Experience-Module und sichere Basisinhalte."

    def handle(self, *args, **options):
        modules = [
            ("before_after", "Privater Fortschritt", "Private Vorher-/Nachher- und Verlaufsfotos", 110),
            ("followup", "Nachsorge & Follow-up", "Freigegebene Nachsorgehinweise und Rückfragen", 120),
            ("beauty_plan", "Beauty Plan", "Persönliche Ziele, Budgets und organisatorische Schritte", 130),
        ]
        for key, name, description, order in modules:
            FeatureModule.objects.update_or_create(
                key=key,
                defaults={
                    "name_de": name,
                    "description_de": description,
                    "enabled": True,
                    "customer_visible": True,
                    "sort_order": order,
                },
            )

        service = Service.objects.filter(slug="beauty-termin", active=True).first()
        if service:
            template, _ = AftercareTemplate.objects.update_or_create(
                service=service,
                version="1.0",
                defaults={
                    "title": "A+ Nachsorge-Checkliste",
                    "introduction": "Von A+ Esthetic freigegebene organisatorische Hinweise nach Ihrem Termin. Bei Unsicherheit oder Beschwerden kontaktieren Sie bitte direkt das A+ Team.",
                    "approved_by": "A+ Esthetic Team",
                    "active": True,
                },
            )
            safe_tasks = [
                (10, "Hinweise prüfen", "Lesen Sie die Ihnen persönlich mitgegebenen A+ Hinweise und Unterlagen.", "do", False),
                (20, "Bei Fragen Kontakt aufnehmen", "Nutzen Sie den direkten A+ Kontakt, wenn etwas unklar ist.", "contact", False),
                (30, "Bei ungewöhnlichen Beschwerden A+ kontaktieren", "Die App stellt keine Diagnose. Kontaktieren Sie bei ungewöhnlichen Beschwerden das A+ Team bzw. im Notfall die zuständigen Notfalldienste.", "contact", True),
            ]
            for order, title, description, task_type, warning in safe_tasks:
                AftercareTask.objects.update_or_create(
                    template=template,
                    sort_order=order,
                    defaults={
                        "title": title,
                        "description": description,
                        "task_type": task_type,
                        "warning_sign": warning,
                    },
                )

        # The connected-app Nginx baseline historically capped requests at 1 MB.
        # P1 progress photos allow up to 8 MB; raise only this existing site-level
        # upload ceiling when the production Nginx file is present. The deployment
        # workflow validates and reloads Nginx after this command.
        nginx_conf = Path("/etc/nginx/sites-available/a-esthetic-connected.conf")
        if nginx_conf.exists():
            text = nginx_conf.read_text(encoding="utf-8")
            if "client_max_body_size" in text:
                updated = re.sub(r"client_max_body_size\s+\S+;", "client_max_body_size 10m;", text, count=1)
            else:
                brace = text.find("{")
                updated = text if brace < 0 else text[: brace + 1] + "\n  client_max_body_size 10m;" + text[brace + 1 :]
            if updated != text:
                nginx_conf.write_text(updated, encoding="utf-8")
                self.stdout.write("Nginx upload ceiling set to 10 MB for P1 protected photos.")

        self.stdout.write(self.style.SUCCESS("A+ Esthetic P1 Experience initialisiert."))
