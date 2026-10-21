"""Report new real A+ Esthetic app signups to authorized app administrators.

Called by the server's half-hourly systemd timer. No customer data is written
to public CI logs and test accounts never enter the notification report.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from platform_app.models import UserProfile
from p0_app.push import create_notification

STATE = ROOT / "ops" / ".new-signup-monitor-state.json"
INITIAL_LOOKBACK_MINUTES = 30
OVERLAP_MINUTES = 3


def _read_state():
    if not STATE.exists():
        return {}
    value = json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Invalid registration monitor state")
    return value


def _save_state(value):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
    os.replace(temp, STATE)


def _is_real_signup(profile):
    u = profile.user
    email = (u.email or "").strip().lower()
    username = (u.username or "").strip().lower()
    if not email or "@" not in email:
        return False
    if email.endswith(("@example.invalid", "@test.invalid", "@example.com", "@localhost")):
        return False
    if username.startswith(("production-smoke-", "qa-", "test-", "demo-")):
        return False
    return bool(profile.role == "customer" and u.is_active and not u.is_staff and not u.is_superuser)


def _line(profile):
    user = profile.user
    name = user.get_full_name().strip() or "Ohne Namen"
    stage = "Profil vollständig" if profile.profile_completed_at else "Profil noch unvollständig"
    email_stage = "E-Mail bestätigt" if profile.email_verified_at else "E-Mail noch nicht bestätigt"
    return f"{name} | {user.email} | {stage} | {email_stage}"


def main():
    now = timezone.now()
    state = _read_state()
    prior = parse_datetime(str(state.get("last_checked_at") or ""))
    if prior is None:
        prior = now - timedelta(minutes=INITIAL_LOOKBACK_MINUTES)
    if timezone.is_naive(prior):
        prior = timezone.make_aware(prior, timezone.get_current_timezone())

    # Small overlap prevents a signup being lost during an in-flight transaction.
    # IDs in the saved state suppress duplicate notices across overlapping runs.
    begin = prior - timedelta(minutes=OVERLAP_MINUTES)
    recent = list(
        UserProfile.objects.select_related("user")
        .filter(user__date_joined__gte=begin, user__date_joined__lte=now, role="customer")
        .order_by("user__date_joined", "user_id")
    )
    remembered = {str(pk) for pk in state.get("notified_ids", [])}
    real = [p for p in recent if _is_real_signup(p) and str(p.user_id) not in remembered]
    admins = list(
        User.objects.filter(is_active=True)
        .filter(
            Q(is_superuser=True)
            | Q(profile__role="admin")
            | Q(is_staff=True, profile__role="manager")
        ).distinct().order_by("id")
    )
    if not admins:
        raise RuntimeError("No active administrator to receive new-signup notifications")

    push_success = 0
    if real:
        for index in range(0, len(real), 15):
            batch = real[index:index + 15]
            body = "\n".join(_line(profile) for profile in batch)
            title = f"A+ Esthetic: {len(real)} neue Registrierungen"
            for admin in admins:
                notification = create_notification(
                    admin,
                    title,
                    body,
                    category="general",
                    deeplink="admin",
                    data={"event": "new_app_registrations", "count": len(real)},
                    send_push=True,
                )
                push_success += sum(
                    1 for device in (notification.push_result or {}).get("devices", [])
                    if device.get("ok")
                )

        # Optional email delivery, when SMTP is configured on the app server.
        # Always restrict the recipient to the organization's admin mailbox.
        mail_backend = str(getattr(settings, "EMAIL_BACKEND", ""))
        if "smtp.EmailBackend" in mail_backend and getattr(settings, "EMAIL_HOST_PASSWORD", ""):
            recipient = os.environ.get("AESTHETIC_SIGNUP_ALERT_EMAIL", "info@a-esthetic.de").strip()
            if recipient.lower().endswith("@a-esthetic.de"):
                try:
                    send_mail(
                        f"A+ Esthetic · {len(real)} neue App-Registrierungen",
                        "\n".join(_line(profile) for profile in real),
                        settings.DEFAULT_FROM_EMAIL,
                        [recipient],
                        fail_silently=False,
                    )
                    print("SIGNUP_MONITOR_EMAIL_SENT=true")
                except Exception as exc:
                    print(f"SIGNUP_MONITOR_EMAIL_FAILED={type(exc).__name__}")

    remembered.update(str(profile.user_id) for profile in real)
    # IDs can be kept for 30 days; a fixed window avoids state growth forever.
    cutoff = now - timedelta(days=30)
    remembered = {
        pk for pk in remembered
        if User.objects.filter(pk=int(pk), date_joined__gte=cutoff).exists()
    }
    _save_state({
        "last_checked_at": now.isoformat(),
        "notified_ids": sorted(remembered, key=int),
    })
    print(
        f"SIGNUP_MONITOR_OK new={len(real)} admins={len(admins)} "
        f"push_deliveries={push_success} checked_at={now.isoformat()}"
    )


if __name__ == "__main__":
    main()
