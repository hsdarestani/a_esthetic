from django.core.management.base import BaseCommand

from experience_app.integrations import check_provider


class Command(BaseCommand):
    help = "Prüft ausschließlich konfigurierte offizielle Integrationen."

    def add_arguments(self, parser):
        parser.add_argument("providers", nargs="*", default=["simplybook", "doctolib", "google", "apple"])

    def handle(self, *args, **options):
        for provider in options["providers"]:
            result = check_provider(provider)
            self.stdout.write(f"{provider}: {'OK' if result.ok else result.error}")
