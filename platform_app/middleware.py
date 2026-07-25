from .models import AuditLog
class AuditRequestMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        if request.user.is_authenticated and request.method in {'POST','PUT','PATCH','DELETE'} and response.status_code < 400:
            try:
                AuditLog.objects.create(actor=request.user,action=f'{request.method} {request.path}',ip_address=request.META.get('REMOTE_ADDR'),metadata={'status':response.status_code})
            except Exception:
                pass
        return response
