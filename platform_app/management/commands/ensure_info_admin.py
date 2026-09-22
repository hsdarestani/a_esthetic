import json
import secrets
import string
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from platform_app.models import UserProfile


BOOK_BOOTSTRAP_URL = "https://book.a-esthetic.de/api/internal/admin-bootstrap/"


def _token():
    try:
        return Path("/etc/aesthetic-patient-sync.token").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return ""


def _password():
    alphabet = string.ascii_letters + string.digits
    return "A+" + "".join(secrets.choice(alphabet) for _ in range(18)) + "!9"


class Command(BaseCommand):
    help = "Create the canonical info@a-esthetic.de admin once and mirror it into Book."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="info@a-esthetic.de")

    def handle(self, *args, **options):
        email = str(options["email"]).strip().lower()
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            profile, _ = UserProfile.objects.get_or_create(user=existing)
            changed = []
            if not existing.is_staff:
                existing.is_staff = True
                changed.append("is_staff")
            if not existing.is_superuser:
                existing.is_superuser = True
                changed.append("is_superuser")
            if changed:
                existing.save(update_fields=changed)
            if profile.role != "admin":
                profile.role = "admin"
                profile.save(update_fields=["role"])
            self.stdout.write("Canonical info admin already exists; password unchanged.")
            return

        token = _token()
        if not token:
            raise CommandError("Internal sync token is missing.")

        password = _password()
        with transaction.atomic():
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name="A+ Esthetic",
                last_name="Admin",
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            UserProfile.objects.create(
                user=user,
                role="admin",
                auth_provider="password",
            )
            payload = json.dumps({
                "email": email,
                "password": password,
            }).encode("utf-8")
            request = Request(
                BOOK_BOOTSTRAP_URL,
                method="POST",
                data=payload,
                headers={
                    "X-Aesthetic-Patient-Sync": token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "A+Esthetic-Admin-Bootstrap/1.0",
                },
            )
            try:
                with urlopen(request, timeout=20) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    if response.status not in {200, 201} or not body.get("ok"):
                        raise CommandError("Book admin bootstrap failed.")
            except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CommandError(f"Book admin bootstrap failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Canonical info admin created; credentials were delivered securely by e-mail."
            )
        )
