import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.booking_gateway import request_booking


@csrf_exempt
@require_http_methods(['GET'])
def mobile_dashboard(request):
    base_response = legacy_mobile_api.dashboard(request)
    if base_response.status_code != 200:
        return base_response

    try:
        payload = json.loads(base_response.content.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return base_response

    status, booking = request_booking(request, 'booking/', method='GET', query={})
    if status == 200 and booking.get('ok'):
        next_item = booking.get('next_appointment')
        payload['next_appointment'] = None if not next_item else {
            'id': next_item.get('id'),
            'title': next_item.get('service'),
            'starts_at': next_item.get('starts_at'),
            'status': next_item.get('status'),
        }

    return JsonResponse(payload, status=200)
