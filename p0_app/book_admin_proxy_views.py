import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .admin_mobile_views import _admin_auth

BOOK_ADMIN_API = "https://book.a-esthetic.de/api/mobile/app-admin"


def _authorization(request):
    return str(request.headers.get("Authorization") or "").strip()


def _proxy(request, endpoint, method=None):
    actor, error = _admin_auth(request)
    if error:
        return error
    auth = _authorization(request)
    if not auth.startswith("Bearer "):
        return JsonResponse({"ok": False, "error": "admin_required"}, status=403)

    query = request.GET.urlencode()
    url = f"{BOOK_ADMIN_API}/{endpoint.lstrip('/')}"
    if query:
        url += f"?{query}"
    outgoing_method = method or request.method
    body = request.body if outgoing_method in {"POST", "PUT", "PATCH", "DELETE"} else None
    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "User-Agent": "A-Esthetic-InApp-Book-Admin-Proxy/1.0",
    }
    if body is not None:
        headers["Content-Type"] = request.content_type or "application/json"
    remote = Request(url, data=body, method=outgoing_method, headers=headers)
    try:
        with urlopen(remote, timeout=18) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    except (URLError, TimeoutError) as exc:
        return JsonResponse({"ok": False, "error": "book_admin_unavailable", "message": str(exc)}, status=503)

    try:
        payload = json.loads(raw) if raw else {"ok": status < 400}
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid_book_admin_response"}, status=502)
    response = JsonResponse(payload, status=status, safe=isinstance(payload, dict))
    response["Cache-Control"] = "private, no-store, max-age=0"
    return response


@csrf_exempt
@require_http_methods(["GET"])
def overview(request):
    return _proxy(request, "overview/")


@csrf_exempt
@require_http_methods(["GET"])
def calendar(request):
    return _proxy(request, "calendar/")


@csrf_exempt
@require_http_methods(["GET"])
def bookings(request):
    return _proxy(request, "bookings/")


@csrf_exempt
@require_http_methods(["GET"])
def customers(request):
    return _proxy(request, "customers/")


@csrf_exempt
@require_http_methods(["GET"])
def customer_detail(request, customer_id):
    return _proxy(request, f"customers/{customer_id}/")


@csrf_exempt
@require_http_methods(["GET"])
def services(request):
    return _proxy(request, "services/")


@csrf_exempt
@require_http_methods(["GET"])
def settings(request):
    return _proxy(request, "settings/")


@csrf_exempt
@require_http_methods(["POST"])
def appointment_action(request, appointment_id):
    return _proxy(request, f"appointments/{appointment_id}/")


@csrf_exempt
@require_http_methods(["POST"])
def block_action(request):
    return _proxy(request, "blocks/")


@csrf_exempt
@require_http_methods(["POST"])
def service_action(request, service_id):
    return _proxy(request, f"services/{service_id}/")


@csrf_exempt
@require_http_methods(["POST"])
def day_override_action(request):
    return _proxy(request, "day-override/")
