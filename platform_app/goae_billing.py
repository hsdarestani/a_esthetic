"""Physician-reviewed GOÄ invoice drafts.

No official GOÄ tariff mapping is inferred from a service price: the practice
must enter and check the fee number, base amount, factor and VAT classification.
Final GOÄ issuance remains disabled pending the approved invoice template.
"""
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from io import BytesIO
from uuid import UUID

from django.db import transaction
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from xml.sax.saxutils import escape

from .models import Invoice, InvoiceItem, UserProfile, SecureDocument
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
# from the marketing treatment name. Deviating § 2 agreements require separate evidence.
FEE_RANGES = {
    "general": (Decimal("2.30"), Decimal("3.50")),
    "technical": (Decimal("1.80"), Decimal("2.50")),
    "laboratory": (Decimal("1.15"), Decimal("1.30")),
}


def cents(amount):
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _agreement_evidence(row, *, user, service_date, category, verified):
    # Only the specifically reviewed general official codes in the current
    # catalogue are eligible here. Technical/laboratory and analog exceptions
    # must not be unlocked by a browser-provided category.
    if category != "general" or not verified or row.get("analog") is True:
        raise ValueError("Abweichende Vereinbarung für diese Leistung nicht freigegeben.")
    if row.get("agreement_confirmed") is not True or user is None or service_date is None:
        raise ValueError("Schriftliche Honorarvereinbarung vor der Behandlung bestätigen.")
    try:
        signed_on = date.fromisoformat(str(row.get("agreement_date") or ""))
        raw_id = str(row.get("agreement_document_id") or "")
        if not re.fullmatch(r"[1-9][0-9]{0,17}", raw_id):
            raise ValueError
        document_id = int(raw_id)
    except (ValueError, TypeError):
        raise ValueError("Datum und Dokument-ID der Honorarvereinbarung erforderlich.")
    if signed_on > service_date or signed_on > date.today():
        raise ValueError("Die Vereinbarung muss vor der Behandlung getroffen worden sein.")
    if not SecureDocument.objects.filter(pk=document_id, user=user, category__in=["medical", "consent"]).exclude(file="").exists():
        raise ValueError("Unterzeichnetes Dokument in der Patientenakte nicht gefunden.")
    return document_id, signed_on


