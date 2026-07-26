from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse


class Command(BaseCommand):
    help = "Render the important A+ Esthetic web-app routes with seeded users."

    customer_routes = [
        ("dashboard", "Dashboard"),
        ("experience:member_center", "Mitgliedskarte"),
        ("experience:wallet_center", "Wallet & Rewards"),
        ("experience:booking_calendar", "Terminbuchung"),
        ("passport", "Beauty Passport"),
        ("experience:photo_center", "Vorher/Nachher"),
        ("experience:aftercare_center", "Nachsorge"),
        ("experience:beauty_plans", "Beauty Plan"),
        ("experience:assistant", "Wissensassistent"),
        ("experience:cabinet", "Beauty Cabinet"),
        ("reminders", "Erinnerungen"),
        ("experience:shop", "Shop"),
        ("experience:gamification", "Challenges"),
        ("experience:offers_events", "Angebote & Events"),
        ("experience:content_library", "Content"),
        ("experience:communication_center", "Kontakt"),
        ("experience:feedback_center", "Feedback"),
        ("experience:concierge", "Concierge"),
        ("profile", "Profil"),
        ("experience:privacy_center", "Datenschutz"),
        ("experience:api_modules", "Module API"),
        ("experience:api_dashboard", "Dashboard API"),
        ("experience:api_wallet", "Wallet API"),
        ("experience:api_passport", "Passport API"),
        ("experience:member_qr", "Member QR"),
    ]

    staff_routes = [
        ("management", "Management"),
        ("experience:management_catalog", "Modulkatalog"),
    ]

    def _check(self, client, route_name, label, accepted=(200,)):
        url = reverse(route_name)
        response = client.get(url, secure=True, HTTP_HOST="esthetic.smarbiz.sbs")
        if response.status_code not in accepted:
            raise CommandError(
                f"{label} ({url}) returned {response.status_code}; expected {accepted}."
            )
        self.stdout.write(self.style.SUCCESS(f"OK {response.status_code}: {label} {url}"))
        return response

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            customer = User.objects.get(username="demo@a-esthetic.de")
            staff = User.objects.filter(is_staff=True, is_active=True).order_by("id").first()
        except User.DoesNotExist as exc:
            raise CommandError("Seeded demo user is missing.") from exc
        if not staff:
            raise CommandError("No active staff user exists.")

        customer_client = Client()
        customer_client.force_login(customer)
        for route_name, label in self.customer_routes:
            response = self._check(customer_client, route_name, label)
            if route_name == "experience:member_center":
                html = response.content.decode("utf-8", errors="replace")
                required_markers = (
                    "premium-member-card",
                    "apple-wallet-pass-preview",
                    "Add to",
                    "Apple Wallet",
                )
                missing = [marker for marker in required_markers if marker not in html]
                if missing:
                    raise CommandError(
                        "Member-card visual markers are missing: " + ", ".join(missing)
                    )

        apple_response = self._check(
            customer_client,
            "experience:apple_wallet_pass",
            "Apple Wallet pass endpoint",
            accepted=(200, 302),
        )
        if apple_response.status_code == 200:
            content_type = apple_response.get("Content-Type", "")
            if "application/vnd.apple.pkpass" not in content_type:
                raise CommandError(
                    f"Apple Wallet returned unexpected content type: {content_type}"
                )

        self._check(
            customer_client,
            "experience:google_wallet_pass",
            "Google Wallet endpoint",
            accepted=(200, 302),
        )

        staff_client = Client()
        staff_client.force_login(staff)
        for route_name, label in self.staff_routes:
            self._check(staff_client, route_name, label)

        self.stdout.write(
            self.style.SUCCESS(
                f"A+ web-app smoke test passed: "
                f"{len(self.customer_routes) + len(self.staff_routes) + 2} routes."
            )
        )
