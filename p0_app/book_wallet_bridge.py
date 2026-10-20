"""Private, minimal wallet transport for the Booking administrative website.

Validated shared server credential; no browser bearer and no endpoints beyond
customer lookup, coin-only adjustment, wallet history and QR lookup.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .book_billing_bridge import _verified
from .admin_mobile_views import mobile_admin_customers, mobile_admin_customer
from .admin_wallet_history_views import mobile_admin_wallet_history
from .wallet_lookup_views import mobile_admin_wallet_lookup


@csrf_exempt
@require_http_methods(["GET", "POST"])
def book_wallet(request, operation, item_id=None):
    denied = _verified(request)
    if denied is not None:
        return denied
    if operation == "customers" and not item_id and request.method == "GET":
        return mobile_admin_customers(request)
    if operation == "history" and item_id and request.method == "GET":
        return mobile_admin_wallet_history(request, item_id)
    if operation == "lookup" and not item_id and request.method == "POST":
        return mobile_admin_wallet_lookup(request)
    if operation == "adjust" and item_id and request.method == "POST":
        # Only coin_delta is supported; never expose credit, membership or
        # profile mutation capabilities through the Booking admin bridge.
        from .admin_mobile_views import _json
        data = _json(request)
        if set(data) != {"coin_delta"} or type(data["coin_delta"]) is not int:
            return JsonResponse({"ok": False, "error": "only_coin_adjustment_allowed"}, status=400)
        if data["coin_delta"] == 0 or abs(data["coin_delta"]) > 100000:
            return JsonResponse({"ok": False, "error": "invalid_coin_adjustment"}, status=400)
        return mobile_admin_customer(request, item_id)
    return JsonResponse({"ok": False, "error": "unsupported_operation"}, status=404)
