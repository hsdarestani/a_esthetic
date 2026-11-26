"""Allow the trusted Booking server to serve the SAME invoice database on its web UI.

Never grant internal credentials to a browser. The shared token is checked
against server configuration and then routed only to billing endpoints.
"""
import json
from datetime import date

from django.contrib.auth.models import User
from django.db.models import Q
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
from platform_app.goae_billing import calculate_goae_lines
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
                             "treatments": TREATMENTS,
                             "review_required": True, "issuance_allowed": False})
    if operation == "patient-search" and request.method == "POST":
        try:
            data = json.loads(request.body) if len(request.body) <= 1024 else None
        except (UnicodeError, ValueError):
            data = None
        query = data.get('query') if isinstance(data, dict) else None
        if not isinstance(query, str) or not query.isprintable() or not 2 <= len(query.strip()) <= 80:
            return JsonResponse({'ok': False, 'error': 'invalid_search'}, status=400)
        patients = User.objects.filter(is_active=True, is_superuser=False, profile__role='customer')
        for term in query.split():
            patients = patients.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term)
                                       | Q(email__icontains=term))
        patients = patients.only('id', 'first_name', 'last_name', 'email').order_by('last_name', 'first_name', 'pk')
        return JsonResponse({'ok': True, 'patients': [
            {'id': patient.pk, 'name': patient.get_full_name() or patient.email, 'email': patient.email}
            for patient in patients[:25]
        ]}, headers={'Cache-Control': 'private, no-store, max-age=0'})
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
        response["Content-Disposition"] = f'inline; filename="Rechnung-{invoice.pk}.pdf"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    return JsonResponse({"ok": False, "error": "unsupported_operation"}, status=404)
