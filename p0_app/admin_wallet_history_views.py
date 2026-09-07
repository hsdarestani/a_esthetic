from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app.models import WalletAccount, WalletTransaction

from .admin_mobile_views import _admin_auth, _customer_payload


@csrf_exempt
@require_http_methods(["GET"])
def mobile_admin_wallet_history(request, customer_id):
    actor, error = _admin_auth(request)
    if error:
        return error

    user = User.objects.filter(
        pk=customer_id,
        is_active=True,
        is_superuser=False,
        profile__role="customer",
    ).first()
    if not user:
        return JsonResponse({"ok": False, "error": "customer_not_found"}, status=404)

    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    transactions = WalletTransaction.objects.filter(user=user).order_by("-created_at")[:120]

    return JsonResponse({
        "ok": True,
        "customer": _customer_payload(user),
        "wallet": {
            "balance_cents": wallet.balance_cents,
            "coin_balance": wallet.coin_balance,
            "updated_at": wallet.updated_at.isoformat() if wallet.updated_at else None,
        },
        "transactions": [
            {
                "id": item.pk,
                "kind": item.kind,
                "kind_label": item.get_kind_display(),
                "direction": item.direction,
                "direction_label": item.get_direction_display(),
                "amount_cents": item.amount_cents,
                "coin_amount": item.coin_amount,
                "description": item.description,
                "reference": item.reference,
                "issuer": item.issuer,
                "created_at": item.created_at.isoformat(),
            }
            for item in transactions
        ],
    })
