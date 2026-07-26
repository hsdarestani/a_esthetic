from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse


class Command(BaseCommand):
    help = "Render the important A+ Esthetic web-app routes with seeded users."

    public_routes = [
        ("account_login", "Anmeldung", ("Willkommen zurück", "auth-card")),
        ("account_signup", "Registrierung", ("Konto erstellen", "Sicher registrieren")),
        ("account_reset_password", "Passwort zurücksetzen", ("Passwort zurücksetzen", "Link zum Zurücksetzen")),
        ("account_email_verification_sent", "E-Mail-Verifizierung", ("E-Mail-Adresse", "auth-status-icon")),
    ]

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

    def _check_email_branding(self):
        site = Site.objects.get_current()
        if site.domain != "esthetic.smarbiz.sbs" or site.name != "A+ Esthetic":
            raise CommandError(
                f"Django Site identity is incorrect: {site.name!r} / {site.domain!r}."
            )
        context = {
            "activate_url": "https://esthetic.smarbiz.sbs/accounts/confirm-email/test-token/",
            "current_site": site,
        }
        subject = render_to_string(
            "account/email/email_confirmation_signup_subject.txt", context
        ).strip()
        text = render_to_string(
            "account/email/email_confirmation_signup_message.txt", context
        )
        html = render_to_string(
            "account/email/email_confirmation_signup_message.html", context
        )
        combined = "\n".join((subject, text, html))
        required = (
            "A+ Esthetic",
            "Bitte bestätigen Sie Ihre E-Mail-Adresse",
            context["activate_url"],
        )
        missing = [marker for marker in required if marker not in combined]
        if missing:
            raise CommandError(
                "Transactional email is missing branded markers: " + ", ".join(missing)
            )
        forbidden = ("example.com", "Hello from", "Thank you for using", "user hsdf7rb")
        found = [marker for marker in forbidden if marker in combined]
        if found:
            raise CommandError(
                "Transactional email still contains default allauth content: "
                + ", ".join(found)
            )
        self.stdout.write(self.style.SUCCESS("OK: branded German transactional email templates"))

    def handle(self, *args, **options):
        self._check_email_branding()

        public_client = Client()
        for route_name, label, markers in self.public_routes:
            response = self._check(public_client, route_name, label)
            html = response.content.decode("utf-8", errors="replace")
            missing = [marker for marker in markers if marker not in html]
            if missing:
                raise CommandError(
                    f"{label} is missing branded German markers: {', '.join(missing)}"
                )
            if "Menu:" in html or "Sign Up" in html or "Verify Your Email Address" in html:
                raise CommandError(f"{label} still contains raw allauth English markup.")

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

        total = len(self.public_routes) + len(self.customer_routes) + len(self.staff_routes) + 2
        self.stdout.write(
            self.style.SUCCESS(f"A+ web-app smoke test passed: {total} routes.")
        )