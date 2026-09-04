import json

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import (
    AuditLog,
    FeatureModule,
    MemberAccount,
    MemberPackage,
    UserProfile,
    WalletAccount,
    WalletTransaction,
)

from .ops_models import AppNotification, PushDevice, RewardRedemption
from .push import create_notification, push_configuration
from .reward_views import redemption_payload

BOOK_ADMIN_URL = "https://book.a-esthetic.de/verwaltung/"
APP_ADMIN_URL = "https://esthetic.smarbiz.sbs/secure-admin/"


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _admin_auth(request):
    user, error = legacy_mobile_api._auth(request)
    if error:
        return None, error
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not (user.is_superuser or (user.is_staff and profile.role in {"admin", "manager"}) or profile.role == "admin"):
        return None, JsonResponse({"ok": False, "error": "admin_required"}, status=403)
    return user, None


def _customer_payload(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    member, _ = MemberAccount.objects.get_or_create(user=user)
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    return {
        "id": user.pk,
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "phone": profile.phone,
        "role": profile.role,
        "member_number": member.member_number,
        "tier": member.tier.name if member.tier else "A+ Member",
        "member_status": member.status,
        "coins": wallet.coin_balance,
        "credit_cents": wallet.balance_cents,
        "active_packages": MemberPackage.objects.filter(user=user, status="active").count(),
        "joined_at": user.date_joined.isoformat(),
    }


@csrf_exempt
@require_http_methods(["GET"])
def mobile_admin_overview(request):
    actor, error = _admin_auth(request)
    if error:
        return error
    customers = User.objects.filter(is_active=True, is_superuser=False)
    pending = RewardRedemption.objects.filter(status__in=["pending", "processing"]).select_related("user", "reward")[:25]
    modules = FeatureModule.objects.order_by("sort_order", "name_de")
    return JsonResponse({
        "ok": True,
        "admin": {
            "id": actor.pk,
            "name": actor.get_full_name() or actor.username,
            "email": actor.email,
            "superuser": actor.is_superuser,
        },
        "stats": {
            "customers": customers.count(),
            "active_packages": MemberPackage.objects.filter(status="active").count(),
            "pending_rewards": RewardRedemption.objects.filter(status__in=["pending", "processing"]).count(),
            "push_devices": PushDevice.objects.filter(enabled=True).count(),
            "unread_notifications": AppNotification.objects.filter(read_at__isnull=True).count(),
        },
        "links": {"book_admin": BOOK_ADMIN_URL, "app_admin": APP_ADMIN_URL},
        "push": push_configuration(),
        "modules": [
            {
                "key": item.key,
                "name": item.name_de,
                "description": item.description_de,
                "enabled": item.enabled,
                "customer_visible": item.customer_visible,
                "locked": item.key == "shop",
            }
            for item in modules
        ],
        "pending_rewards": [redemption_payload(item) | {"customer": _customer_payload(item.user)} for item in pending],
    })


@csrf_exempt
@require_http_methods(["GET"])
def mobile_admin_customers(request):
    actor, error = _admin_auth(request)
    if error:
        return error
    query = str(request.GET.get("q") or "").strip()
    users = User.objects.filter(is_active=True, is_superuser=False).order_by("-date_joined")
    if query:
        users = users.filter(
            Q(email__icontains=query)
            | Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(profile__phone__icontains=query)
        ).distinct()
    users = users[:100]
    return JsonResponse({"ok": True, "customers": [_customer_payload(user) for user in users]})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_admin_module(request, key):
    actor, error = _admin_auth(request)
    if error:
        return error
    item = FeatureModule.objects.filter(key=key).first()
    if not item:
        return JsonResponse({"ok": False, "error": "module_not_found"}, status=404)
    if key == "shop":
        return JsonResponse({"ok": False, "error": "shop_locked_disabled"}, status=409)
    data = _json(request)
    if "enabled" in data:
        item.enabled = bool(data["enabled"])
    if "customer_visible" in data:
        item.customer_visible = bool(data["customer_visible"])
    item.save(update_fields=["enabled", "customer_visible", "updated_at"])
    AuditLog.objects.create(
        actor=actor,
        action="App-Modul geändert",
        entity_type="FeatureModule",
        entity_id=str(item.pk),
        metadata={"key": key, "enabled": item.enabled, "customer_visible": item.customer_visible},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"ok": True, "module": {"key": key, "enabled": item.enabled, "customer_visible": item.customer_visible}})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_admin_reward(request, redemption_id):
    actor, error = _admin_auth(request)
    if error:
        return error
    data = _json(request)
    action = str(data.get("action") or "").strip()
    note = str(data.get("note") or "")[:3000]

    with transaction.atomic():
        item = RewardRedemption.objects.select_for_update().select_related("reward", "user").filter(pk=redemption_id).first()
        if not item:
            return JsonResponse({"ok": False, "error": "redemption_not_found"}, status=404)
        if action == "processing":
            if item.status != "pending":
                return JsonResponse({"ok": False, "error": "invalid_redemption_state"}, status=409)
            item.status = "processing"
            item.admin_note = note
            item.save(update_fields=["status", "admin_note", "updated_at"])
            title = "Reward wird vorbereitet"
            body = f"{item.reward.name} wird gerade vorbereitet. Code: {item.fulfillment_code}."
        elif action == "fulfill":
            if item.status not in {"pending", "processing"}:
                return JsonResponse({"ok": False, "error": "invalid_redemption_state"}, status=409)
            item.status = "fulfilled"
            item.admin_note = note
            item.fulfilled_by = actor
            item.fulfilled_at = timezone.now()
            item.save(update_fields=["status", "admin_note", "fulfilled_by", "fulfilled_at", "updated_at"])
            title = "Reward erfüllt"
            body = f"{item.reward.name} wurde als erfüllt markiert. Vielen Dank."
        elif action == "cancel":
            if item.status not in {"pending", "processing"}:
                return JsonResponse({"ok": False, "error": "invalid_redemption_state"}, status=409)
            wallet, _ = WalletAccount.objects.select_for_update().get_or_create(user=item.user)
            wallet.coin_balance += item.coin_cost
            wallet.save(update_fields=["coin_balance", "updated_at"])
            WalletTransaction.objects.create(
                user=item.user,
                kind="coin",
                direction="in",
                coin_amount=item.coin_cost,
                description=f"Reward storniert: {item.reward.name}",
                reference=f"reward_refund:{item.pk}",
            )
            if item.reward.inventory is not None:
                item.reward.inventory += 1
                item.reward.save(update_fields=["inventory"])
            item.status = "cancelled"
            item.admin_note = note
            item.cancelled_at = timezone.now()
            item.save(update_fields=["status", "admin_note", "cancelled_at", "updated_at"])
            title = "Reward storniert"
            body = f"{item.reward.name} wurde storniert. {item.coin_cost} A+ Coins wurden zurückgebucht."
        else:
            return JsonResponse({"ok": False, "error": "invalid_reward_action"}, status=400)

        AuditLog.objects.create(
            actor=actor,
            action=f"Reward-Fulfillment: {action}",
            entity_type="RewardRedemption",
            entity_id=str(item.pk),
            metadata={"customer_id": item.user_id, "note": note},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    create_notification(
        item.user,
        title,
        body,
        category="reward",
        deeplink="wallet",
        data={"redemption_id": item.pk},
    )
    return JsonResponse({"ok": True, "redemption": redemption_payload(item)})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_admin_notification(request):
    actor, error = _admin_auth(request)
    if error:
        return error
    data = _json(request)
    title = str(data.get("title") or "").strip()[:180]
    body = str(data.get("body") or "").strip()[:5000]
    category = str(data.get("category") or "general")
    deeplink = str(data.get("deeplink") or "")[:240]
    if len(title) < 2 or len(body) < 2:
        return JsonResponse({"ok": False, "error": "notification_content_required"}, status=400)
    if category not in {value for value, _ in AppNotification.CATEGORY}:
        return JsonResponse({"ok": False, "error": "invalid_notification_category"}, status=400)

    if bool(data.get("all_customers")):
        recipients = list(User.objects.filter(is_active=True, is_superuser=False).order_by("id")[:500])
    else:
        try:
            user_id = int(data.get("user_id"))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "notification_recipient_required"}, status=400)
        recipient = User.objects.filter(pk=user_id, is_active=True).first()
        if not recipient:
            return JsonResponse({"ok": False, "error": "customer_not_found"}, status=404)
        recipients = [recipient]

    pushed = 0
    for recipient in recipients:
        item = create_notification(
            recipient,
            title,
            body,
            category=category,
            deeplink=deeplink,
            data={"sent_by_admin": actor.pk},
        )
        pushed += sum(1 for row in item.push_result.get("devices", []) if row.get("ok"))

    AuditLog.objects.create(
        actor=actor,
        action="Push/Notification versendet",
        entity_type="AppNotification",
        metadata={"recipients": len(recipients), "push_deliveries": pushed, "category": category},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"ok": True, "recipients": len(recipients), "push_deliveries": pushed, "push": push_configuration()})