def calculate_goae_lines(data, *, user=None, service_date=None):
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
        if not Decimal("1") <= factor <= Decimal("99.9999") or factor != factor.quantize(Decimal(".0001")):
            raise ValueError("Ungültiger Steigerungsfaktor (maximal vier Nachkommastellen).")
        agreement = None
        if factor > maximum:
            agreement = _agreement_evidence(row, user=user, service_date=service_date,
                                            category=category, verified=verified)
        elif factor > threshold and not reason:
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
        if agreement:
            agreed = to_decimal(row.get("agreement_amount_eur"))
            if agreed != agreed.quantize(Decimal(".01")) or cents(agreed) != net:
                raise ValueError("Vereinbarter Nettobetrag und tatsächliche Gebührenposition stimmen nicht überein.")
        tax = int((Decimal(net) * vat / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        gross = net + tax
        result.append(dict(
            description=desc, goae_number=code, goae_factor=factor,
            goae_base_cents=cents(base), goae_justification=reason,
            quantity=quantity, unit_gross_cents=cents(Decimal(unit_net) / 100 * (1 + vat / 100)),
            vat_rate=vat, net_cents=net, tax_cents=tax, gross_cents=gross,
            **({'goae_agreement_document_id': agreement[0], 'goae_agreement_date': agreement[1]} if agreement else {}),
        ))
    # Round VAT once per tax rate on the complete net taxable amount,
    # then distribute exact cent shares by largest remainder. Never force
    # VAT to match a requested retail amount.
    for rate in {item["vat_rate"] for item in result}:
        group = [item for item in result if item["vat_rate"] == rate]
        target_tax = int((sum(item["net_cents"] for item in group) * rate / 100)
                         .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        raw = [Decimal(item["net_cents"]) * rate / 100 for item in group]
        shares = [int(value) for value in raw]
        remainder = target_tax - sum(shares)
        order = sorted(range(len(group)), key=lambda i: (raw[i] - shares[i], -i), reverse=True)
        for i in order[:remainder]:
            shares[i] += 1
        for item, share in zip(group, shares):
            item["tax_cents"] = share
            item["gross_cents"] = item["net_cents"] + share
    if sum(row['gross_cents'] for row in result) > 2147483647:
        raise ValueError("Rechnungsbetrag außerhalb des zulässigen Bereichs.")
    return result


def _check_draft_request(invoice, *, user, actor, digest):
    if (invoice.user_id, invoice.created_by_id, invoice.draft_request_digest) != (user.pk, actor.pk, digest):
        raise ValueError("Diese Entwurfsanfrage wurde bereits mit anderen Angaben verwendet.")
    return invoice


def _book_preview_details(data):
    """Optional draft-only presentation values shared by export and save."""
    values = data.get('book_preview')
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise ValueError('Ungültige Vorschauangaben.')
    result = {}
    for key in ('invoice_date', 'due_date'):
        value = values.get(key)
        if value:
            result[key] = date.fromisoformat(str(value)).isoformat()
    diagnosis = values.get('diagnosis', '')
    if not isinstance(diagnosis, str) or len(diagnosis) > 500:
        raise ValueError('Ungültiger Behandlungsanlass.')
    if diagnosis.strip():
        result['diagnosis'] = diagnosis.strip()
    return result


def _prepare_goae_invoice(*, user, actor, service_date, data, create_profile=False):
    items = calculate_goae_lines(data, user=user, service_date=service_date)
    target = data.get('target_total_cents')
    total = sum(row['gross_cents'] for row in items)
    if target is not None:
        target = to_decimal(target)
        if target != target.to_integral_value() or target != total:
            raise ValueError('Wunschbetrag und serverseitig berechnete Rechnung stimmen nicht centgenau überein.')
    preview = _book_preview_details(data)
    profile = UserProfile.objects.get_or_create(user=user)[0] if create_profile else user.profile
    fields = dict(user=user, billing_method='goae', service_date=service_date,
                  customer_name=user.get_full_name() or user.email, customer_email=user.email,
                  customer_street=profile.street, customer_postal_code=profile.postal_code,
                  customer_city=profile.city, subtotal_cents=sum(row['net_cents'] for row in items),
                  tax_cents=sum(row['tax_cents'] for row in items), total_cents=total, created_by=actor)
    if preview:
        fields['native_draft_data'] = {'book_preview': preview}
    return fields, items


def goae_preview_pdf_bytes(*, user, actor, service_date, data, settings):
    """Render the exact validated draft without writing any invoice or patient row."""
    if data.get('target_total_cents') is None:
        raise ValueError('Bestätigter Gesamtbetrag fehlt.')
    fields, items = _prepare_goae_invoice(user=user, actor=actor, service_date=service_date, data=data)
    invoice = Invoice(**fields)
    return goae_draft_pdf_bytes(invoice, settings, items=[InvoiceItem(**item) for item in items])


def create_goae_draft(*, user, actor, service_date, data):
    request_id = data.get("draft_request_id")
    digest = ""
    if request_id is not None:
        try:
            request_id = UUID(str(request_id))
        except ValueError as exc:
            raise ValueError("Ungültige Entwurfsanfrage.") from exc
        request_data = {key: value for key, value in data.items() if key != "draft_request_id"}
        request_data["service_date"] = service_date.isoformat()
        digest = sha256(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
        existing = Invoice.objects.filter(draft_request_id=request_id).first()
        if existing:
            return _check_draft_request(existing, user=user, actor=actor, digest=digest)
    fields, items = _prepare_goae_invoice(user=user, actor=actor, service_date=service_date, data=data, create_profile=True)
    fields['draft_request_digest'] = digest
    with transaction.atomic():
        if request_id is None:
            invoice = Invoice.objects.create(**fields)
        else:
            invoice, created = Invoice.objects.get_or_create(draft_request_id=request_id, defaults=fields)
            if not created:
                return _check_draft_request(invoice, user=user, actor=actor, digest=digest)
        InvoiceItem.objects.bulk_create([InvoiceItem(invoice=invoice, **item) for item in items])
    return invoice


def goae_draft_pdf_bytes(invoice, settings, *, simulation=False, items=None):
    """Paginated non-final draft; clinical tariff and issuer review still required."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=44, rightMargin=44,
                            topMargin=44, bottomMargin=54)
    styles = getSampleStyleSheet()
    styles['BodyText'].fontSize = 9
    styles['BodyText'].leading = 12
    draft = invoice.status == 'draft'
    preview = (invoice.native_draft_data or {}).get('book_preview', {}) if draft else {}
    if not isinstance(preview, dict):
        preview = {}
    def para(value, style="BodyText"):
        return Paragraph(escape(str(value or "")), styles[style])

    story = [
        para(settings.company_name, "Title"),
        para(f"{settings.street} · {settings.postal_code} {settings.city}"),
        para(' · '.join(filter(None, [settings.email, settings.phone]))),
        para(' · '.join(filter(None, ['Steuernummer: ' + settings.tax_number if settings.tax_number else '', 'USt-IdNr.: ' + settings.vat_id if settings.vat_id else '']))),
        Spacer(1, 10),
        para("TESTRECHNUNG – NICHT ZAHLBAR" if simulation else ("Rechnung nach GOÄ – ENTWURF" if draft else "Rechnung nach GOÄ"), "Heading2"),
        para(f"Rechnungsnummer: {invoice.number}" if invoice.number else ""),
        para(invoice.customer_name),
        para(invoice.customer_street),
        para(f"{invoice.customer_postal_code} {invoice.customer_city}".strip()),
        Spacer(1, 8),
        para(f"Leistungsdatum: {invoice.service_date:%d.%m.%Y}"),
    ]
    if invoice.issued_on and not draft:
        story.append(para(f"Rechnungsdatum: {invoice.issued_on:%d.%m.%Y}"))
    for key, label in [('invoice_date', 'Rechnungsdatum (Vorschau)'), ('due_date', 'Fälligkeit (Vorschau)')]:
        if preview.get(key):
            try:
                story.append(para(f"{label}: {date.fromisoformat(preview[key]):%d.%m.%Y}"))
            except (ValueError, TypeError):
                pass
    if preview.get('diagnosis'):
        story.append(para('Behandlungsanlass: ' + str(preview['diagnosis'])))
    story.append(Spacer(1, 9))
    money = lambda amount: f"{Decimal(amount)/100:.2f}".replace('.', ',') + ' EUR'
    number = lambda value: format(Decimal(str(value)).normalize(), 'f').replace('.', ',')
    rows = [[para(x) for x in ("GOÄ Nr.", "Leistung", "Anzahl", "Faktor", "Netto / USt")]]
    positions = list(invoice.items.all() if items is None else items)
    for item in positions:
        desc = para(item.description)
        if item.goae_justification:
            desc = [desc, para("Begründung: " + item.goae_justification)]
        if item.goae_agreement_document_id:
            desc = (desc if isinstance(desc, list) else [desc]) + [para("Honorarvereinbarung nach § 2 GOÄ dokumentiert")]
        rows.append([para(item.goae_number or "Auslage"), desc, para(number(item.quantity)),
                     para(number(item.goae_factor) if item.goae_factor is not None else "–"),
                     [para(money(item.net_cents)), para(f"USt {item.vat_rate}%: {money(item.tax_cents)}")]])
    table = Table(rows, colWidths=[62, 180, 46, 44, 171], repeatRows=1, splitInRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaece6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#31463e")),
        ("LINEBELOW", (0, 1), (-1, -1), .3, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 14), KeepTogether([
        para(f"Ärztliche Leistungen: {money(sum(item.net_cents for item in positions if item.goae_number))}"),
        para(f"Material / Auslagen: {money(sum(item.net_cents for item in positions if not item.goae_number))}"),
        para(f"Netto: {money(invoice.subtotal_cents)}"),
        para(f"Umsatzsteuer: {money(invoice.tax_cents)}"),
        para(f"Gesamt: {money(invoice.total_cents)}", "Heading2"),
    ] + ([para("Nicht zur Zahlung verwenden. Ärztliche und steuerliche Freigabe ausstehend.")] if draft or simulation else []))])

    def footer(pdf, document):
        pdf.saveState()
        if draft:
            pdf.saveState()
            pdf.setFont('Helvetica-Bold', 64)
            pdf.setFillColor(colors.HexColor('#efefef'))
            pdf.translate(A4[0] / 2, A4[1] / 2)
            pdf.rotate(35)
            pdf.drawCentredString(0, 0, 'ENTWURF')
            pdf.restoreState()
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(colors.HexColor("#7f3c36"))
        if draft:
            pdf.drawString(44, 32, "ENTWURF – NICHT ZUR ZAHLUNG")
        elif simulation:
            pdf.drawString(44, 32, "TESTRECHNUNG – NICHT ZAHLBAR")
        pdf.drawRightString(A4[0] - 44, 32, f"Seite {document.page}")
        pdf.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
