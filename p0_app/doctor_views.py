from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from platform_app.mobile_api import _auth
from platform_app.models import UserProfile


def _is_qamar_doctor(user):
    """An ordinary customer cannot impersonate a clinician by choosing a name."""
    if not user.is_staff or not user.is_active or user.is_superuser:
        return False
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return (
        profile.role == 'specialist'
        and user.first_name.strip().casefold() == 'qamar'
        and user.last_name.strip().casefold() == 'hameed'
    )


@csrf_exempt
@require_GET
def doctor_identity(request):
    user, error = _auth(request, allow_incomplete=True)
    if error:
        return error
    if not _is_qamar_doctor(user):
        return JsonResponse({'ok': False, 'error': 'doctor_required'}, status=403)
    response = JsonResponse({
        'ok': True,
        'doctor': {
            'id': user.pk,
            'name': user.get_full_name(),
            'email': user.email,
        },
    })
    response['Cache-Control'] = 'private, no-store, max-age=0'
    return response
