import json
import os
import secrets
from pathlib import Path

from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.account_onboarding import award_referrer_first_booking

from .ops_models import AppNotification, PushDevice
from .push import create_notification, push_configuration


def _auth(request):
    return legacy_mobile_api._auth(request)


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _internal_sync_token():
    direct = (
        os.environ.get("PATIENT_RECORD_SYNC_TOKEN")
        or os.environ.get("PATIENT_SYNC_TOKEN")
        or ""
    ).strip()
    if direct:
        return direct
    token_file = (
        os.environ.get("PATIENT_RECORD_SYNC_TOKEN_FILE")
        or os.environ.get("PATIENT_SYNC_TOKEN_FILE")
        or "/etc/aesthetic-patient-sync.token"
    )
    try:
        return Path(token_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def _internal_authorized(request):
    expected = _internal_sync_token()
    provided = str(request.headers.get("X-Aesthetic-Patient-Sync") or "").strip()
    return bool(expected and provided and secrets.compare_digest(expected, provided))


def _payload(item):
    return {
        "id": item.pk,
        "title": item.title,
        "body": item.body,
        "category": item.category,
        "deeplink": item.deeplink,
        "data": item.data,
        "read": bool(item.read_at),
        "read_at": item.read_at.isoformat() if item.read_at else None,
        "created_at": item.created_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(["GET"])
def mobile_notifications(request):
    user, error = _auth(request)
    if error:
        return error
    items = AppNotification.objects.filter(user=user)[:100]
    return JsonResponse({
        "ok": True,
        "unread_count": AppNotification.objects.filter(user=user, read_at__isnull=True).count(),
        "push": push_configuration(),
        "notifications": [_payload(item) for item in items],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_notification_read(request, notification_id):
    user, error = _auth(request)
    if error:
        return error
    item = AppNotification.objects.filter(pk=notification_id, user=user).first()
    if not item:
        return JsonResponse({"ok": False, "error": "notification_not_found"}, status=404)
    if not item.read_at:
        item.read_at = timezone.now()
        item.save(update_fields=["read_at"])
    return JsonResponse({"ok": True, "notification": _payload(item)})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_notifications_read_all(request):
    user, error = _auth(request)
    if error:
        return error
    updated = AppNotification.objects.filter(user=user, read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({"ok": True, "updated": updated, "unread_count": 0})


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def mobile_push_devices(request):
    user, error = _auth(request)
    if error:
        return error
    data = _json(request)
    token = str(data.get("token") or "").strip()
    if not token or len(token) > 512:
        return JsonResponse({"ok": False, "error": "push_token_required"}, status=400)

    if request.method == "DELETE":
        updated = PushDevice.objects.filter(user=user, token=token).update(enabled=False, last_seen_at=timezone.now())
        return JsonResponse({"ok": True, "disabled": updated})

    platform = str(data.get("platform") or "").strip().lower()
    if platform not in {"android", "ios"}:
        return JsonResponse({"ok": False, "error": "invalid_push_platform"}, status=400)
    item, created = PushDevice.objects.update_or_create(
        token=token,
        defaults={
            "user": user,
            "platform": platform,
            "app_version": str(data.get("app_version") or "")[:40],
            "enabled": True,
            "last_seen_at": timezone.now(),
        },
    )
    return JsonResponse({
        "ok": True,
        "created": created,
        "device": {"id": item.pk, "platform": item.platform, "enabled": item.enabled},
        "push": push_configuration(),
    }, status=201 if created else 200)


@csrf_exempt
@require_http_methods(["POST"])
def internal_booking_notification(request):
    expected = _internal_sync_token()
    if not expected:
        return JsonResponse({"ok": False, "error": "booking_notification_sync_not_configured"}, status=503)
    if not _internal_authorized(request):
        return JsonResponse({"ok": False, "error": "booking_notification_sync_forbidden"}, status=403)

    data = _json(request)
    target = str(data.get("target") or "").strip().lower()
    event = str(data.get("event") or "booking_updated").strip().lower()[:60]
    title = str(data.get("title") or "").strip()[:180]
    body = str(data.get("body") or "").strip()[:5000]
    email = str(data.get("customer_email") or "").strip().lower()[:254]
    if target not in {"admin", "customer"}:
        return JsonResponse({"ok": False, "error": "invalid_notification_target"}, status=400)
    if not title or not body:
        return JsonResponse({"ok": False, "error": "notification_content_required"}, status=400)

    recipients = []
    missing_customer = False
    if target == "customer":
        customer = User.objects.filter(is_active=True, email__iexact=email).order_by("id").first() if email else None
        if customer:
            recipients = [customer]
        else:
            missing_customer = True
    else:
        recipients = list(
            User.objects.filter(is_active=True)
            .filter(
                Q(is_superuser=True)
                | Q(profile__role="admin")
                | Q(is_staff=True, profile__role="manager")
            )
            .distinct()
            .order_by("id")
        )

    push_deliveries = 0
    notifications = 0
    relay_data = {
        "booking_event": event,
        "booking_public_id": str(data.get("booking_public_id") or "")[:80],
        "booking_status": str(data.get("status") or "")[:40],
        "booking_starts_at": str(data.get("starts_at") or "")[:80],
        "booking_source": str(data.get("source") or "")[:40],
    }
    deeplink = "admin_booking" if target == "admin" else "appointments"
    for recipient in recipients:
        item = create_notification(
            recipient,
            title,
            body,
            category="booking",
            deeplink=deeplink,
            data=relay_data,
        )
        notifications += 1
        push_deliveries += sum(
            1 for row in (item.push_result or {}).get("devices", []) if row.get("ok")
        )

    return JsonResponse({
        "ok": True,
        "target": target,
        "event": event,
        "recipients": len(recipients),
        "notifications": notifications,
        "push_deliveries": push_deliveries,
        "missing_customer": missing_customer,
        "push": push_configuration(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def internal_referral_booking(request):
    expected = _internal_sync_token()
    if not expected:
        return JsonResponse({"ok": False, "error": "referral_sync_not_configured"}, status=503)
    if not _internal_authorized(request):
        return JsonResponse({"ok": False, "error": "referral_sync_forbidden"}, status=403)
    data = _json(request)
    email = str(data.get("customer_email") or "").strip().lower()
    if not email:
        return JsonResponse({"ok": False, "error": "customer_email_required"}, status=400)
    result = award_referrer_first_booking(
        email,
        str(data.get("booking_public_id") or ""),
    )
    return JsonResponse(result)
