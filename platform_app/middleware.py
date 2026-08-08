from django.http import HttpResponse

from .models import AuditLog


class MobileApiCorsMiddleware:
    ALLOWED_ORIGINS = {
        'capacitor://localhost',
        'https://localhost',
        'http://localhost',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_mobile_api = request.path.startswith('/api/mobile/')
        origin = request.headers.get('Origin', '')

        if is_mobile_api and request.method == 'OPTIONS':
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if is_mobile_api and origin in self.ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
            response['Access-Control-Max-Age'] = '86400'
            response['Vary'] = 'Origin'

        return response


class AuditRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and response.status_code < 400:
            try:
                AuditLog.objects.create(
                    actor=request.user,
                    action=f'{request.method} {request.path}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    metadata={'status': response.status_code},
                )
            except Exception:
                pass
        return response
