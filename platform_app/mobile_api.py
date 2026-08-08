import json
from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core import signing
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    Appointment,
    AuditLog,
    Campaign,
    GiftCard,
    MemberAccount,
    MemberPackage,
    Message,
    Referral,
    Reminder,
    Reward,
    Service,
    StaffMember,
    Thread,
    UserProfile,
    WalletAccount,
    WalletTransaction,
)

TOKEN_SALT = 'aesthetic-customer-club-mobile-v1'
TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _token_for(user):
    return signing.dumps(
        {'uid': user.pk, 'password_marker': user.password[-16:]},
        salt=TOKEN_SALT,
        compress=True,
    )


def _user_from_request(request):
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    token = header[7:].strip()
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        user = User.objects.get(pk=payload['uid'], is_active=True)
        if payload.get('password_marker') != user.password[-16:]:
            return None
        return user
    except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist, KeyError):
        return None


def _auth(request):
    user = _user_from_request(request)
    if not user:
        return None, JsonResponse({'ok': False, 'error': 'authentication_required'}, status=401)
    return user, None


def _iso(value):
    return value.isoformat() if value else None


def _member_payload(user):
    member, _ = MemberAccount.objects.get_or_create(user=user)
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    return {
        'name': user.get_full_name() or user.username,
        'member_number': member.member_number,
        'tier': member.tier.name if member.tier else 'A+ Member',
        'member_status': member.status,
        'valid_until': member.valid_until.isoformat() if member.valid_until else None,
        'coins': wallet.coin_balance,
        'credit_cents': wallet.balance_cents,
    }


@csrf_exempt
@require_http_methods(['GET'])
def status(request):
    return JsonResponse({'ok': True, 'service': 'A+ Esthetic Customer Club API', 'time': timezone.now().isoformat()})


