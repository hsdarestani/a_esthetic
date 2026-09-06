import json

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app.models import MemberAccount

from .admin_mobile_views import _admin_auth, _customer_payload


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


@csrf_exempt
@require_http_methods(["POST"])
def mobile_admin_wallet_lookup(request):
    """Resolve a scanned member QR token to the customer wallet.

    The QR token is deliberately never returned by customer-list APIs. It is only
    accepted here over an authenticated A+ admin request and compared exactly.
    """
    actor, error = _admin_auth(request)
    if error:
        return error

    token = str(_json(request).get("qr_token") or "").strip()
    if not token or len(token) > 128:
        return JsonResponse({"ok": False, "error": "invalid_wallet_qr"}, status=400)

    member = MemberAccount.objects.select_related("user").filter(qr_token=token).first()
    if not member:
        return JsonResponse({"ok": False, "error": "wallet_not_found"}, status=404)

    user = User.objects.filter(
        pk=member.user_id,
        is_active=True,
        is_superuser=False,
        profile__role="customer",
    ).first()
    if not user:
        return JsonResponse({"ok": False, "error": "wallet_not_found"}, status=404)

    return JsonResponse({
        "ok": True,
        "customer": _customer_payload(user),
        "resolved_by": "wallet_qr",
        "admin_id": actor.pk,
    })
