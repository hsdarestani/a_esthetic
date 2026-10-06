from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app.book_sync import sync_service_catalog_from_book
from platform_app.models import (
    AuditLog,
    Invoice,
    InvoiceItem,
    InvoiceSettings,
    SecureDocument,
    Service,
    UserProfile,
)
from platform_app.office_views import (
    _format_eur_input,
    _invoice_pdf_bytes,
    _parse_eur_cents,
    _parse_service_date,
)

from .admin_mobile_views import _admin_auth, _json


def _money(cents):
    return f"{Decimal(cents or 0) / Decimal(100):.2f}".replace(".", ",")


def _settings_payload(item):
    return {
        "company_name": item.company_name,
        "street": item.street,
        "postal_code": item.postal_code,
        "city": item.city,
        "country": item.country,
        "email": item.email,
        "phone": item.phone,
        "tax_number": item.tax_number,
        "vat_id": item.vat_id,
        "iban": item.iban,
        "bic": item.bic,
        "bank_name": item.bank_name,
        "invoice_prefix": item.invoice_prefix,
        "next_sequence": item.next_sequence,
        "ready_for_issue": item.ready_for_issue,
    }


def _service_payload(item):
    return {
        "id": item.pk,
        "name": item.name,
        "slug": item.slug,
        "price_label": item.price_label,
        "price_cents": item.price_cents,
        "price_input": _format_eur_input(item.price_cents),
        "vat_rate": str(item.vat_rate).replace(".", ",") if item.vat_rate is not None else "",
        "configured": item.price_cents is not None and item.vat_rate is not None,
        "active": item.active,
    }


def _invoice_payload(item):
    return {
        "id": item.pk,
        "number": item.number,
        "status": item.status,
        "status_label": item.get_status_display(),
        "service_date": item.service_date.strftime("%d.%m.%Y"),
        "issued_on": item.issued_on.strftime("%d.%m.%Y") if item.issued_on else None,
        "customer_id": item.user_id,
        "customer_name": item.customer_name,
        "customer_email": item.customer_email,
        "total_cents": item.total_cents,
        "total": _money(item.total_cents),
        "tax_cents": item.tax_cents,
        "tax": _money(item.tax_cents),
        "document_id": item.document_id,
        "created_at": item.created_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(["GET"])
def billing_overview(request):
    actor, error = _admin_auth(request)
    if error:
        return error

    sync_service_catalog_from_book()
    settings, _ = InvoiceSettings.objects.get_or_create(pk=1)
    services = Service.objects.filter(active=True).order_by("name")
    invoices = Invoice.objects.select_related("user").order_by("-created_at")[:50]
    customers = (
        User.objects.filter(is_active=True, is_superuser=False, profile__role="customer")
        .select_related("profile", "member_account")
        .order_by("last_name", "first_name", "pk")[:1000]
    )
    configured = services.filter(price_cents__isnull=False, vat_rate__isnull=False).count()

    return JsonResponse({
        "ok": True,
        "settings": _settings_payload(settings),
        "stats": {
            "invoices": Invoice.objects.count(),
            "issued": Invoice.objects.filter(status="issued").count(),
            "drafts": Invoice.objects.filter(status="draft").count(),
            "configured_services": configured,
            "active_services": services.count(),
        },
        "services": [_service_payload(item) for item in services],
        "customers": [
            {
                "id": item.pk,
                "name": item.get_full_name() or item.email,
                "email": item.email,
                "phone": getattr(item.profile, "phone", ""),
                "member_number": getattr(getattr(item, "member_account", None), "member_number", ""),
                "address_complete": bool(
                    getattr(item.profile, "street", "")
                    and getattr(item.profile, "postal_code", "")
                    and getattr(item.profile, "city", "")
                ),
            }
            for item in customers
        ],
        "invoices": [_invoice_payload(item) for item in invoices],
    })


@csrf_exempt
@require_http_methods(["POST"])
def billing_settings(request):
    actor, error = _admin_auth(request)
    if error:
        return error

    data = _json(request)
    settings, _ = InvoiceSettings.objects.get_or_create(pk=1)

    try:
        next_sequence = int(data.get("next_sequence") or settings.next_sequence or 1)
        if next_sequence < 1:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_next_sequence"}, status=400)

    settings.company_name = str(data.get("company_name") or settings.company_name).strip()[:180]
    settings.street = str(data.get("street") or settings.street).strip()[:180]
    settings.postal_code = str(data.get("postal_code") or settings.postal_code).strip()[:20]
    settings.city = str(data.get("city") or settings.city).strip()[:120]
    settings.email = str(data.get("email") or settings.email).strip()[:254]
    settings.phone = str(data.get("phone") or settings.phone).strip()[:40]
    settings.tax_number = str(data.get("tax_number") or "").strip()[:80]
    settings.vat_id = str(data.get("vat_id") or "").strip()[:80]
    settings.iban = str(data.get("iban") or "").strip().replace(" ", "")[:64]
    settings.bic = str(data.get("bic") or "").strip().upper()[:32]
    settings.bank_name = str(data.get("bank_name") or "").strip()[:120]
    settings.invoice_prefix = str(data.get("invoice_prefix") or "RE").strip()[:20] or "RE"
    settings.next_sequence = next_sequence
    settings.save()

    AuditLog.objects.create(
        actor=actor,
        action="Mobile Rechnungseinstellungen geändert",
        entity_type="InvoiceSettings",
        entity_id=str(settings.pk),
        metadata={"channel": "admin_app"},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"ok": True, "settings": _settings_payload(settings)})


