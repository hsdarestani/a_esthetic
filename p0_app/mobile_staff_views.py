"""Bearer-only role resolution and narrow Book relay for the bundled app."""

import json
import re
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from platform_app.admin_aware_login import _is_admin
from platform_app.mobile_api import _auth
from platform_app.models import AuditLog, WalletAccount, WalletTransaction
from .doctor_views import _is_qamar_doctor


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _session(request):
    user, error = _auth(request, allow_incomplete=True)
    if error:
        return None, error
    role = 'admin' if _is_admin(user) else 'doctor' if _is_qamar_doctor(user) else 'customer'
    return {'id': user.pk, 'name': user.get_full_name() or user.username, 'role': role}, None


@never_cache
@require_GET
def session(request):
    identity, error = _session(request)
    return error or JsonResponse(identity)


@csrf_exempt
@never_cache
@require_http_methods(['GET', 'POST'])
def book(request, operation):
    identity, error = _session(request)
    if error:
        return error
    if identity['role'] == 'customer':
        return JsonResponse({'ok': False, 'error': 'staff_required'}, status=403)
    read = r'(?:overview|calendar|catalog|appointments|patients|identity-review|forms(?:/[1-9][0-9]*(?:/pdf)?)?|patient/[1-9][0-9]*(?:/records/[0-9a-f-]{36})?)'
    write = r'(?:appointment|block|availability|service|record-note|record-upload|record-edit|identity-review|forms/[1-9][0-9]*/link)'
    if not re.fullmatch(read if request.method == 'GET' else write, operation):
        return JsonResponse({'ok': False, 'error': 'not_found'}, status=404)
    if identity['role'] == 'doctor' and (operation in {'service', 'identity-review'} or operation == 'forms' or operation.startswith('forms/')):
        return JsonResponse({'ok': False, 'error': 'admin_required'}, status=403)
    origin = getattr(settings, 'MOBILE_STAFF_BOOK_ORIGIN', 'https://book.a-esthetic.de')
    url = f'{origin}/api/mobile/staff/{operation}/'
    query = request.GET.urlencode()
    if query:
        url += f'?{query}'
    remote = Request(
        url, data=request.body if request.method == 'POST' else None, method=request.method,
        headers={'Authorization': request.headers['Authorization'], 'Accept': 'application/json',
                 'Content-Type': 'application/json'},
    )
    try:
        upstream = build_opener(NoRedirect).open(remote, timeout=12)
    except HTTPError as exc:
        upstream = exc
    except (URLError, TimeoutError):
        return JsonResponse({'ok': False, 'error': 'book_unavailable'}, status=503)

    if upstream.code == 200 and (('/records/' in operation and upstream.headers.get_content_type() == 'application/octet-stream') or
                                 (operation.startswith('forms/') and operation.endswith('/pdf') and upstream.headers.get_content_type() == 'application/pdf')):
        def stream():
            with upstream:
                yield from iter(lambda: upstream.read(64 * 1024), b'')
        response = StreamingHttpResponse(stream(), content_type=upstream.headers.get_content_type())
        response['Content-Disposition'] = upstream.headers.get('Content-Disposition', 'attachment')
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    try:
        with upstream:
            if upstream.headers.get_content_type() != 'application/json':
                return JsonResponse({'ok': False, 'error': 'book_unavailable'}, status=502)
            raw = upstream.read(4 * 1024 * 1024 + 1)
    except (OSError, TimeoutError):
        return JsonResponse({'ok': False, 'error': 'book_unavailable'}, status=503)
    if len(raw) > 4 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'book_response_too_large'}, status=502)
    return HttpResponse(raw, status=upstream.code, content_type='application/json')


@csrf_exempt
@never_cache
@require_http_methods(['POST'])
def points(request, customer_id):
    identity, error = _session(request)
    if error:
        return error
    if identity['role'] != 'admin':
        return JsonResponse({'ok': False, 'error': 'admin_required'}, status=403)
    try:
        data = json.loads(request.body)
        key = str(UUID(data['key']))
        delta = data['coin_delta']
        if type(delta) is not int or not 0 < abs(delta) <= 100000:
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'invalid_coin_adjustment'}, status=400)
    with transaction.atomic():
        # Serialize retries by actor and wallet changes by target. Membership and
        # package balances are handled by their respective existing services.
        actor = User.objects.select_for_update().get(pk=identity['id'])
        customer = User.objects.filter(pk=customer_id, is_active=True, profile__role='customer',
                                       is_superuser=False, is_staff=False).first()
        if not customer:
            return JsonResponse({'ok': False, 'error': 'not_found'}, status=404)
        wallet, _ = WalletAccount.objects.select_for_update().get_or_create(user=customer)
        previous = AuditLog.objects.filter(actor=actor, action='Mobile staff points adjusted', metadata__key=key).first()
        if previous:
            if previous.entity_id != str(customer.pk) or previous.metadata['delta'] != delta:
                return JsonResponse({'ok': False, 'error': 'conflict'}, status=409)
            return JsonResponse({'ok': True, 'coins': wallet.coin_balance, 'replayed': True})
        if not 0 <= wallet.coin_balance + delta <= 2147483647:
            return JsonResponse({'ok': False, 'error': 'invalid_coin_balance',
                                 'message': 'Der neue Punktestand ist ungültig.'}, status=409)
        wallet.coin_balance += delta
        wallet.save(update_fields=['coin_balance', 'updated_at'])
        WalletTransaction.objects.create(
            user=customer, kind='coin', direction='in' if delta > 0 else 'out', coin_amount=abs(delta),
            description='Admin-Korrektur A+ Punkte', reference=f'mobile-staff:{key}',
        )
        AuditLog.objects.create(actor=actor, action='Mobile staff points adjusted', entity_type='UserAccount',
                                entity_id=str(customer.pk), metadata={'key': key, 'delta': delta})
        return JsonResponse({'ok': True, 'coins': wallet.coin_balance})
