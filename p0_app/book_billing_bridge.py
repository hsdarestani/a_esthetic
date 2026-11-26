"""Allow the trusted Booking server to serve the SAME invoice database on its web UI.

Never grant internal credentials to a browser. The shared token is checked
against server configuration and then routed only to billing endpoints.
"""
import json
from datetime import date

from django.contrib.auth.models import User
from django.db.models import Q, Value
from django.db.models.functions import Replace
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .notification_views import _internal_authorized
from .billing_admin_views import (
    billing_overview,
    billing_settings,
    billing_service,
    billing_invoices,
    billing_invoice_finalize,
)
from platform_app.models import Invoice
from platform_app.office_views import _invoice_pdf_bytes
from platform_app.models import InvoiceSettings
from platform_app.goae_billing import calculate_goae_lines, calculate_quick_draft, create_goae_draft, goae_preview_pdf_bytes
from platform_app.goae_quick import template_options
from platform_app.goae_tariff import catalog_payload, TREATMENTS


def _verified(request):
    if not _internal_authorized(request):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    # Operate under a real configured admin identity for audit attribution.
    actor = (User.objects.filter(is_active=True)
             .filter(Q(is_superuser=True) | Q(profile__role="admin"))
             .distinct().order_by("pk").first())
    if actor is None:
        return JsonResponse({"ok": False, "error": "admin_not_configured"}, status=503)
    request._book_internal_billing_actor = actor
    return None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def book_billing(request, operation, item_id=None):
    denied = _verified(request)
    if denied is not None:
        return denied
    routes = {
        ("overview", "GET"): billing_overview,
        ("settings", "POST"): billing_settings,
        ("invoices", "POST"): billing_invoices,
    }
    if operation == "goae" and request.method == "GET":
        return JsonResponse({"ok": True, "catalog": catalog_payload(),
                             "treatments": TREATMENTS, "quick_templates": template_options(),
                             "review_required": True, "issuance_allowed": False})
    if operation == "patient-search" and request.method == "POST":
        try:
            data = json.loads(request.body) if len(request.body) <= 1024 else None
        except (UnicodeError, ValueError):
            data = None
        query = data.get('query') if isinstance(data, dict) else None
        if not isinstance(query, str) or not query.isprintable() or not 2 <= len(query.strip()) <= 80:
            return JsonResponse({'ok': False, 'error': 'invalid_search'}, status=400)
        offset = data.get('offset', 0)
        if type(offset) is not int or not 0 <= offset <= 100000:
            return JsonResponse({'ok': False, 'error': 'invalid_search'}, status=400)
        patients = User.objects.filter(is_active=True, is_superuser=False, profile__role='customer')
        digits = ''.join(c for c in query if c in '0123456789')
        if len(digits) >= 2 and all(c in '+0123456789 .()-/' for c in query):
            from django.db.models import F
            phone = F('profile__phone')
            for char in '+ .()-/':
                phone = Replace(phone, Value(char), Value(''))
            patients = patients.annotate(phone_digits=phone).filter(phone_digits__contains=digits)
        else:
            for term in query.split():
                patients = patients.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term)
                                           | Q(email__icontains=term) | Q(profile__phone__icontains=term))
        patients = patients.select_related('profile').order_by('last_name', 'first_name', 'pk')
        rows = list(patients[offset:offset + 26])
        return JsonResponse({'ok': True, 'patients': [
            {'id': patient.pk, 'name': patient.get_full_name() or patient.email, 'email': patient.email,
             'phone': patient.profile.phone, 'street': patient.profile.street,
             'postal_code': patient.profile.postal_code, 'city': patient.profile.city}
            for patient in rows[:25]
        ], 'next_offset': offset + 25 if len(rows) > 25 else None}, headers={'Cache-Control': 'private, no-store, max-age=0'})
    if operation in {'quick-quote', 'quick-draft'} and request.method == 'POST':
        try:
            data = json.loads(request.body) if len(request.body) <= 4096 else None
            if not isinstance(data, dict):
                raise ValueError('Ungültige Entwurfsangaben.')
            patient_id = str(data.get('customer_id', ''))
            if not patient_id.isdecimal() or len(patient_id) > 18:
                raise ValueError('Ungültige Patienten-ID.')
            patient = User.objects.filter(pk=int(patient_id), is_active=True, is_superuser=False,
                                          profile__role='customer').first()
            if patient is None:
                raise ValueError('Patient nicht gefunden.')
            service_date = date.fromisoformat(str(data.get('service_date', '')))
            if operation == 'quick-draft':
                if not data.get('draft_request_id') or not isinstance(data.get('quick_invoice'), dict):
                    raise ValueError('Vorlage und Entwurfsreferenz erforderlich.')
                draft = create_goae_draft(user=patient, actor=request._book_internal_billing_actor,
                                          service_date=service_date, data=data, allow_quick=True)
                return JsonResponse({'ok': True, 'invoice_id': draft.pk, 'total_cents': draft.total_cents})
            rows, _metadata = calculate_quick_draft(data.get('quick_invoice'))
            return JsonResponse({'ok': True, 'subtotal_cents': sum(row['net_cents'] for row in rows),
                                 'tax_cents': sum(row['tax_cents'] for row in rows),
                                 'total_cents': sum(row['gross_cents'] for row in rows),
                                 'items': [{'number': row['goae_number'], 'description': row['description'],
                                            'gross_cents': row['gross_cents']} for row in rows]})
        except (ValueError, TypeError, UnicodeError) as exc:
            return JsonResponse({'ok': False, 'message': str(exc)[:200]}, status=400)
    if operation == "quote" and request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Ungültige Angaben.")
            customer, service_date = None, None
            if data.get("customer_id") and data.get("service_date"):
                raw_id = str(data["customer_id"])
                if not raw_id.isdigit() or len(raw_id) > 18:
                    raise ValueError("Ungültige Patienten-ID.")
                customer = User.objects.filter(pk=int(raw_id), is_active=True,
                        is_superuser=False, profile__role="customer").first()
                service_date = date.fromisoformat(str(data["service_date"]))
                if customer is None:
                    raise ValueError("Patient nicht gefunden.")
            lines = calculate_goae_lines(data, user=customer, service_date=service_date)
        except (ValueError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
            return JsonResponse({"ok": False, "error": "invalid_goae",
                                 "message": str(exc)[:200]}, status=400)
        return JsonResponse({"ok": True,
            "subtotal_cents": sum(item["net_cents"] for item in lines),
            "tax_cents": sum(item["tax_cents"] for item in lines),
            "total_cents": sum(item["gross_cents"] for item in lines),
            "items": [{"goae_number": item["goae_number"], "description": item["description"],
                       "net_cents": item["net_cents"], "tax_cents": item["tax_cents"],
                       "gross_cents": item["gross_cents"]} for item in lines]})
    if operation == "draft" and request.method == "POST":
        try:
            data = json.loads(request.body)
        except (UnicodeError, ValueError):
            data = None
        if not isinstance(data, dict) or data.get("billing_method") != "goae" or not data.get("draft_request_id"):
            return JsonResponse({"ok": False, "error": "draft_request_required"}, status=400)
        return billing_invoices(request)
    if operation == 'pdf-preview' and request.method == 'POST':
        try:
            data = json.loads(request.body) if len(request.body) <= 150000 else None
            if not isinstance(data, dict):
                raise ValueError('Ungültige Vorschauangaben.')
            raw_id = str(data.get('customer_id', ''))
            if not raw_id.isdigit() or len(raw_id) > 18:
                raise ValueError('Ungültige Patienten-ID.')
            customer = User.objects.filter(pk=int(raw_id), is_active=True, is_superuser=False,
                                           profile__role='customer').select_related('profile').first()
            if customer is None:
                raise ValueError('Patient nicht gefunden.')
            service_date = date.fromisoformat(str(data.get('service_date', '')))
            settings = InvoiceSettings.objects.filter(pk=1).first() or InvoiceSettings()
            pdf = goae_preview_pdf_bytes(user=customer, actor=request._book_internal_billing_actor,
                                         service_date=service_date, data=data, settings=settings, allow_quick=True)
        except (ValueError, TypeError, UnicodeError) as exc:
            return JsonResponse({'ok': False, 'message': str(exc)[:200]}, status=400)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="GOAE-Rechnungsentwurf.pdf"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    handler = routes.get((operation, request.method))
    if handler:
        return handler(request)
    if request.method == "POST" and operation == "services" and item_id:
        return billing_service(request, item_id)
    if request.method == "POST" and operation == "finalize" and item_id:
        return billing_invoice_finalize(request, item_id)
    if request.method == "GET" and operation == "pdf" and item_id:
        invoice = Invoice.objects.filter(pk=item_id).prefetch_related("items").first()
        if not invoice:
            return JsonResponse({"ok": False, "error": "invoice_not_found"}, status=404)
        # Normal drafts are not payment documents; GOÄ drafts display ENTWURF
        # watermarks and remain explicitly non-final.
        if invoice.status != "issued" and invoice.billing_method != "goae":
            return JsonResponse({"ok": False, "error": "pdf_not_issued"}, status=409)
        settings, _ = InvoiceSettings.objects.get_or_create(pk=1)
        pdf = _invoice_pdf_bytes(invoice, settings)
        response = HttpResponse(pdf, content_type="application/pdf")
        name = 'Rechnungsentwurf' if invoice.status == 'draft' else 'Rechnung'
        response["Content-Disposition"] = f'attachment; filename="{name}-{invoice.pk}.pdf"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    return JsonResponse({"ok": False, "error": "unsupported_operation"}, status=404)
