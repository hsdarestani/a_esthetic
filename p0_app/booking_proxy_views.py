from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.booking_gateway import request_booking


def _proxy(request, path):
    user, error = legacy_mobile_api._auth(request)
    if error:
        return error
    status, payload = request_booking(request, path)
    return JsonResponse(payload, status=status)


@csrf_exempt
@require_http_methods(['GET'])
def mobile_slots(request):
    return _proxy(request, 'slots/')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def mobile_booking(request):
    return _proxy(request, 'booking/')


@csrf_exempt
@require_http_methods(['GET'])
def mobile_manageable_appointments(request):
    return _proxy(request, 'booking/manageable/')


@csrf_exempt
@require_http_methods(['POST'])
def mobile_appointment_change(request, appointment_id):
    return _proxy(request, f'booking/{appointment_id}/change/')
