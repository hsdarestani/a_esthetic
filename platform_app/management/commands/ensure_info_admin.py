import json
import os
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
MARKER = Path("/opt/a-esthetic-mobile/.info-admin-bootstrap-v1")


def _token():
    try:
        return Path("/etc/aesthetic-patient-sync.token").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return ""


def _password():
    configured = str(os.environ.get("ADMINPASS") or "").strip()
    if configured:
        if len(configured) < 12:
            raise CommandError("ADMINPASS must contain at least 12 characters.")
        return configured, True
    alphabet = string.ascii_letters + string.digits
    generated = "A+" + "".join(secrets.choice(alphabet) for _ in range(18)) + "!9"
    return generated, False


class Command(BaseCommand):
    help = "Create/mirror the canonical info@a-esthetic.de admin once."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="info@a-esthetic.de")

    def handle(self, *args, **options):
        email = str(options["email"]).strip().lower()
        if email != "info@a-esthetic.de":
            raise CommandError("This bootstrap is restricted to info@a-esthetic.de.")

        existing = User.objects.filter(email__iexact=email).first()
        configured_password = bool(str(os.environ.get("ADMINPASS") or "").strip())
        if MARKER.exists() and not configured_password:
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
            self.stdout.write("Canonical info admin bootstrap already completed.")
            return

        token = _token()
        if not token:
            raise CommandError("Internal sync token is missing.")

        password, from_adminpass = _password()
        with transaction.atomic():
            user = existing or User(username=email, email=email)
            user.username = email
            user.email = email
            user.first_name = user.first_name or "A+ Esthetic"
            user.last_name = user.last_name or "Admin"
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(password)
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = "admin"
            profile.auth_provider = "info_admin_v1"
            profile.onboarding_required = False
            profile.save(
                update_fields=["role", "auth_provider", "onboarding_required"]
            )

            payload = json.dumps({
                "email": email,
                "password": password,
                "send_credentials": not from_adminpass,
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
            except (
                HTTPError,
                URLError,
                TimeoutError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ) as exc:
                raise CommandError(f"Book admin bootstrap failed: {exc}") from exc

        MARKER.touch(mode=0o600, exist_ok=True)
        self.stdout.write(
            self.style.SUCCESS(
                "Canonical info admin password synchronized from ADMINPASS." if from_adminpass else "Canonical info admin created/mirrored; credentials were delivered securely by e-mail."
            )
        )
