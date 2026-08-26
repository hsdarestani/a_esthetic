import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

BOOKING_SERVICE_BASE_URL = getattr(
    settings,
    'BOOKING_SERVICE_BASE_URL',
    'https://book.a-esthetic.de/api/mobile',
).rstrip('/')


def request_booking(request, path, *, method=None, payload=None, query=None, timeout=12):
    method = method or request.method
    target = f"{BOOKING_SERVICE_BASE_URL}/{path.lstrip('/')}"
    params = query
    if params is None and method == 'GET':
        params = request.GET
    if params:
        encoded = params.urlencode() if hasattr(params, 'urlencode') else urlencode(params, doseq=True)
        if encoded:
            target = f'{target}?{encoded}'

    headers = {
        'Accept': 'application/json',
        'User-Agent': 'A-Esthetic-App-Gateway/1.0',
    }
    authorization = request.headers.get('Authorization', '').strip()
    if authorization:
        headers['Authorization'] = authorization
    idempotency_key = request.headers.get('Idempotency-Key', '').strip()
    if idempotency_key:
        headers['Idempotency-Key'] = idempotency_key

    data = None
    if method != 'GET':
        headers['Content-Type'] = 'application/json'
        if payload is None:
            data = request.body or b'{}'
        else:
            data = json.dumps(payload).encode('utf-8')

    upstream = Request(target, data=data, method=method, headers=headers)
    try:
        with urlopen(upstream, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
            return response.status, json.loads(raw) if raw else {'ok': True}
    except HTTPError as exc:
        raw = exc.read().decode('utf-8', 'replace')
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {}
        if not body:
            body = {'ok': False, 'error': 'booking_service_error'}
        return exc.code, body
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return 503, {
            'ok': False,
            'error': 'booking_service_unavailable',
            'message': 'Die Terminbuchung ist vorübergehend nicht erreichbar. Bitte versuchen Sie es erneut.',
        }
