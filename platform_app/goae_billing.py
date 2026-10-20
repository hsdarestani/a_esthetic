"""Physician-reviewed GOÄ invoice drafts.

No official GOÄ tariff mapping is inferred from a service price: the practice
must enter and check the fee number, base amount, factor and VAT classification.
Final GOÄ issuance remains disabled pending the approved invoice template.
"""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO

from django.db import transaction
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import Invoice, InvoiceItem, UserProfile


def to_decimal(value):
    try:
        return Decimal(str(value or "").strip().replace(",", "."))
    except (ValueError, InvalidOperation):
        raise ValueError("Ungültiger Geldbetrag oder Faktor.")


def create_goae_draft(*, user, actor, service_date, data):
    code = str(data.get("goae_number") or "").strip()[:24]
    desc = str(data.get("goae_description") or "").strip()[:220]
    reason = str(data.get("goae_justification") or "").strip()[:1500]
    if not re.fullmatch(r"[A-Za-z0-9 ./-]{1,24}", code) or len(desc) < 4:
        raise ValueError("GOÄ Nummer und Leistungsbeschreibung sind erforderlich.")
    base = to_decimal(data.get("goae_base_eur"))
    factor = to_decimal(data.get("goae_factor"))
    vat_value = data.get("goae_vat_rate")
    if vat_value is None or str(vat_value).strip() == "":
        raise ValueError("Umsatzsteuerstatus muss ausdrücklich ausgewählt werden.")
    vat = to_decimal(vat_value)
    if not (Decimal("0") < base <= Decimal("100000")):
        raise ValueError("Den GOÄ Einfachsatz bitte prüfen.")
    if not (Decimal("1.00") <= factor <= Decimal("10.00")):
        raise ValueError("Steigerungsfaktor bitte prüfen.")
    if vat not in {Decimal("0"), Decimal("7"), Decimal("19")}:
        raise ValueError("Umsatzsteuerstatus bitte prüfen.")
    if factor > Decimal("2.30") and not reason:
        raise ValueError("Ein erhöhter Steigerungsfaktor braucht eine individuelle Begründung.")
    gross = int((base * factor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    net = int((Decimal(gross) / (Decimal("1") + vat/100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))
    profile, _ = UserProfile.objects.get_or_create(user=user)
    with transaction.atomic():
        invoice = Invoice.objects.create(
            user=user, billing_method="goae", service_date=service_date,
            customer_name=user.get_full_name() or user.email,
            customer_email=user.email,
            customer_street=profile.street, customer_postal_code=profile.postal_code,
            customer_city=profile.city, subtotal_cents=net,
            tax_cents=gross-net, total_cents=gross, created_by=actor,
        )
        InvoiceItem.objects.create(
            invoice=invoice, service=None, description=desc,
            goae_number=code, goae_factor=factor,
            goae_base_cents=int((base * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
            goae_justification=reason, unit_gross_cents=gross,
            vat_rate=vat, net_cents=net, tax_cents=gross-net, gross_cents=gross,
        )
    return invoice


def goae_draft_pdf_bytes(invoice, settings):
    """Non-final draft only, with physician issuer and no A+ branding."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    x, y = 48, h-60
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(x, y, "Privatpraxis Ariane Regaei")
    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(x, y, "Stiftstrasse 14")
    y -= 14
    pdf.drawString(x, y, "60313 Frankfurt am Main")
    y -= 48
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(x, y, "Rechnung nach GOÄ - ENTWURF")
    y -= 26
    pdf.setFont("Helvetica", 10)
    for text_line in (invoice.customer_name, invoice.customer_street,
                      f"{invoice.customer_postal_code} {invoice.customer_city}".strip(),
                      f"Leistungsdatum: {invoice.service_date:%d.%m.%Y}"):
        if text_line:
            pdf.drawString(x, y, str(text_line)[:83])
            y -= 16
    y -= 20
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x, y, "GOÄ Nr.")
    pdf.drawString(x+80, y, "Leistung")
    pdf.drawRightString(w-170, y, "Faktor")
    pdf.drawRightString(w-48, y, "Betrag")
    y -= 10
    pdf.line(x, y, w-48, y)
    y -= 19
    pdf.setFont("Helvetica", 9)
    for item in invoice.items.all():
        pdf.drawString(x, y, str(item.goae_number)[:22])
        pdf.drawString(x+80, y, str(item.description)[:38])
        pdf.drawRightString(w-170, y, str(item.goae_factor or "-"))
        pdf.drawRightString(w-48, y, f"{Decimal(item.gross_cents)/100:.2f} EUR")
        y -= 18
        if item.goae_justification:
            pdf.setFont("Helvetica-Oblique", 8)
            pdf.drawString(x+80, y, ("Begründung: "+item.goae_justification)[:80])
            pdf.setFont("Helvetica", 9)
            y -= 18
    y -= 9
    pdf.line(x, y, w-48, y)
    y -= 20
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(w-48, y, f"Gesamt: {Decimal(invoice.total_cents)/100:.2f} EUR")
    y -= 27
    pdf.setFont("Helvetica", 9)
    pdf.drawString(x, y, "GOÄ Gebührennummer, Einfachsatz und Umsatzsteuer ärztlich prüfen.")
    y -= 15
    pdf.drawString(x, y, "Nicht zur Zahlung verwenden. Ärztliche Freigabe noch ausstehend.")
    pdf.saveState()
    pdf.setFillGray(0.86)
    pdf.setFont("Helvetica-Bold", 52)
    pdf.translate(w/2, h/2)
    pdf.rotate(30)
    pdf.drawCentredString(0, 0, "ENTWURF")
    pdf.restoreState()
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
