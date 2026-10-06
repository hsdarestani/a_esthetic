import os
from pathlib import Path

import requests

from .models import Service

BOOK_CUSTOMER_SYNC_URL = os.environ.get(
    "AESTHETIC_BOOK_CUSTOMER_SYNC_URL",
    "https://book.a-esthetic.de/api/internal/customer-sync/",
)
BOOK_BILLING_CATALOG_URL = os.environ.get(
    "AESTHETIC_BOOK_BILLING_CATALOG_URL",
    "https://book.a-esthetic.de/api/internal/billing-catalog/",
)


def _sync_token():
    direct = str(
        os.environ.get("PATIENT_RECORD_SYNC_TOKEN")
        or os.environ.get("PATIENT_SYNC_TOKEN")
        or ""
    ).strip()
    if direct:
        return direct
    token_file = (
        os.environ.get("PATIENT_RECORD_SYNC_TOKEN_FILE")
        or os.environ.get("PATIENT_SYNC_TOKEN_FILE")
        or "/etc/aesthetic-patient-sync.token"
    )
    try:
        return Path(token_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def _headers():
    token = _sync_token()
    headers = {
        "Accept": "application/json",
        "User-Agent": "A+Esthetic-Office-Sync/1.0",
    }
    if token:
        headers["X-Aesthetic-Patient-Sync"] = token
    return headers


def sync_customer_to_book(user):
    profile = getattr(user, "profile", None)
    payload = {
        "email": user.email,
        "phone": getattr(profile, "phone", "") if profile else "",
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
    try:
        response = requests.post(
            BOOK_CUSTOMER_SYNC_URL,
            json=payload,
            headers=_headers(),
            timeout=6,
        )
        body = response.json() if response.content else {}
        return bool(response.ok and body.get("ok")), body
    except (requests.RequestException, ValueError):
        return False, {}


def sync_service_catalog_from_book():
    """Mirror the canonical booking catalog into the A+ app database.

    Billing-specific numeric gross prices and VAT remain local and are never
    overwritten by the booking catalog.
    """
    try:
        response = requests.get(
            BOOK_BILLING_CATALOG_URL,
            headers=_headers(),
            timeout=6,
        )
        body = response.json() if response.content else {}
    except (requests.RequestException, ValueError):
        return {"ok": False, "updated": 0}

    if not response.ok or not body.get("ok"):
        return {"ok": False, "updated": 0}

    updated = 0
    for item in body.get("services") or []:
        slug = str(item.get("slug") or "").strip()
        name = str(item.get("name") or "").strip()
        if not slug or not name:
            continue

        service, _ = Service.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name[:140],
                "description": str(item.get("description") or ""),
                "duration_minutes": int(item.get("duration_minutes") or 30),
                "buffer_minutes": int(item.get("buffer_minutes") or 10),
                "price_label": str(item.get("price_label") or "")[:80],
                "active": bool(item.get("active", True)),
                "bookable_in_app": bool(item.get("bookable", True)),
                "requires_medical_confirmation": bool(item.get("requires_confirmation", False)),
            },
        )

        fields = []
        mappings = {
            "name": name[:140],
            "description": str(item.get("description") or ""),
            "duration_minutes": int(item.get("duration_minutes") or 30),
            "buffer_minutes": int(item.get("buffer_minutes") or 10),
            "active": bool(item.get("active", True)),
            "bookable_in_app": bool(item.get("bookable", True)),
            "requires_medical_confirmation": bool(item.get("requires_confirmation", False)),
        }
        for field, value in mappings.items():
            if getattr(service, field) != value:
                setattr(service, field, value)
                fields.append(field)

        if service.price_cents is None:
            booking_label = str(item.get("price_label") or "")[:80]
            if service.price_label != booking_label:
                service.price_label = booking_label
                fields.append("price_label")

        if fields:
            service.save(update_fields=fields)
            updated += 1

    return {"ok": True, "updated": updated}
