import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import (
    AuditLog,
    CheckInSession,
    Invoice,
    InvoiceItem,
    InvoiceSettings,
    MemberAccount,
    SecureDocument,
    Service,
    UserProfile,
)


OFFICE_ROLES = {"reception", "specialist", "manager", "admin"}


def _office_allowed(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = UserProfile.objects.filter(user=user).only("role").first()
    return bool(profile and profile.role in OFFICE_ROLES)


def _normalize_phone(value):
    return re.sub(r"\D+", "", str(value or ""))


def _unique_username(email):
    base = (email.split("@", 1)[0] or "kunde")[:120]
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base[:110]}-{suffix}"
    return candidate


def _money(cents):
    return f"{Decimal(cents or 0) / Decimal(100):.2f}"


def _invoice_pdf_bytes(invoice, settings):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 56

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(48, y, "A+ ESTHETIC")
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(width - 48, y, settings.company_name)
    y -= 14
    pdf.drawRightString(width - 48, y, f"{settings.street}, {settings.postal_code} {settings.city}")
    y -= 34

    pdf.setFont("Helvetica-Bold", 16)
    title = f"Rechnung {invoice.number}" if invoice.number else f"Rechnungsentwurf #{invoice.pk}"
    pdf.drawString(48, y, title)
    y -= 28

    pdf.setFont("Helvetica", 10)
    for line in [
        invoice.customer_name,
        invoice.customer_street,
        f"{invoice.customer_postal_code} {invoice.customer_city}".strip(),
        invoice.customer_email,
    ]:
        if line:
            pdf.drawString(48, y, line)
            y -= 14

    y -= 14
    pdf.drawString(48, y, f"Leistungsdatum: {invoice.service_date:%d.%m.%Y}")
    pdf.drawRightString(width - 48, y, f"Rechnungsdatum: {(invoice.issued_on or date.today()):%d.%m.%Y}")
    y -= 30

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(48, y, "Leistung")
    pdf.drawRightString(width - 210, y, "Netto")
    pdf.drawRightString(width - 130, y, "MwSt")
    pdf.drawRightString(width - 48, y, "Brutto")
    y -= 10
    pdf.line(48, y, width - 48, y)
    y -= 18

    pdf.setFont("Helvetica", 9)
    for item in invoice.items.all():
        pdf.drawString(48, y, item.description[:58])
        pdf.drawRightString(width - 210, y, f"{_money(item.net_cents)} EUR")
        pdf.drawRightString(width - 130, y, f"{item.vat_rate}%")
        pdf.drawRightString(width - 48, y, f"{_money(item.gross_cents)} EUR")
        y -= 18

    y -= 8
    pdf.line(width - 250, y, width - 48, y)
    y -= 18
    pdf.drawRightString(width - 130, y, "Netto:")
    pdf.drawRightString(width - 48, y, f"{_money(invoice.subtotal_cents)} EUR")
    y -= 16
    pdf.drawRightString(width - 130, y, "MwSt:")
    pdf.drawRightString(width - 48, y, f"{_money(invoice.tax_cents)} EUR")
    y -= 18
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(width - 130, y, "Gesamt:")
    pdf.drawRightString(width - 48, y, f"{_money(invoice.total_cents)} EUR")

    y -= 52
    pdf.setFont("Helvetica", 8)
    legal = []
    if settings.tax_number:
        legal.append(f"Steuernummer: {settings.tax_number}")
    if settings.vat_id:
        legal.append(f"USt-IdNr.: {settings.vat_id}")
    if settings.iban:
        legal.append(f"IBAN: {settings.iban}")
    if settings.bic:
        legal.append(f"BIC: {settings.bic}")
    if settings.bank_name:
        legal.append(settings.bank_name)
    legal.append(f"{settings.email} · {settings.phone}")
    for line in legal:
        pdf.drawString(48, y, line)
        y -= 12

    if invoice.status == "draft":
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 48)
        pdf.setFillGray(0.88)
        pdf.translate(width / 2, height / 2)
        pdf.rotate(35)
        pdf.drawCentredString(0, 0, "ENTWURF")
        pdf.restoreState()

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@login_required
@require_http_methods(["GET", "POST"])
def office_dashboard(request):
    if not _office_allowed(request.user):
        return HttpResponseForbidden("Kein Zugriff.")

    notice = ""
    error = ""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "new_checkin":
            session = CheckInSession.objects.create(
                created_by=request.user,
                expires_at=timezone.now() + timedelta(minutes=30),
            )
            return redirect("office_checkin", token=session.token)

        if action == "new_invoice":
            customer = User.objects.filter(pk=request.POST.get("customer_id"), is_active=True).first()
            service = Service.objects.filter(pk=request.POST.get("service_id"), active=True).first()
            try:
                service_date = date.fromisoformat(request.POST.get("service_date") or "")
            except ValueError:
                service_date = None
            if not customer or not service or not service_date:
                error = "Kunde, Behandlung und Leistungsdatum sind erforderlich."
            elif service.price_cents is None or service.vat_rate is None:
                error = "Für diese Behandlung fehlen noch Preis oder MwSt."
            else:
                profile, _ = UserProfile.objects.get_or_create(user=customer)
                gross = int(service.price_cents)
                rate = Decimal(service.vat_rate)
                divisor = Decimal("1") + (rate / Decimal("100"))
                net = int((Decimal(gross) / divisor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                tax = gross - net
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
                    created_by=request.user,
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
                    actor=request.user,
                    action="Rechnungsentwurf erstellt",
                    entity_type="Invoice",
                    entity_id=str(invoice.pk),
                    metadata={"service": service.name, "customer_id": customer.pk},
                    ip_address=request.META.get("REMOTE_ADDR"),
                )
                return redirect("office_invoice_detail", invoice_id=invoice.pk)

    query = (request.GET.get("q") or "").strip()
    customers = User.objects.filter(is_active=True, is_superuser=False, profile__role="customer")
    if query:
        customers = customers.filter(
            models.Q(email__icontains=query)
            | models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(profile__phone__icontains=query)
            | models.Q(member_account__member_number__icontains=query)
        )
    customers = customers.select_related("profile", "member_account").order_by("last_name", "first_name")[:250]
    services = Service.objects.filter(active=True).order_by("name")
    invoices = Invoice.objects.select_related("user").order_by("-created_at")[:40]
    settings, _ = InvoiceSettings.objects.get_or_create(pk=1)
    return render(request, "office/dashboard.html", {
        "customers": customers,
        "services": services,
        "invoices": invoices,
        "invoice_settings": settings,
        "notice": notice,
        "error": error,
        "query": query,
    })


@require_http_methods(["GET", "POST"])
def office_checkin(request, token):
    session = get_object_or_404(CheckInSession, token=token)
    if session.completed_at:
        return render(request, "office/checkin.html", {"session": session, "completed": True})
    if session.expires_at <= timezone.now():
        return render(request, "office/checkin.html", {"session": session, "expired": True}, status=410)

    error = ""
    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()[:80]
        last_name = (request.POST.get("last_name") or "").strip()[:80]
        email = (request.POST.get("email") or "").strip().lower()[:254]
        phone = (request.POST.get("phone") or "").strip()[:40]
        salutation = (request.POST.get("salutation") or "").strip().lower()
        street = (request.POST.get("street") or "").strip()[:180]
        postal_code = (request.POST.get("postal_code") or "").strip()[:20]
        city = (request.POST.get("city") or "").strip()[:120]

        if not all([first_name, last_name, email, phone, street, postal_code, city]) or "@" not in email:
            error = "Bitte alle Pflichtfelder vollständig ausfüllen."
        else:
            email_user = User.objects.filter(email__iexact=email).order_by("pk").first()
            phone_user = None
            normalized_phone = _normalize_phone(phone)
            if normalized_phone:
                for profile in UserProfile.objects.exclude(phone="").select_related("user").order_by("pk"):
                    if _normalize_phone(profile.phone) == normalized_phone:
                        phone_user = profile.user
                        break
            if email_user and phone_user and email_user.pk != phone_user.pk:
                error = "E-Mail und Telefonnummer gehören bereits zu unterschiedlichen Kundenkonten. Bitte den Empfang informieren."
            else:
                user = email_user or phone_user
                created = False
                if not user:
                    user = User.objects.create(
                        username=_unique_username(email),
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=True,
                    )
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                    created = True
                else:
                    user.email = email
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save(update_fields=["email", "first_name", "last_name"])

                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.role = "customer"
                profile.phone = phone
                if salutation in {"herr", "frau", "divers"}:
                    profile.salutation = salutation
                profile.street = street
                profile.postal_code = postal_code
                profile.city = city
                profile.country = "DE"
                profile.onboarding_required = created or profile.onboarding_required
                profile.save()

                member, _ = MemberAccount.objects.get_or_create(user=user)
                session.customer = user
                session.completed_at = timezone.now()
                session.save(update_fields=["customer", "completed_at"])
                AuditLog.objects.create(
                    actor=session.created_by,
                    action="iPad Kundenaufnahme abgeschlossen",
                    entity_type="User",
                    entity_id=str(user.pk),
                    metadata={"created": created, "member_number": member.member_number},
                    ip_address=request.META.get("REMOTE_ADDR"),
                )
                return render(request, "office/checkin.html", {
                    "session": session,
                    "completed": True,
                    "member_number": member.member_number,
                })

    return render(request, "office/checkin.html", {"session": session, "error": error})


@login_required
def office_invoice_detail(request, invoice_id):
    if not _office_allowed(request.user):
        return HttpResponseForbidden("Kein Zugriff.")
    invoice = get_object_or_404(Invoice.objects.prefetch_related("items"), pk=invoice_id)
    settings, _ = InvoiceSettings.objects.get_or_create(pk=1)
    missing_address = not all([invoice.customer_street, invoice.customer_postal_code, invoice.customer_city])
    return render(request, "office/invoice_detail.html", {
        "invoice": invoice,
        "invoice_settings": settings,
        "missing_address": missing_address,
    })


@login_required
@require_POST
def office_invoice_finalize(request, invoice_id):
    if not _office_allowed(request.user):
        return HttpResponseForbidden("Kein Zugriff.")
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().prefetch_related("items").get(pk=invoice_id)
        settings, _ = InvoiceSettings.objects.select_for_update().get_or_create(pk=1)
        if invoice.status != "draft":
            return redirect("office_invoice_detail", invoice_id=invoice.pk)
        if not settings.ready_for_issue:
            return HttpResponse("Steuernummer oder USt-IdNr. fehlt in den Rechnungseinstellungen.", status=409)
        if not all([invoice.customer_street, invoice.customer_postal_code, invoice.customer_city]):
            return HttpResponse("Kundenadresse fehlt.", status=409)
        if not invoice.items.exists():
            return HttpResponse("Rechnung hat keine Position.", status=409)

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
            uploaded_by=request.user,
        )
        document.file.save(f"{invoice.number}.pdf", ContentFile(pdf_bytes), save=True)
        invoice.document = document
        invoice.save(update_fields=["document"])
        AuditLog.objects.create(
            actor=request.user,
            action="Rechnung ausgestellt",
            entity_type="Invoice",
            entity_id=str(invoice.pk),
            metadata={"number": invoice.number, "total_cents": invoice.total_cents},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
    return redirect("office_invoice_detail", invoice_id=invoice.pk)


@login_required
def office_invoice_pdf(request, invoice_id):
    if not _office_allowed(request.user):
        return HttpResponseForbidden("Kein Zugriff.")
    invoice = get_object_or_404(Invoice.objects.prefetch_related("items"), pk=invoice_id)
    if invoice.document_id and invoice.document.file:
        response = HttpResponse(invoice.document.file.read(), content_type="application/pdf")
    else:
        settings, _ = InvoiceSettings.objects.get_or_create(pk=1)
        response = HttpResponse(_invoice_pdf_bytes(invoice, settings), content_type="application/pdf")
    filename = invoice.number or f"rechnungsentwurf-{invoice.pk}"
    response["Content-Disposition"] = f'inline; filename="{filename}.pdf"'
    return response
