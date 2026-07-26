import json

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone
from pywebpush import WebPushException, webpush

from experience_app.models import NotificationOutbox, NotificationPreference, PushSubscription


class Command(BaseCommand):
    help = "Versendet fällige A+ Benachrichtigungen mit Retry und Privatsphäre-Einstellungen."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        items = NotificationOutbox.objects.filter(status="queued", scheduled_for__lte=timezone.now()).select_related("user")[: options["limit"]]
        sent = failed = 0
        for item in items:
            preferences, _ = NotificationPreference.objects.get_or_create(user=item.user)
            title = item.title
            body = "Neue geschützte Information in der A+ App" if item.sensitive and preferences.hide_sensitive_text else item.body
            try:
                if item.channel == "email":
                    if not preferences.email_enabled or not item.user.email:
                        item.status = "cancelled"
                    else:
                        send_mail(title, body, getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@esthetic.smarbiz.sbs"), [item.user.email], fail_silently=False)
                        item.status = "sent"
                elif item.channel == "push":
                    if not preferences.push_enabled:
                        item.status = "cancelled"
                    elif not getattr(settings, "WEBPUSH_VAPID_PRIVATE_KEY", ""):
                        raise RuntimeError("VAPID-Konfiguration fehlt")
                    else:
                        subscriptions = PushSubscription.objects.filter(user=item.user, active=True)
                        if not subscriptions:
                            item.status = "cancelled"
                        else:
                            for subscription in subscriptions:
                                try:
                                    webpush(
                                        subscription_info={"endpoint": subscription.endpoint, "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}},
                                        data=json.dumps({"title": title, "body": body, "url": "https://esthetic.smarbiz.sbs/"}),
                                        vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                                        vapid_claims={"sub": getattr(settings, "WEBPUSH_VAPID_SUBJECT", "mailto:privacy@esthetic.smarbiz.sbs")},
                                    )
                                    subscription.last_success_at = timezone.now()
                                    subscription.last_error = ""
                                    subscription.save(update_fields=["last_success_at", "last_error", "updated_at"])
                                except WebPushException as exc:
                                    subscription.last_error = str(exc)[:1000]
                                    if getattr(exc.response, "status_code", None) in {404, 410}:
                                        subscription.active = False
                                    subscription.save(update_fields=["last_error", "active", "updated_at"])
                            item.status = "sent"
                else:
                    item.status = "sent"
                item.attempts += 1
                item.last_error = ""
                item.save(update_fields=["status", "attempts", "last_error", "updated_at"])
                sent += 1
            except Exception as exc:
                item.attempts += 1
                item.last_error = str(exc)[:1000]
                item.status = "failed" if item.attempts >= 5 else "queued"
                item.save(update_fields=["status", "attempts", "last_error", "updated_at"])
                failed += 1
        self.stdout.write(f"Versendet/erledigt: {sent}; fehlgeschlagen: {failed}")
