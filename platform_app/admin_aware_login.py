from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import mobile_api
from .models import AuditLog, UserProfile


def _is_admin(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return bool(
        user.is_superuser
        or profile.role == 'admin'
        or (user.is_staff and profile.role in {'admin', 'manager'})
    )


@csrf_exempt
@require_http_methods(['POST'])
def login(request):
    """Mobile login that keeps staff/admin identities out of Customer Club membership.

    Customer users retain the existing response and membership behavior. Admins get
    the same signed bearer token, but no MemberAccount/WalletAccount is created and
    the client can immediately enter the dedicated Book administration experience.
    """
    data = mobile_api._json(request)
    identifier = str(data.get('username') or data.get('email') or '').strip()
    password = str(data.get('password') or '')
    username = identifier
    if '@' in identifier:
        match = User.objects.filter(email__iexact=identifier).first()
        if match:
            username = match.username

    user = authenticate(request, username=username, password=password)
    if not user or not user.is_active:
        return JsonResponse({'ok': False, 'error': 'invalid_credentials'}, status=401)

    is_admin = _is_admin(user)
    AuditLog.objects.create(
        actor=user,
        action='Mobile App Login',
        entity_type='AdminAccount' if is_admin else 'UserAccount',
        entity_id=str(user.pk),
        metadata={'channel': 'book_admin_app' if is_admin else 'customer_club_app'},
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    payload = {
        'ok': True,
        'token': mobile_api._token_for(user),
        'admin': is_admin,
        'account_type': 'admin' if is_admin else 'customer',
    }
    if is_admin:
        payload['admin_profile'] = {
            'id': user.pk,
            'name': user.get_full_name() or user.username,
            'email': user.email,
        }
    else:
        payload['member'] = mobile_api._member_payload(user)
    return JsonResponse(payload)