@csrf_exempt
@require_http_methods(['POST'])
def login(request):
    data = _json(request)
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
    AuditLog.objects.create(
        actor=user,
        action='Mobile App Login',
        entity_type='UserAccount',
        entity_id=str(user.pk),
        metadata={'channel': 'customer_club_app'},
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    return JsonResponse({'ok': True, 'token': _token_for(user), 'member': _member_payload(user)})


@csrf_exempt
@require_http_methods(['GET'])
def me(request):
    user, error = _auth(request)
    if error:
        return error
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return JsonResponse({
        'ok': True,
        'member': _member_payload(user),
        'profile': {
            'email': user.email,
            'phone': profile.phone,
            'marketing_consent': profile.marketing_consent,
            'preferred_language': profile.preferred_language,
        },
    })


@csrf_exempt
@require_http_methods(['GET'])
def dashboard(request):
    user, error = _auth(request)
    if error:
        return error
    next_appointment = Appointment.objects.filter(
        user=user,
        status__in=['requested', 'confirmed'],
        starts_at__gte=timezone.now(),
    ).order_by('starts_at').first()
    reminders = Reminder.objects.filter(user=user, status='scheduled').order_by('scheduled_for')[:4]
    packages = MemberPackage.objects.filter(user=user, status='active')[:4]
    return JsonResponse({
        'ok': True,
        'member': _member_payload(user),
        'next_appointment': None if not next_appointment else {
            'id': next_appointment.pk,
            'title': next_appointment.service.name,
            'starts_at': _iso(next_appointment.starts_at),
            'status': next_appointment.status,
        },
        'reminders': [
            {'id': item.pk, 'title': item.title, 'body': item.body, 'scheduled_for': _iso(item.scheduled_for)}
            for item in reminders
        ],
        'packages': [
            {
                'id': item.pk,
                'name': item.definition.name,
                'remaining_sessions': item.remaining_sessions,
                'expires_at': item.expires_at.isoformat(),
            }
            for item in packages
        ],
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def club(request):
    user, error = _auth(request)
    if error:
        return error
    if request.method == 'POST':
        data = _json(request)
        invited_email = str(data.get('invited_email') or '').strip()
        if not invited_email or '@' not in invited_email:
            return JsonResponse({'ok': False, 'error': 'valid_email_required'}, status=400)
        code = f'APLUS-{user.pk}-{Referral.objects.count() + 1}'
        Referral.objects.create(
            referrer=user,
            code=code,
            invited_email=invited_email,
            reward_coins=300,
        )
    campaigns = Campaign.objects.filter(
        active=True,
        starts_at__lte=timezone.now(),
        ends_at__gte=timezone.now(),
    )
    giftcards = GiftCard.objects.filter(purchaser=user)
    referrals = Referral.objects.filter(referrer=user).order_by('-created_at')[:20]
    return JsonResponse({
        'ok': True,
        'member': _member_payload(user),
        'campaigns': [
            {'id': c.pk, 'name': c.name, 'message': c.message, 'ends_at': _iso(c.ends_at)}
            for c in campaigns
        ],
        'giftcards': [
            {'id': c.pk, 'code': c.code, 'balance_cents': c.balance_cents, 'status': c.status}
            for c in giftcards
        ],
        'referrals': [
            {'id': r.pk, 'code': r.code, 'email': r.invited_email, 'status': r.status, 'reward_coins': r.reward_coins}
            for r in referrals
        ],
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def booking(request):
    user, error = _auth(request)
    if error:
        return error
    if request.method == 'POST':
        data = _json(request)
        service = Service.objects.filter(pk=data.get('service_id'), active=True, bookable_in_app=True).first()
        if not service:
            return JsonResponse({'ok': False, 'error': 'service_not_found'}, status=400)
        starts_at = parse_datetime(str(data.get('starts_at') or ''))
        if not starts_at:
            return JsonResponse({'ok': False, 'error': 'invalid_start_time'}, status=400)
        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
        if starts_at < timezone.now() + timedelta(hours=1):
            return JsonResponse({'ok': False, 'error': 'start_time_too_soon'}, status=400)
        staff = None
        if data.get('staff_id'):
            staff = StaffMember.objects.filter(pk=data.get('staff_id'), active=True).first()
            if not staff:
                return JsonResponse({'ok': False, 'error': 'staff_not_found'}, status=400)
        ends_at = starts_at + timedelta(minutes=service.duration_minutes + service.buffer_minutes)
        with transaction.atomic():
            if staff:
                StaffMember.objects.select_for_update().get(pk=staff.pk)
                if Appointment.objects.filter(
                    staff=staff,
                    status__in=['requested', 'confirmed'],
                    starts_at__lt=ends_at,
                    ends_at__gt=starts_at,
                ).exists():
                    return JsonResponse({'ok': False, 'error': 'time_not_available'}, status=409)
            appointment = Appointment.objects.create(
                user=user,
                service=service,
                staff=staff,
                starts_at=starts_at,
                ends_at=ends_at,
                status='requested',
                source='app',
                notes_customer='',
                consent_acknowledged=False,
            )
        return JsonResponse({'ok': True, 'appointment_id': appointment.pk}, status=201)

    services = Service.objects.filter(active=True, bookable_in_app=True).order_by('name')
    staff = StaffMember.objects.filter(active=True).order_by('display_name')
    appointments = Appointment.objects.filter(user=user).order_by('-starts_at')[:20]
    return JsonResponse({
        'ok': True,
        'services': [
            {'id': s.pk, 'name': s.name, 'duration_minutes': s.duration_minutes, 'price_label': s.price_label}
            for s in services
        ],
        'staff': [{'id': s.pk, 'name': s.display_name} for s in staff],
        'appointments': [
            {
                'id': a.pk,
                'service': a.service.name,
                'starts_at': _iso(a.starts_at),
                'status': a.status,
                'staff': a.staff.display_name if a.staff else '',
            }
            for a in appointments
        ],
    })


@csrf_exempt
@require_http_methods(['GET'])
def wallet(request):
    user, error = _auth(request)
    if error:
        return error
    account, _ = WalletAccount.objects.get_or_create(user=user)
    transactions = WalletTransaction.objects.filter(user=user)[:30]
    rewards = Reward.objects.filter(active=True).order_by('coin_cost')
    packages = MemberPackage.objects.filter(user=user, status='active')
    return JsonResponse({
        'ok': True,
        'balance_cents': account.balance_cents,
        'coin_balance': account.coin_balance,
        'transactions': [
            {
                'id': tx.pk,
                'description': tx.description,
                'kind': tx.kind,
                'direction': tx.direction,
                'amount_cents': tx.amount_cents,
                'coin_amount': tx.coin_amount,
                'created_at': _iso(tx.created_at),
            }
            for tx in transactions
        ],
        'rewards': [
            {'id': r.pk, 'name': r.name, 'description': r.description, 'coin_cost': r.coin_cost}
            for r in rewards
        ],
        'packages': [
            {
                'id': p.pk,
                'name': p.definition.name,
                'remaining_sessions': p.remaining_sessions,
                'expires_at': p.expires_at.isoformat(),
            }
            for p in packages
        ],
    })


@csrf_exempt
@require_http_methods(['POST'])
def redeem_reward(request, reward_id):
    user, error = _auth(request)
    if error:
        return error
    reward = Reward.objects.filter(pk=reward_id, active=True).first()
    if not reward:
        return JsonResponse({'ok': False, 'error': 'reward_not_found'}, status=404)
    with transaction.atomic():
        wallet = WalletAccount.objects.select_for_update().get(user=user)
        if wallet.coin_balance < reward.coin_cost:
            return JsonResponse({'ok': False, 'error': 'not_enough_coins'}, status=409)
        if reward.inventory is not None and reward.inventory < 1:
            return JsonResponse({'ok': False, 'error': 'reward_unavailable'}, status=409)
        wallet.coin_balance -= reward.coin_cost
        wallet.save(update_fields=['coin_balance', 'updated_at'])
        WalletTransaction.objects.create(
            user=user,
            kind='coin',
            direction='out',
            coin_amount=reward.coin_cost,
            description=f'Reward: {reward.name}',
        )
        if reward.inventory is not None:
            reward.inventory -= 1
            reward.save(update_fields=['inventory'])
    return JsonResponse({'ok': True, 'coin_balance': wallet.coin_balance})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def reminders(request):
    user, error = _auth(request)
    if error:
        return error
    if request.method == 'POST':
        data = _json(request)
        item = Reminder.objects.filter(pk=data.get('id'), user=user).first()
        if not item:
            return JsonResponse({'ok': False, 'error': 'reminder_not_found'}, status=404)
        item.status = 'dismissed' if item.status == 'scheduled' else 'scheduled'
        item.save(update_fields=['status'])
    items = Reminder.objects.filter(user=user).order_by('scheduled_for')
    return JsonResponse({
        'ok': True,
        'reminders': [
            {
                'id': item.pk,
                'title': item.title,
                'body': item.body,
                'scheduled_for': _iso(item.scheduled_for),
                'status': item.status,
            }
            for item in items
        ],
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def messages(request):
    user, error = _auth(request)
    if error:
        return error
    thread = Thread.objects.filter(user=user, status='open').first() or Thread.objects.create(
        user=user,
        subject='Anfrage an A+ Esthetic',
    )
    if request.method == 'POST':
        data = _json(request)
        body = str(data.get('body') or '').strip()
        if not body:
            return JsonResponse({'ok': False, 'error': 'message_required'}, status=400)
        if len(body) > 3000:
            return JsonResponse({'ok': False, 'error': 'message_too_long'}, status=400)
        Message.objects.create(thread=thread, sender=user, body=body)
    return JsonResponse({
        'ok': True,
        'messages': [
            {
                'id': msg.pk,
                'body': msg.body,
                'mine': msg.sender_id == user.pk,
                'sender': msg.sender.get_full_name() or msg.sender.username,
                'created_at': _iso(msg.created_at),
            }
            for msg in thread.messages.filter(is_internal=False)
        ],
    })


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def profile(request):
    user, error = _auth(request)
    if error:
        return error
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if request.method == 'POST':
        data = _json(request)
        profile.phone = str(data.get('phone') or '')[:40]
        profile.marketing_consent = bool(data.get('marketing_consent'))
        profile.save(update_fields=['phone', 'marketing_consent'])
    return JsonResponse({
        'ok': True,
        'profile': {
            'name': user.get_full_name() or user.username,
            'email': user.email,
            'phone': profile.phone,
            'marketing_consent': profile.marketing_consent,
        },
    })


@csrf_exempt
@require_http_methods(['POST'])
def account_deletion(request):
    user, error = _auth(request)
    if error:
        return error
    AuditLog.objects.create(
        actor=user,
        action='Kontolöschung angefordert',
        entity_type='UserAccount',
        entity_id=str(user.pk),
        metadata={'source': 'mobile_app', 'status': 'open'},
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    UserProfile.objects.filter(user=user).update(marketing_consent=False)
    return JsonResponse({'ok': True, 'message': 'deletion_requested'})
