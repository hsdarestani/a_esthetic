"""Small verified GOÄ reference catalog: numbers are not treatment prescriptions.

Source: https://www.gesetze-im-internet.de/go__1982/anlage.html
Ordinary limits: §5 and section A of the official schedule.
Treatment associations from the supplied calculator are review prompts only:
no procedures, quantities, expenses, diagnoses or fee factors are inferred.
"""
from decimal import Decimal, ROUND_HALF_UP

POINT_VALUE_EUR = Decimal("0.0582873")
CATALOG = {
    "1": {"points": 80, "category": "general", "de": "Beratung, auch telefonisch", "en": "Consultation, including by telephone"},
    "5": {"points": 80, "category": "general", "de": "Symptombezogene Untersuchung", "en": "Symptom-related examination"},
    "250": {"points": 40, "category": "technical", "de": "Venöse Blutentnahme", "en": "Venous blood collection"},
    "252": {"points": 40, "category": "general", "de": "Subkutane, submuköse, intrakutane oder intramuskuläre Injektion", "en": "Subcutaneous, submucosal, intradermal or intramuscular injection"},
    "268": {"points": 130, "category": "general", "de": "Medikamentöse Infiltration mehrerer Körperregionen, je Sitzung", "en": "Medicinal infiltration of multiple body regions, per session"},
    "2442": {"points": 900, "category": "general", "de": "Selbständige Implantation alloplastischen Materials zur Weichteilunterfütterung", "en": "Independent alloplastic soft-tissue implantation"},
}
TREATMENTS = {
    "botox": ["252", "1", "5"],
    "hyaluron": ["2442", "1", "5"],
    "prp": ["268", "250", "1", "5"],
    "lipolysis": ["252", "1", "5"],
}


def catalog_payload():
    return [{"number": number, **entry} for number, entry in CATALOG.items()]


def reference_case():
    """Reconcile the supplied single synthetic screenshot, not a billing rule.

    It derives the fee residual from a desired gross price. That arithmetic
    is not a validation of the clinical factor, quantities or VAT handling.
    Keep these values separate from the actual forward-calculation engine.
    """
    def rounded(value):
        return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    target = 23600
    materials = 9552
    medical = rounded(Decimal(target) / Decimal("1.19")) - materials
    fixed = 2 * rounded(Decimal(80) * POINT_VALUE_EUR * Decimal("2.3") * 100)
    residual = medical - fixed
    factor = Decimal(residual) / (Decimal(40) * POINT_VALUE_EUR * 100 * 10)
    medical_tax = rounded(Decimal(medical) * Decimal(".19"))
    material_tax = rounded(Decimal(materials) * Decimal(".19"))
    return {
        "target_cents": target, "medical_cents": medical, "material_cents": materials,
        "residual_cents": residual, "derived_factor": str(factor.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)),
        "medical_tax_cents": medical_tax, "material_tax_cents": material_tax,
        "reference_total_cents": medical + materials + medical_tax + material_tax,
        "approval_required": True,
    }
