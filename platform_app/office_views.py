import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from urllib.parse import urlencode

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import models, transaction
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


def _office_settings_allowed(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = UserProfile.objects.filter(user=user).only("role").first()
    return bool(user.is_staff and (not profile or profile.role in {"admin", "manager"})) or bool(
        profile and profile.role in {"admin", "manager"}
    )


def _office_login_redirect(request):
    next_path = request.get_full_path()
    return redirect(f"/office/admin/login/?{urlencode({'next': next_path})}")


@require_http_methods(["GET", "POST"])
def office_staff_login(request):
    if _office_allowed(request.user):
        return redirect("office_dashboard")

    error = ""
    next_path = (request.GET.get("next") or request.POST.get("next") or "/office/admin/").strip()
    if not next_path.startswith("/office/"):
        next_path = "/office/admin/"

    if request.method == "POST":
        identifier = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        username = identifier
        if "@" in identifier:
            match = User.objects.filter(email__iexact=identifier).order_by("pk").first()
            if match:
                username = match.username

        user = authenticate(request, username=username, password=password)
        if not user or not user.is_active:
            error = "E Mail Adresse oder Passwort ist nicht korrekt."
        elif not _office_allowed(user):
            error = "Dieses Konto hat keinen Zugriff auf A+ Esthetic Office."
        else:
            auth_login(request, user)
            AuditLog.objects.create(
                actor=user,
                action="Office Login",
                entity_type="AdminAccount",
                entity_id=str(user.pk),
                metadata={"channel": "office_web"},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            return redirect(next_path)

    response = render(request, "office/staff_login.html", {"error": error, "next": next_path})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@require_POST
def office_staff_logout(request):
    if request.user.is_authenticated:
        auth_logout(request)
    return redirect("office_staff_login")


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


def _parse_service_date(value):
    raw = str(value or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return timezone.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_eur_cents(value):
    raw = str(value or "").strip().replace("€", "").replace("EUR", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("invalid_price") from exc
    if amount < 0:
        raise ValueError("invalid_price")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _format_eur_input(cents):
    if cents is None:
        return ""
    return f"{Decimal(cents) / Decimal(100):.2f}".replace(".", ",")


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


@require_http_methods(["GET", "POST"])
def office_public_intake(request):
    """Public iPad intake surface. No Customer Club login is required."""
    error = ""
    if request.method == "POST":
        # Invisible honeypot for basic bot protection.
        if (request.POST.get("website") or "").strip():
            response = render(request, "office/checkin.html", {"completed": True, "public_intake": True})
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            return response

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
                if user:
                    existing_profile = UserProfile.objects.filter(user=user).first()
                    if user.is_staff or user.is_superuser or (existing_profile and existing_profile.role in OFFICE_ROLES):
                        error = "Diese Daten können hier nicht als Kundenkonto verwendet werden. Bitte den Empfang informieren."
                if not error:
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
                    AuditLog.objects.create(
                        actor=None,
                        action="iPad Kundenaufnahme abgeschlossen",
                        entity_type="User",
                        entity_id=str(user.pk),
                        metadata={"created": created, "member_number": member.member_number, "source": "office_public_ipad"},
                        ip_address=request.META.get("REMOTE_ADDR"),
                    )
                    response = render(request, "office/checkin.html", {
                        "completed": True,
                        "public_intake": True,
                        "member_number": member.member_number,
                    })
                    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
                    return response

    response = render(request, "office/checkin.html", {"error": error, "public_intake": True})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@require_http_methods(["GET", "POST"])
def office_dashboard(request):
    if not request.user.is_authenticated:
        return _office_login_redirect(request)
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
            service_date = _parse_service_date(request.POST.get("service_date"))
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
def office_settings(request):
    if not request.user.is_authenticated:
        return _office_login_redirect(request)
    if not _office_settings_allowed(request.user):
        return HttpResponseForbidden("Kein Zugriff.")

    settings, _ = InvoiceSettings.objects.get_or_create(pk=1)
    services = list(Service.objects.filter(active=True).order_by("name"))
    error = ""
    notice = ""

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "invoice_settings":
            invoice_prefix = (request.POST.get("invoice_prefix") or "RE").strip()[:20] or "RE"
            try:
                next_sequence = int(request.POST.get("next_sequence") or "1")
                if next_sequence < 1:
                    raise ValueError
            except ValueError:
                error = "Die nächste Rechnungsnummer muss eine positive Zahl sein."
            if not error:
                settings.company_name = (request.POST.get("company_name") or settings.company_name).strip()[:180]
                settings.street = (request.POST.get("street") or settings.street).strip()[:180]
                settings.postal_code = (request.POST.get("postal_code") or settings.postal_code).strip()[:20]
                settings.city = (request.POST.get("city") or settings.city).strip()[:120]
                settings.email = (request.POST.get("email") or settings.email).strip()[:254]
                settings.phone = (request.POST.get("phone") or settings.phone).strip()[:40]
                settings.tax_number = (request.POST.get("tax_number") or "").strip()[:80]
                settings.vat_id = (request.POST.get("vat_id") or "").strip()[:80]
                settings.iban = (request.POST.get("iban") or "").strip().replace(" ", "")[:64]
                settings.bic = (request.POST.get("bic") or "").strip().upper()[:32]
                settings.bank_name = (request.POST.get("bank_name") or "").strip()[:120]
                settings.invoice_prefix = invoice_prefix
                settings.next_sequence = next_sequence
                settings.save()
                AuditLog.objects.create(
                    actor=request.user,
                    action="Rechnungseinstellungen geändert",
                    entity_type="InvoiceSettings",
                    entity_id=str(settings.pk),
                    metadata={"invoice_prefix": settings.invoice_prefix, "next_sequence": settings.next_sequence},
                    ip_address=request.META.get("REMOTE_ADDR"),
                )
                notice = "Rechnungseinstellungen wurden gespeichert."

        elif action == "service_prices":
            parsed = []
            for service in services:
                price_raw = request.POST.get(f"service_{service.pk}_price", "")
                vat_raw = request.POST.get(f"service_{service.pk}_vat", "")
                try:
                    cents = _parse_eur_cents(price_raw)
                    vat = Decimal(str(vat_raw).strip().replace(",", ".")) if str(vat_raw).strip() else None
                except (ValueError, InvalidOperation):
                    error = f"Preis oder MwSt für „{service.name}“ ist ungültig."
                    break
                if cents is None or vat is None:
                    error = f"Bitte Preis und MwSt für „{service.name}“ vollständig eintragen."
                    break
                if vat < 0 or vat > 100:
                    error = f"Die MwSt für „{service.name}“ muss zwischen 0 und 100 liegen."
                    break
                parsed.append((service, cents, vat))

            if not error:
                with transaction.atomic():
                    for service, cents, vat in parsed:
                        service.price_cents = cents
                        service.vat_rate = vat
                        service.price_label = f"{_format_eur_input(cents)} €"
                        service.save(update_fields=["price_cents", "vat_rate", "price_label"])
                    AuditLog.objects.create(
                        actor=request.user,
                        action="Behandlungspreise geändert",
                        entity_type="Service",
                        entity_id="bulk",
                        metadata={"services": len(parsed)},
                        ip_address=request.META.get("REMOTE_ADDR"),
                    )
                notice = "Preise und MwSt wurden gespeichert."
                services = list(Service.objects.filter(active=True).order_by("name"))

    service_rows = [
        {
            "service": service,
            "price_input": _format_eur_input(service.price_cents),
            "vat_input": "" if service.vat_rate is None else str(service.vat_rate).replace(".", ","),
            "configured": service.price_cents is not None and service.vat_rate is not None,
        }
        for service in services
    ]
    return render(request, "office/settings.html", {
        "invoice_settings": settings,
        "service_rows": service_rows,
        "error": error,
        "notice": notice,
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


def office_invoice_detail(request, invoice_id):
    if not request.user.is_authenticated:
        return _office_login_redirect(request)
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


@require_POST
def office_invoice_finalize(request, invoice_id):
    if not request.user.is_authenticated:
        return _office_login_redirect(request)
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


def office_invoice_pdf(request, invoice_id):
    if not request.user.is_authenticated:
        return _office_login_redirect(request)
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
