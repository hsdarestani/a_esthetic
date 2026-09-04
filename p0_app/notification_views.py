import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api

from .ops_models import AppNotification, PushDevice
from .push import push_configuration


def _auth(request):
    return legacy_mobile_api._auth(request)


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


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
