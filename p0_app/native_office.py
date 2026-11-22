"""Native admin Office APIs; never resolve clinical identity from unverified input."""
import hashlib
import json
import re
import unicodedata
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from uuid import UUID

from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from platform_app.admin_aware_login import _is_admin
from platform_app.mobile_api import _auth
from platform_app.goae_billing import create_goae_draft, goae_draft_pdf_bytes
from platform_app.models import AuditLog, Invoice, InvoiceSettings, OfficePatientLink, UserProfile
from .mobile_staff_views import NoRedirect


def error(code, status=400):
    return JsonResponse({'ok': False, 'error': code}, status=status)


def read_book(request, path):
    # path is assembled exclusively from validated integer/UUID identifiers.
    origin = settings.MOBILE_STAFF_BOOK_ORIGIN if hasattr(settings, 'MOBILE_STAFF_BOOK_ORIGIN') else 'https://book.a-esthetic.de'
    query = Request(f'{origin}/api/mobile/staff/{path}/', headers={
        'Authorization': request.headers['Authorization'], 'Accept': 'application/json',
    })
    try:
        with build_opener(NoRedirect).open(query, timeout=8) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                return None
            result = json.loads(raw)
            return result if isinstance(result, dict) and result.get('ok') else None
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None


def normalized_name(value):
    value = unicodedata.normalize('NFC', str(value or '')).casefold()
    return ' '.join(value.split())


def normalized_phone(value):
    digits = re.sub(r'[^0-9]', '', str(value or ''))
    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = '49' + digits[1:]
    return digits if 8 <= len(digits) <= 15 else ''


def identity_score(user, profile, book):
    local = (normalized_name(user.first_name), normalized_name(user.last_name),
             normalized_phone(profile.phone), user.email.strip().casefold(),
             profile.date_of_birth.isoformat() if profile.date_of_birth else '')
    remote = (normalized_name(book.get('first_name')), normalized_name(book.get('last_name')),
              normalized_phone(book.get('phone')), str(book.get('email') or '').strip().casefold(),
              str(book.get('date_of_birth') or ''))
    return sum(bool(a and b and a == b) for a, b in zip(local, remote))


def customer(pk):
    return User.objects.filter(pk=pk, is_active=True, is_staff=False, is_superuser=False,
                               profile__role='customer').select_related('profile').first()


def person(user):
    profile = user.profile
    link = OfficePatientLink.objects.filter(user=user).first()
    return {'id': user.pk, 'name': user.get_full_name(), 'email': user.email, 'phone': profile.phone,
            'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            'book_customer_id': link.book_customer_id if link else None,
            'address': {'street': profile.street, 'postal_code': profile.postal_code, 'city': profile.city}}


def serialize(invoice):
    return {'id': invoice.pk, 'number': invoice.number, 'status': invoice.status, 'customer_id': invoice.user_id,
            'service_date': invoice.service_date.isoformat(),
            'book_appointment_public_id': str(invoice.book_appointment_public_id) if invoice.book_appointment_public_id else None,
            'subtotal_cents': invoice.subtotal_cents, 'tax_cents': invoice.tax_cents, 'total_cents': invoice.total_cents}