@csrf_exempt
@require_http_methods(["POST"])
def billing_service(request, service_id):
    actor, error = _admin_auth(request)
    if error:
        return error

    service = Service.objects.filter(pk=service_id, active=True).first()
    if not service:
        return JsonResponse({"ok": False, "error": "service_not_found"}, status=404)

    data = _json(request)
    price_raw = str(data.get("price") or data.get("price_input") or "").strip()
    vat_raw = str(data.get("vat_rate") or "").strip()

    if not price_raw and not vat_raw:
        service.price_cents = None
        service.vat_rate = None
        service.price_label = ""
        service.save(update_fields=["price_cents", "vat_rate", "price_label"])
    else:
        if not price_raw or not vat_raw:
            return JsonResponse({"ok": False, "error": "price_and_vat_required"}, status=400)
        try:
            cents = _parse_eur_cents(price_raw)
            vat = Decimal(vat_raw.replace(",", "."))
        except (ValueError, InvalidOperation):
            return JsonResponse({"ok": False, "error": "invalid_price_or_vat"}, status=400)
        if vat < 0 or vat > 100:
            return JsonResponse({"ok": False, "error": "invalid_vat"}, status=400)
        service.price_cents = cents
        service.vat_rate = vat
        service.price_label = f"{_format_eur_input(cents)} €"
        service.save(update_fields=["price_cents", "vat_rate", "price_label"])

    AuditLog.objects.create(
        actor=actor,
        action="Mobile Behandlungspreis geändert",
        entity_type="Service",
        entity_id=str(service.pk),
        metadata={"channel": "admin_app", "price_cents": service.price_cents, "vat_rate": str(service.vat_rate) if service.vat_rate is not None else None},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"ok": True, "service": _service_payload(service)})


@csrf_exempt
@require_http_methods(["POST"])
def billing_invoices(request):
    actor, error = _admin_auth(request)
    if error:
        return error

    data = _json(request)
    customer = User.objects.filter(
        pk=data.get("customer_id"), is_active=True, is_superuser=False, profile__role="customer"
    ).select_related("profile").first()
    service = Service.objects.filter(pk=data.get("service_id"), active=True).first()
    service_date = _parse_service_date(data.get("service_date"))

    if not customer or not service or not service_date:
        return JsonResponse({"ok": False, "error": "customer_service_date_required"}, status=400)
    if service.price_cents is None or service.vat_rate is None:
        return JsonResponse({"ok": False, "error": "service_billing_not_configured"}, status=409)

    profile = customer.profile
    gross = int(service.price_cents)
    rate = Decimal(service.vat_rate)
    divisor = Decimal("1") + (rate / Decimal("100"))
    net = int((Decimal(gross) / divisor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    tax = gross - net

    with transaction.atomic():
        invoice = Invoice.objects.create(
            user=customer,
            service_date=service_date,
            customer_name=customer.get_full_name() or customer.email,
            customer_email=customer.email,
            customer_street=profile.street,
            customer_postal_code=profile.postal_code,
            customer_city=profile.city,
            subtotal_cents=net,
            tax_cents=tax,
            total_cents=gross,
            created_by=actor,
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service=service,
            description=service.name,
            unit_gross_cents=gross,
            vat_rate=rate,
            net_cents=net,
            tax_cents=tax,
            gross_cents=gross,
        )
        AuditLog.objects.create(
            actor=actor,
            action="Mobile Rechnungsentwurf erstellt",
            entity_type="Invoice",
            entity_id=str(invoice.pk),
            metadata={"channel": "admin_app", "service": service.name, "customer_id": customer.pk},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    return JsonResponse({"ok": True, "invoice": _invoice_payload(invoice)}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def billing_invoice_finalize(request, invoice_id):
    actor, error = _admin_auth(request)
    if error:
        return error

    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().prefetch_related("items").filter(pk=invoice_id).first()
        if not invoice:
            return JsonResponse({"ok": False, "error": "invoice_not_found"}, status=404)
        if invoice.status != "draft":
            return JsonResponse({"ok": True, "invoice": _invoice_payload(invoice)})

        settings, _ = InvoiceSettings.objects.select_for_update().get_or_create(pk=1)
        if not settings.ready_for_issue:
            return JsonResponse({"ok": False, "error": "tax_data_missing"}, status=409)
        if not all([invoice.customer_street, invoice.customer_postal_code, invoice.customer_city]):
            return JsonResponse({"ok": False, "error": "customer_address_missing"}, status=409)
        if not invoice.items.exists():
            return JsonResponse({"ok": False, "error": "invoice_items_missing"}, status=409)

        today = timezone.localdate()
        invoice.number = f"{settings.invoice_prefix}{today.year}-{settings.next_sequence:04d}"
        settings.next_sequence += 1
        settings.save(update_fields=["next_sequence", "updated_at"])
        invoice.status = "issued"
        invoice.issued_on = today
        invoice.issued_at = timezone.now()
        invoice.save(update_fields=["number", "status", "issued_on", "issued_at"])

        pdf_bytes = _invoice_pdf_bytes(invoice, settings)
        document = SecureDocument.objects.create(
            user=invoice.user,
            title=f"Rechnung {invoice.number}",
            category="invoice",
            uploaded_by=actor,
        )
        document.file.save(f"{invoice.number}.pdf", ContentFile(pdf_bytes), save=True)
        invoice.document = document
        invoice.save(update_fields=["document"])

        AuditLog.objects.create(
            actor=actor,
            action="Mobile Rechnung ausgestellt",
            entity_type="Invoice",
            entity_id=str(invoice.pk),
            metadata={"channel": "admin_app", "number": invoice.number, "total_cents": invoice.total_cents},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    return JsonResponse({"ok": True, "invoice": _invoice_payload(invoice)})
