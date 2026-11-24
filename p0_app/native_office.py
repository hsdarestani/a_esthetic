"""Native admin Office APIs; never resolve clinical identity from unverified input."""
import hashlib
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal
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
from platform_app.goae_billing import calculate_goae_lines, create_goae_draft, goae_draft_pdf_bytes, to_decimal, cents
from platform_app.goae_tariff import catalog_payload, TREATMENTS, reference_case, POINT_VALUE_EUR
from platform_app.models import AuditLog, CheckInSession, Invoice, InvoiceItem, InvoiceSettings, OfficePatientLink, OfficeIntakeReview, OfficeIntakeSubmission, UserProfile
from platform_app.intake_identity import score, user_data, birth_date
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
            'revision': invoice.native_revision,
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
        if operation == 'invoice-settings' and ident is None:
            config, _ = InvoiceSettings.objects.get_or_create(pk=1)
            keys = ('company_name','street','postal_code','city','email','phone','tax_number','vat_id',
                    'bank_name','iban','bic','invoice_prefix','next_sequence')
            return JsonResponse({'ok':True, 'revision':config.updated_at.isoformat(),
                'ready_for_issue':config.ready_for_issue,
                'settings':{key:getattr(config,key) for key in keys}})
        if operation == 'tariff-catalog' and ident is None:
            return JsonResponse({'ok': True, 'items': catalog_payload(), 'treatments': TREATMENTS,
                'point_value_eur':str(POINT_VALUE_EUR),
                'approval_required': True, 'synthetic_reference_available': bool(getattr(settings, 'OFFICE_SYNTHETIC_STAGE', False))})
        if operation == 'reference-case' and ident is None:
            if not getattr(settings, 'OFFICE_SYNTHETIC_STAGE', False):
                return error('not_found', 404)
            return JsonResponse({'ok':True, **reference_case()})
        if operation == 'intake-reviews' and ident is None:
            rows = OfficeIntakeReview.objects.filter(status='pending').order_by('created_at')[:100]
            return JsonResponse({'ok': True, 'items': [{
                'id': row.pk, 'submission': row.payload, 'created_at': row.created_at.isoformat(),
            } for row in rows]})
        if operation == 'submissions' and ident is None:
            # List only the minimal identifying fields; clinical answers and
            # signature bytes are loaded only on explicit detail selection.
            query = request.GET.get('q', '').strip()[:100]
            status = request.GET.get('status', '')
            try:
                page = max(1, min(10000, int(request.GET.get('page', '1'))))
            except ValueError:
                return error('invalid_page')
            rows = OfficeIntakeSubmission.objects.all()
            if status:
                if status not in {'pending', 'linked', 'review', 'error'}:
                    return error('invalid_status')
                rows = rows.filter(sync_status=status)
            for term in query.split():
                rows = rows.filter(Q(identity__first_name__icontains=term) |
                                   Q(identity__last_name__icontains=term) |
                                   Q(identity__email__icontains=term) |
                                   Q(identity__phone__icontains=term))
            start = (page - 1) * 30
            result = list(rows.order_by('-created_at', '-pk').defer('signature_png', 'answers')[start:start+31])
            return JsonResponse({'ok': True, 'has_more': len(result) > 30, 'items': [{
                'id': row.pk, 'name': ' '.join(str(row.identity.get(k, '')) for k in ('first_name', 'last_name')).strip(),
                'email': row.identity.get('email', ''), 'created_at': row.created_at.isoformat(),
                'status': row.sync_status,
            } for row in result[:30]]})
        if operation == 'submission' and ident is not None:
            row = OfficeIntakeSubmission.objects.filter(pk=ident).first()
            if not row:
                return error('not_found', 404)
            return JsonResponse({'ok': True, 'submission': {
                'id': row.pk, 'identity': row.identity, 'answers': row.answers,
                'signature_png': row.signature_png, 'created_at': row.created_at.isoformat(),
                'status': row.sync_status, 'book_customer_id': row.book_customer_id,
                'book_record_id': row.book_record_id,
            }})
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
        if operation == 'detail' and ident is not None:
            invoice = Invoice.objects.filter(pk=ident, billing_method='goae', native_request_id__isnull=False).first()
            if not invoice:
                return error('not_found', 404)
            return JsonResponse({'ok': True, 'invoice': serialize(invoice), 'draft': invoice.native_draft_data if invoice.status == 'draft' else {},
                'original_date': invoice.book_original_service_date.isoformat() if invoice.book_original_service_date else None,
                'can_simulate': bool(getattr(settings, 'OFFICE_SYNTHETIC_STAGE', False) and invoice.user.email.endswith('@example.test'))})
        if operation == 'pdf' and ident is not None:
            invoice = Invoice.objects.filter(pk=ident, billing_method='goae').first()
            if not invoice:
                return error('not_found', 404)
            synthetic = bool(getattr(settings, 'OFFICE_SYNTHETIC_STAGE', False) and invoice.status == 'issued' and (invoice.number or '').startswith('TEST-GOAE-'))
            if invoice.status != 'draft' and not synthetic:
                return error('not_found', 404)
            response = HttpResponse(goae_draft_pdf_bytes(invoice, InvoiceSettings(), simulation=synthetic), content_type='application/pdf')
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
        if operation == 'invoice-settings' and ident is None:
            if data.get('confirmed_financial_update') is not True:
                return error('financial_settings_confirmation_required', 409)
            required = {'company_name':180, 'street':180, 'postal_code':20, 'city':120, 'email':254, 'phone':40}
            optional = {'tax_number':80,'vat_id':80,'bank_name':120,'iban':64,'bic':32,'invoice_prefix':20}
            changes = {}
            try:
                if not data.get('revision') or len(str(data['revision']))>80:
                    return error('invalid_revision')
                for key, limit in {**required,**optional}.items():
                    if key not in data or not isinstance(data[key],str) or len(data[key].strip())>limit:
                        return error('invalid_settings')
                    val=data[key].strip()
                    if key in required and not val:
                        return error('required_settings')
                    changes[key]=val
                if '@' not in changes['email'] or ' ' in changes['email']:
                    return error('invalid_email')
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,20}',changes['invoice_prefix']):
                    return error('invalid_prefix')
                seq=int(data['next_sequence'])
                if not (1<=seq<=99999999):
                    return error('invalid_sequence')
                with transaction.atomic():
                    config, _ = InvoiceSettings.objects.select_for_update().get_or_create(pk=1)
                    if config.updated_at.isoformat()!=data['revision']:
                        return error('settings_conflict',409)
                    if seq<config.next_sequence:
                        return error('sequence_cannot_decrease',409)
                    for key,val in changes.items():
                        setattr(config,key,val)
                    config.iban=changes['iban'].replace(' ','')
                    config.bic=changes['bic'].upper()
                    config.next_sequence=seq
                    config.save()
                    AuditLog.objects.create(actor=actor,action='Native Office invoice settings changed',
                        entity_type='InvoiceSettings',entity_id=str(config.pk),
                        metadata={'fields':sorted(changes),'invoice_prefix':config.invoice_prefix,
                                  'next_sequence':seq})
                return JsonResponse({'ok':True,'revision':config.updated_at.isoformat(),
                    'ready_for_issue':config.ready_for_issue})
            except (ValueError, TypeError, KeyError):
                return error('invalid_settings')
        if operation == 'issue-simulation' and ident is not None:
            if not getattr(settings, 'OFFICE_SYNTHETIC_STAGE', False):
                return error('goae_issuance_requires_approval', 409)
            if data.get('confirmed_synthetic') is not True:
                return error('synthetic_confirmation_required', 409)
            with transaction.atomic():
                invoice = Invoice.objects.select_for_update().filter(pk=ident, billing_method='goae',
                    native_request_id__isnull=False, user__email__endswith='@example.test').first()
                if not invoice:
                    return error('not_found', 404)
                if invoice.status == 'issued' and (invoice.number or '').startswith('TEST-GOAE-'):
                    return JsonResponse({'ok': True, 'invoice': serialize(invoice), 'replayed': True})
                if invoice.status != 'draft' or int(data['revision']) != invoice.native_revision:
                    return error('draft_conflict', 409)
                counter, _ = InvoiceSettings.objects.select_for_update().get_or_create(pk=1)
                invoice.number = f'TEST-GOAE-{timezone.localdate().year}-{counter.next_sequence:05d}'
                counter.next_sequence += 1
                counter.save(update_fields=['next_sequence','updated_at'])
                invoice.status = 'issued'
                invoice.issued_on = timezone.localdate()
                invoice.issued_at = timezone.now()
                invoice.native_revision += 1
                invoice.save(update_fields=['number','status','issued_on','issued_at','native_revision'])
                AuditLog.objects.create(actor=actor, action='Synthetic GOAE invoice numbered',
                    entity_type='Invoice', entity_id=str(invoice.pk), metadata={'simulation': True,'number': invoice.number})
            return JsonResponse({'ok': True, 'invoice': serialize(invoice)})
        if operation == 'quote' and ident is None:
            lines = calculate_goae_lines(data)
            total=sum(item['gross_cents'] for item in lines)
            target=None
            if str(data.get('desired_total_eur') or '').strip():
                requested=to_decimal(data['desired_total_eur'])
                if not 1<=requested<=10000000 or requested!=requested.quantize(Decimal('.01')):
                    return error('invalid_target')
                target=cents(requested)
            return JsonResponse({'ok': True,
                'subtotal_cents': sum(item['net_cents'] for item in lines),
                'tax_cents': sum(item['tax_cents'] for item in lines),
                'total_cents': total,
                'target_cents':target,'target_matches':None if target is None else abs(total-target)<=1,
                'items': [{
                    'goae_number': item['goae_number'], 'description': item['description'],
                    'quantity': str(item['quantity']), 'factor': str(item['goae_factor']),
                    'base_cents':item['goae_base_cents'],'unit_gross_cents':item['unit_gross_cents'],
                    'net_cents': item['net_cents'], 'tax_cents': item['tax_cents'],
                    'gross_cents': item['gross_cents'],
                } for item in lines]})
        if operation == 'intake-review' and ident is not None:
            decision = data.get('decision')
            if decision not in {'approve', 'reject'}:
                return error('invalid_request')
            with transaction.atomic():
                row = OfficeIntakeReview.objects.select_for_update().filter(pk=ident).first()
                if not row:
                    return error('not_found', 404)
                if row.status != 'pending':
                    return error('review_already_resolved', 409)
                if decision == 'approve':
                    target = customer(int(data['customer_id']))
                    if not target or data.get('confirmed_same_patient') is not True:
                        return error('identity_verification_required', 409)
                    profile = UserProfile.objects.select_for_update().get(user=target)
                    if score(row.payload, user_data(target)) < 3:
                        return error('identity_verification_required', 409)
                    if row.session_id:
                        session = CheckInSession.objects.select_for_update().get(pk=row.session_id)
                        if session.completed_at and session.customer_id != target.pk:
                            return error('identity_link_conflict', 409)
                        session.customer = target
                        session.completed_at = timezone.now()
                        session.save(update_fields=['customer','completed_at'])
                    changed = []
                    for key in ('street','postal_code','city'):
                        if not getattr(profile, key) and row.payload.get(key):
                            setattr(profile, key, row.payload[key])
                            changed.append(key)
                    if not profile.date_of_birth and row.payload.get('date_of_birth'):
                        profile.date_of_birth = birth_date(row.payload['date_of_birth'])
                        changed.append('date_of_birth')
                    if changed:
                        profile.save(update_fields=changed)
                    row.matched_user = target
                row.status = 'approved' if decision == 'approve' else 'rejected'
                row.reviewed_by = actor
                row.reviewed_at = timezone.now()
                row.save(update_fields=['matched_user','status','reviewed_by','reviewed_at'])
                AuditLog.objects.create(actor=actor, action='Office intake reviewed',
                    entity_type='OfficeIntakeReview', entity_id=str(row.pk),
                    metadata={'decision': decision, 'customer_id': row.matched_user_id})
            return JsonResponse({'ok': True, 'status': row.status})
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

        if operation not in {'draft', 'edit-draft'}:
            return error('not_found', 404)
        editing = operation == 'edit-draft'
        if editing and ident is None:
            return error('not_found', 404)
        request_id = UUID(str(data['request_id'])) if not editing else None
        visit_id = UUID(str(data['visit_id']))
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        # A replay must not create a second invoice.
        previous = Invoice.objects.filter(native_request_id=request_id).first() if request_id else None
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
            if editing:
                invoice = Invoice.objects.select_for_update().filter(
                    pk=ident, user=user, billing_method='goae', native_request_id__isnull=False,
                    book_appointment_public_id=visit_id, status='draft').first()
                if not invoice or int(data['revision']) != invoice.native_revision:
                    return error('draft_conflict', 409)
                items = calculate_goae_lines(data)
                invoice.items.all().delete()
                InvoiceItem.objects.bulk_create([InvoiceItem(invoice=invoice, **item) for item in items])
                invoice.subtotal_cents = sum(item['net_cents'] for item in items)
                invoice.tax_cents = sum(item['tax_cents'] for item in items)
                invoice.total_cents = sum(item['gross_cents'] for item in items)
                invoice.service_date = service_date
                invoice.native_revision += 1
            else:
                invoice = create_goae_draft(user=user, actor=actor, service_date=service_date, data=data)
                invoice.native_request_id = request_id
                invoice.native_request_fingerprint = fingerprint
            invoice.book_appointment_public_id = visit_id
            invoice.book_original_service_date = original_date
            invoice.service_date_correction = correction
            invoice.customer_street = addr['street']
            invoice.customer_postal_code = addr['postal_code']
            invoice.customer_city = addr['city']
            invoice.native_draft_data = {
                'visit_id': str(visit_id), 'service_date': service_date.isoformat(),
                'date_correction_reason': correction, 'address': addr,
                'treatment': data.get('treatment') if data.get('treatment') in TREATMENTS else '', 'lines': [
                    {key: row[key] for key in ('kind','goae_number','goae_description','goae_points','goae_base_eur',
                        'goae_category','goae_factor','goae_vat_rate','quantity','goae_justification',
                        'material_receipt_reference','material_eligible','tariff_source','clinical_confirmed',
                        'analog','analog_confirmed') if key in row}
                    for row in (data.get('lines') or [data])],
            }
            invoice.save()
            # Persist only genuinely missing profile fields after explicit consent.
            if data.get('save_missing_address') is True:
                changed = []
                for key in addr:
                    if not getattr(profile, key):
                        setattr(profile, key, addr[key])
                        changed.append(key)
                if changed:
                    profile.save(update_fields=changed)
            AuditLog.objects.create(actor=actor, action='Office GOAE draft edited' if editing else 'Office GOAE draft created',
                entity_type='Invoice', entity_id=str(invoice.pk), metadata={
                    'book_visit_id': str(visit_id), 'original_service_date': original_date.isoformat(),
                    'service_date': service_date.isoformat(), 'address_saved': data.get('save_missing_address') is True,
                    'revision': invoice.native_revision, 'total_cents': invoice.total_cents,
                })
        return JsonResponse({'ok': True, 'invoice': serialize(invoice)}, status=200 if editing else 201)
    except IntegrityError:
        return error('request_conflict', 409)
    except (ValueError, TypeError, KeyError, OverflowError):
        return error('invalid_request')
