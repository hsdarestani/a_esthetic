from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api


def _auth(request):
    return legacy_mobile_api._auth(request)


def _disabled_payload():
    return {
        "ok": True,
        "enabled": False,
        "status": "disabled",
        "message": "Der A+ Shop ist derzeit deaktiviert und wird zu einem späteren Zeitpunkt freigeschaltet.",
        "categories": [],
        "products": [],
        "orders": [],
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_shop(request):
    user, error = _auth(request)
    if error:
        return error
    if request.method == "GET":
        return JsonResponse(_disabled_payload())
    return JsonResponse({"ok": False, "error": "shop_disabled"}, status=409)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_shop_orders(request):
    user, error = _auth(request)
    if error:
        return error
    if request.method == "GET":
        return JsonResponse({"ok": True, "enabled": False, "orders": [], "message": _disabled_payload()["message"]})
    return JsonResponse({"ok": False, "error": "shop_disabled"}, status=409)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_shop_order_detail(request, order_id):
    user, error = _auth(request)
    if error:
        return error
    return JsonResponse({"ok": False, "error": "shop_disabled"}, status=409)


@csrf_exempt
@require_http_methods(["POST"])
def mobile_shop_order_cancel(request, order_id):
    user, error = _auth(request)
    if error:
        return error
    return JsonResponse({"ok": False, "error": "shop_disabled"}, status=409)
