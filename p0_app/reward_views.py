import json
import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, Reward, WalletAccount, WalletTransaction

from .ops_models import RewardRedemption
from .push import create_notification


def _auth(request):
    return legacy_mobile_api._auth(request)


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _code():
    while True:
        value = "A+R-" + secrets.token_hex(5).upper()
        if not RewardRedemption.objects.filter(fulfillment_code=value).exists():
            return value


def redemption_payload(item):
    return {
        "id": item.pk,
        "reward_id": item.reward_id,
        "reward": item.reward.name,
        "fulfillment_code": item.fulfillment_code,
        "coin_cost": item.coin_cost,
        "status": item.status,
        "status_label": item.get_status_display(),
        "customer_note": item.customer_note,
        "admin_note": item.admin_note if item.status in {"fulfilled", "cancelled"} else "",
        "requested_at": item.requested_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "fulfilled_at": item.fulfilled_at.isoformat() if item.fulfilled_at else None,
        "cancelled_at": item.cancelled_at.isoformat() if item.cancelled_at else None,
    }


@csrf_exempt
@require_http_methods(["POST"])
def mobile_redeem_reward(request, reward_id):
    user, error = _auth(request)
    if error:
        return error
    data = _json(request)

    with transaction.atomic():
        reward = Reward.objects.select_for_update().filter(
            pk=reward_id,
            active=True,
            is_medical_service=False,
        ).first()
        if not reward:
            return JsonResponse({"ok": False, "error": "reward_not_found"}, status=404)
        try:
            reward.full_clean()
        except ValidationError:
            return JsonResponse({"ok": False, "error": "reward_not_available"}, status=409)

        wallet, _ = WalletAccount.objects.select_for_update().get_or_create(user=user)
        if wallet.coin_balance < reward.coin_cost:
            return JsonResponse({"ok": False, "error": "not_enough_coins"}, status=409)
        if reward.inventory is not None and reward.inventory < 1:
            return JsonResponse({"ok": False, "error": "reward_unavailable"}, status=409)

        redemption = RewardRedemption.objects.create(
            user=user,
            reward=reward,
            fulfillment_code=_code(),
            coin_cost=reward.coin_cost,
            customer_note=str(data.get("note") or "")[:2000],
        )
        wallet.coin_balance -= reward.coin_cost
        wallet.save(update_fields=["coin_balance", "updated_at"])
        WalletTransaction.objects.create(
            user=user,
            kind="coin",
            direction="out",
            coin_amount=reward.coin_cost,
            description=f"Reward reserviert: {reward.name}",
            reference=f"reward_redemption:{redemption.pk}",
        )
        if reward.inventory is not None:
            reward.inventory -= 1
            reward.save(update_fields=["inventory"])
        AuditLog.objects.create(
            actor=user,
            action="Reward eingelöst",
            entity_type="RewardRedemption",
            entity_id=str(redemption.pk),
            metadata={"reward_id": reward.pk, "coin_cost": reward.coin_cost},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    create_notification(
        user,
        "Reward reserviert",
        f"{reward.name} wurde reserviert. Ihr Abholcode lautet {redemption.fulfillment_code}.",
        category="reward",
        deeplink="wallet",
        data={"redemption_id": redemption.pk},
    )
    return JsonResponse({
        "ok": True,
        "coin_balance": wallet.coin_balance,
        "redemption": redemption_payload(redemption),
    }, status=201)


@csrf_exempt
@require_http_methods(["GET"])
def mobile_reward_redemptions(request):
    user, error = _auth(request)
    if error:
        return error
    items = RewardRedemption.objects.filter(user=user).select_related("reward")[:50]
    return JsonResponse({"ok": True, "redemptions": [redemption_payload(item) for item in items]})
