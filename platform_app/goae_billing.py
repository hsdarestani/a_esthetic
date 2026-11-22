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
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from .models import Invoice, InvoiceItem, UserProfile
from .goae_tariff import CATALOG, POINT_VALUE_EUR


def to_decimal(value):
    try:
        parsed = Decimal(str(value or "").strip().replace(",", "."))
    except (ValueError, InvalidOperation):
        raise ValueError("Ungültiger Geldbetrag oder Faktor.")
    if not parsed.is_finite():
        raise ValueError("Ungültiger Geldbetrag oder Faktor.")
    return parsed


# GOÄ § 5 ordinary ranges. These categories must be assigned by an
# authorized reviewer against the official tariff schedule, never inferred
# from the marketing treatment name. Deviating § 2 agreements are not supported.
FEE_RANGES = {
    "general": (Decimal("2.30"), Decimal("3.50")),
    "technical": (Decimal("1.80"), Decimal("2.50")),
    "laboratory": (Decimal("1.15"), Decimal("1.30")),
}


def cents(amount):
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_goae_lines(data):
    rows = data.get("lines")
    if rows is None:
        rows = [data]  # existing Office one-line form
    if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
        raise ValueError("Bitte eine bis 50 Rechnungspositionen angeben.")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Ungültige Rechnungsposition.")
        if row.get("kind") == "material":
            desc = str(row.get("goae_description") or "").strip()
            evidence = str(row.get("material_receipt_reference") or "").strip()
            confirmation = row.get("material_eligible") is True
            if not confirmation or not 4 <= len(desc) <= 220 or not 1 <= len(evidence) <= 250:
                raise ValueError("Auslage nur mit bestätigter Berechnungsfähigkeit und Beleg erfassen.")
            # §10: exact eligible expenditure, no markup or flat-rate material fee.
            cost = to_decimal(row.get("goae_base_eur"))
            if not Decimal("0") < cost <= Decimal("100000") or cost != cost.quantize(Decimal(".01")):
                raise ValueError("Tatsächlichen Einzelpreis in Euro angeben.")
            quantity = to_decimal(row.get("quantity", "1"))
            if not 1 <= quantity <= 100 or quantity != quantity.to_integral_value():
                raise ValueError("Ungültige Anzahl.")
            if row.get("goae_vat_rate") is None or not str(row.get("goae_vat_rate")).strip():
                raise ValueError("Umsatzsteuerstatus muss ausdrücklich ausgewählt werden.")
            vat = to_decimal(row.get("goae_vat_rate"))
            if vat not in {Decimal("0"), Decimal("7"), Decimal("19")}:
                raise ValueError("Umsatzsteuerstatus bitte prüfen.")
            net = cents(cost) * int(quantity)
            tax = int((Decimal(net) * vat / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            result.append(dict(description=desc, goae_number="", goae_factor=None,
                goae_base_cents=None, goae_justification="Auslage (§ 10), Beleg: "+evidence,
                quantity=quantity, unit_gross_cents=cents(cost * (1 + vat/100)),
                vat_rate=vat, net_cents=net, tax_cents=tax, gross_cents=net+tax))
            continue
        code = str(row.get("goae_number") or "").strip()
        desc = str(row.get("goae_description") or "").strip()
        reason = str(row.get("goae_justification") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9 ./-]{1,24}", code) or len(desc) > 220 or (row.get("tariff_source") != "official_catalog" and len(desc) < 4) or len(reason) > 1500:
            raise ValueError("GOÄ Nummer und Leistungsbeschreibung sind erforderlich.")
        verified = row.get("tariff_source") == "official_catalog"
        if verified:
            tariff = CATALOG.get(code)
            if not tariff or row.get("clinical_confirmed") is not True:
                raise ValueError("Amtliche Ziffer und tatsächlich erbrachte Leistung bestätigen.")
            # § 6(2)/§ 12(4): an analogous service requires an independently
            # documented description and a physician-reviewed equivalence.
            if row.get("analog") is True:
                if row.get("analog_confirmed") is not True or len(desc) < 4:
                    raise ValueError("Analoge Leistung ärztlich bestätigen.")
                desc = desc + " – entsprechend GOÄ Nr. " + code + ": " + tariff["de"]
                if len(desc) > 220:
                    raise ValueError("Analogleistung bitte kürzer beschreiben.")
                code += " A"
            else:
                desc = tariff["de"]
            category = tariff["category"]
        else:
            category = row.get("goae_category", "general")
        if code.split()[0] in {"250", "250a"}:
            category = "technical"  # explicitly listed in Anlage A, even for manual drafts
        if category not in FEE_RANGES:
            raise ValueError("Bitte die Gebührenkategorie prüfen.")
        threshold, maximum = FEE_RANGES[category]
        factor = to_decimal(row.get("goae_factor"))
        if not Decimal("1") <= factor <= maximum or factor != factor.quantize(Decimal(".01")):
            raise ValueError("Steigerungsfaktor außerhalb des zulässigen Gebührenrahmens.")
        if factor > threshold and not reason:
            raise ValueError("Ein erhöhter Steigerungsfaktor braucht eine individuelle Begründung.")
        points_value = row.get("goae_points")
        if verified:
            base = Decimal(tariff["points"]) * POINT_VALUE_EUR
        elif points_value is not None and str(points_value).strip():
            points = to_decimal(points_value)
            if not 1 <= points <= 100000 or points != points.to_integral_value():
                raise ValueError("Ungültige Punktzahl.")
            base = points * POINT_VALUE_EUR
        else:
            base = to_decimal(row.get("goae_base_eur"))
        if not Decimal("0") < base <= Decimal("100000"):
            raise ValueError("Den GOÄ Einfachsatz bitte prüfen.")
        quantity = to_decimal(row.get("quantity", "1"))
        if not 1 <= quantity <= 100 or quantity != quantity.to_integral_value():
            raise ValueError("Die Anzahl muss eine positive ganze Zahl sein.")
        vat_value = row.get("goae_vat_rate")
        if vat_value is None or str(vat_value).strip() == "":
            raise ValueError("Umsatzsteuerstatus muss ausdrücklich ausgewählt werden.")
        vat = to_decimal(vat_value)
        if vat not in {Decimal("0"), Decimal("7"), Decimal("19")}:
            raise ValueError("Umsatzsteuerstatus bitte prüfen.")
        # Round the individual fee before multiplying quantity; apply VAT to
        # the net fee (do not silently derive a smaller fee from a gross price).
        unit_net = cents(base * factor)
        net = unit_net * int(quantity)
        tax = int((Decimal(net) * vat / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        gross = net + tax
        result.append(dict(
            description=desc, goae_number=code, goae_factor=factor,
            goae_base_cents=cents(base), goae_justification=reason,
            quantity=quantity, unit_gross_cents=cents(Decimal(unit_net) / 100 * (1 + vat / 100)),
            vat_rate=vat, net_cents=net, tax_cents=tax, gross_cents=gross,
        ))
    if sum(row['gross_cents'] for row in result) > 2147483647:
        raise ValueError("Rechnungsbetrag außerhalb des zulässigen Bereichs.")
    return result


def create_goae_draft(*, user, actor, service_date, data):
    items = calculate_goae_lines(data)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    with transaction.atomic():
        invoice = Invoice.objects.create(
            user=user, billing_method="goae", service_date=service_date,
            customer_name=user.get_full_name() or user.email,
            customer_email=user.email,
            customer_street=profile.street, customer_postal_code=profile.postal_code,
            customer_city=profile.city,
            subtotal_cents=sum(row["net_cents"] for row in items),
            tax_cents=sum(row["tax_cents"] for row in items),
            total_cents=sum(row["gross_cents"] for row in items),
            created_by=actor,
        )
        InvoiceItem.objects.bulk_create([InvoiceItem(invoice=invoice, **item) for item in items])
    return invoice


def goae_draft_pdf_bytes(invoice, settings, *, simulation=False):
    """Paginated non-final draft; clinical tariff and issuer review still required."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=44, rightMargin=44,
                            topMargin=44, bottomMargin=54)
    styles = getSampleStyleSheet()
    def para(value, style="BodyText"):
        return Paragraph(escape(str(value or "")), styles[style])

    story = [
        para("Privatpraxis Ariane Regaei", "Title"),
        para("Stiftstrasse 14 · 60313 Frankfurt am Main"),
        Spacer(1, 18),
        para("TESTRECHNUNG – NICHT ZAHLBAR" if simulation else "Rechnung nach GOÄ – ENTWURF", "Heading2"),
        para(invoice.number if simulation else ""),
        para(invoice.customer_name),
        para(invoice.customer_street),
        para(f"{invoice.customer_postal_code} {invoice.customer_city}".strip()),
        Spacer(1, 12),
        para(f"Leistungsdatum: {invoice.service_date:%d.%m.%Y}"),
        Spacer(1, 12),
    ]
    money = lambda amount: f"{Decimal(amount)/100:.2f} EUR"
    rows = [[para(x) for x in ("GOÄ Nr.", "Leistung", "Anzahl", "Faktor", "Netto / USt")]]
    for item in invoice.items.all():
        desc = para(item.description)
        if item.goae_justification:
            desc = [desc, para("Begründung: " + item.goae_justification)]
        rows.append([para(item.goae_number or "Auslage"), desc, para(item.quantity),
                     para(item.goae_factor or "-"),
                     [para(money(item.net_cents)), para(f"USt {item.vat_rate}%: {money(item.tax_cents)}")]])
    table = Table(rows, colWidths=[62, 180, 46, 44, 171], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaece6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#31463e")),
        ("LINEBELOW", (0, 1), (-1, -1), .3, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 14),
        para(f"Netto: {money(invoice.subtotal_cents)}"),
        para(f"Umsatzsteuer: {money(invoice.tax_cents)}"),
        para(f"Gesamt: {money(invoice.total_cents)}", "Heading2"),
        para("Nicht zur Zahlung verwenden. Ärztliche und steuerliche Freigabe ausstehend."),
    ])

    def footer(pdf, document):
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(colors.HexColor("#7f3c36"))
        pdf.drawString(44, 32, "ENTWURF – NICHT ZUR ZAHLUNG")
        pdf.drawRightString(A4[0] - 44, 32, f"Seite {document.page}")
        pdf.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