@csrf_exempt
@never_cache
@require_http_methods(['GET', 'POST'])
def office(request, operation, ident=None):
    actor, auth_error = _auth(request, allow_incomplete=True)
    if auth_error:
        return auth_error
    if operation == 'intake' and ident is None:
        # Account-authenticated intake cannot alter any other user's identity.
        owner = customer(actor.pk)
        if not owner:
            return error('customer_required', 403)
        if request.method == 'GET':
            return JsonResponse({'ok': True, 'patient': person(owner)})
        try:
            if len(request.body) > 4000:
                raise ValueError
            incoming = json.loads(request.body)
            if not isinstance(incoming, dict):
                raise ValueError
            dob = date.fromisoformat(str(incoming['date_of_birth']))
            if not date(1900, 1, 1) <= dob <= timezone.localdate():
                raise ValueError
            limits = {'street':180, 'postal_code':20, 'city':120}
            fields = {key: str(incoming[key]).strip() for key in limits}
            if not all(fields[key] and len(fields[key]) <= limits[key] for key in fields):
                raise ValueError
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=owner)
                if profile.date_of_birth and profile.date_of_birth != dob:
                    return error('identity_verification_required', 409)
                for key, value in fields.items():
                    setattr(profile, key, value)
                profile.date_of_birth = dob
                profile.save(update_fields=[*fields, 'date_of_birth'])
                AuditLog.objects.create(actor=actor, action='Authenticated Office intake saved',
                    entity_type='User', entity_id=str(owner.pk), metadata={'source': 'native_customer'})
            return JsonResponse({'ok': True})
        except (ValueError, TypeError, KeyError):
            return error('invalid_intake')
    if not _is_admin(actor):
        return error('admin_required', 403)
    if request.method == 'GET':
        if operation == 'customers' and ident is None:
            query = request.GET.get('q', '').strip()[:100]
            if len(query) < 2:
                return JsonResponse({'ok': True, 'items': []})
            users = User.objects.filter(is_active=True, is_staff=False, is_superuser=False, profile__role='customer')
            for term in query.split():
                users = users.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(email__icontains=term))
            users = users.select_related('profile').order_by('last_name', 'first_name', 'pk')[:30]
            return JsonResponse({'ok': True, 'items': [person(user) for user in users]})
        if operation == 'invoices' and ident is not None:
            if not customer(ident):
                return error('not_found', 404)
            return JsonResponse({'ok': True, 'items': [serialize(row) for row in
                Invoice.objects.filter(user_id=ident, billing_method='goae').order_by('-pk')[:100]]})
        if operation == 'pdf' and ident is not None:
            invoice = Invoice.objects.filter(pk=ident, billing_method='goae', status='draft').first()
            if not invoice:
                return error('not_found', 404)
            response = HttpResponse(goae_draft_pdf_bytes(invoice, InvoiceSettings()), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="goae-draft.pdf"'
            response['X-Content-Type-Options'] = 'nosniff'
            return response
        return error('not_found', 404)

    if len(request.body) > 128000:
        return error('invalid_request')
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        uid = int(data['customer_id'])
        user = customer(uid)
        if not user:
            return error('not_found', 404)
        if operation == 'link':
            book_id = int(data['book_customer_id'])
            if book_id <= 0 or data.get('confirmed_same_patient') is not True:
                return error('identity_verification_required', 409)
            remote = read_book(request, f'patient/{book_id}')
            if not remote or remote.get('patient', {}).get('id') != book_id:
                return error('book_unavailable', 503)
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=user)
                if identity_score(user, profile, remote['patient']) < 3:
                    return error('identity_verification_required', 409)
                previous = OfficePatientLink.objects.filter(Q(user=user) | Q(book_customer_id=book_id)).first()
                if previous:
                    if previous.user_id == uid and previous.book_customer_id == book_id:
                        return JsonResponse({'ok': True, 'book_customer_id': book_id})
                    return error('identity_link_conflict', 409)
                OfficePatientLink.objects.create(user=user, book_customer_id=book_id, verified_by=actor)
                AuditLog.objects.create(actor=actor, action='Office patient identity confirmed',
                    entity_type='User', entity_id=str(uid), metadata={'book_customer_id': book_id})
            return JsonResponse({'ok': True, 'book_customer_id': book_id})

        if operation != 'draft':
            return error('not_found', 404)
        request_id = UUID(str(data['request_id']))
        visit_id = UUID(str(data['visit_id']))
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        # A replay must not create a second invoice.
        previous = Invoice.objects.filter(native_request_id=request_id).first()
        if previous:
            if previous.user_id == uid and previous.book_appointment_public_id == visit_id and previous.native_request_fingerprint == fingerprint:
                return JsonResponse({'ok': True, 'invoice': serialize(previous), 'replayed': True})
            return error('request_conflict', 409)
        link = OfficePatientLink.objects.filter(user=user).first()
        if not link:
            return error('verified_identity_required', 409)
        remote = read_book(request, f'patient/{link.book_customer_id}/visits/{visit_id}')
        if not remote or str(remote.get('visit', {}).get('public_id')) != str(visit_id) or remote.get('visit', {}).get('customer_id') != link.book_customer_id:
            return error('visit_unavailable', 409)
        visit = remote['visit']
        if visit['status'] != 'completed':
            return error('completed_visit_required', 409)
        original_date = date.fromisoformat(visit['date'])
        service_date = date.fromisoformat(str(data.get('service_date') or original_date))
        correction = str(data.get('date_correction_reason') or '').strip()
        if service_date > timezone.localdate() or len(correction) > 500 or (service_date != original_date and not correction):
            return error('invalid_service_date')
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get(user=user)
            if not OfficePatientLink.objects.filter(pk=link.pk, user=user, book_customer_id=link.book_customer_id).exists():
                return error('verified_identity_required', 409)
            address = data.get('address', {})
            if not isinstance(address, dict):
                raise ValueError
            addr = {key: str(address.get(key, getattr(profile, key))).strip() for key in ('street','postal_code','city')}
            limits = {'street':180, 'postal_code':20, 'city':120}
            if not all(addr[key] and len(addr[key]) <= limits[key] for key in addr):
                return error('billing_address_required')
            invoice = create_goae_draft(user=user, actor=actor, service_date=service_date, data=data)
            invoice.book_appointment_public_id = visit_id
            invoice.book_original_service_date = original_date
            invoice.service_date_correction = correction
            invoice.native_request_id = request_id
            invoice.native_request_fingerprint = fingerprint
            invoice.customer_street = addr['street']
            invoice.customer_postal_code = addr['postal_code']
            invoice.customer_city = addr['city']
            invoice.save(update_fields=['book_appointment_public_id','book_original_service_date','service_date_correction',
                'native_request_id','native_request_fingerprint','customer_street','customer_postal_code','customer_city'])
            # Persist only genuinely missing profile fields after explicit consent.
            if data.get('save_missing_address') is True:
                changed = []
                for key in addr:
                    if not getattr(profile, key):
                        setattr(profile, key, addr[key])
                        changed.append(key)
                if changed:
                    profile.save(update_fields=changed)
            AuditLog.objects.create(actor=actor, action='Office GOAE draft created',
                entity_type='Invoice', entity_id=str(invoice.pk), metadata={
                    'book_visit_id': str(visit_id), 'original_service_date': original_date.isoformat(),
                    'service_date': service_date.isoformat(), 'address_saved': data.get('save_missing_address') is True,
                })
        return JsonResponse({'ok': True, 'invoice': serialize(invoice)}, status=201)
    except IntegrityError:
        return error('request_conflict', 409)
    except (ValueError, TypeError, KeyError, OverflowError):
        return error('invalid_request')
