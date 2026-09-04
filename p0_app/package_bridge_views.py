import json
import re
import unicodedata

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, MemberPackage, WalletTransaction

from .models import PackageBookingRedemption, PackageBookingService


_GENERIC_WORDS = {
    "paket", "package", "packages", "sitzung", "sitzungen", "session", "sessions",
    "behandlung", "behandlungen", "termin", "termine", "plus", "a", "er", "x",
}


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _tokens(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", value)
    return {word for word in words if len(word) >= 3 and word not in _GENERIC_WORDS and not word.isdigit()}


def _package_matches(definition, service_slug, service_name):
    service_tokens = _tokens(service_name) | _tokens(service_slug.replace("-", " "))
    package_tokens = _tokens(definition.name)
    if not service_tokens or not package_tokens:
        return False
    overlap = service_tokens & package_tokens
    if overlap:
        return True
    service_compact = "".join(sorted(service_tokens))
    package_compact = "".join(sorted(package_tokens))
    return bool(service_compact and package_compact and (
        service_compact in package_compact or package_compact in service_compact
    ))


def _select_package(user, service_slug, service_name):
    today = timezone.localdate()
    base = MemberPackage.objects.select_for_update().select_related("definition").filter(
        user=user,
        status="active",
        remaining_sessions__gt=0,
        expires_at__gte=today,
        definition__active=True,
    ).order_by("expires_at", "created_at")

    mapped_ids = set(
        PackageBookingService.objects.filter(
            service_slug=service_slug,
            active=True,
            package_definition__active=True,
        ).values_list("package_definition_id", flat=True)
    )
    if mapped_ids:
        mapped = base.filter(definition_id__in=mapped_ids).first()
        if mapped:
            return mapped

    # Backward-compatible auto-link for existing packages. Once matched, persist
    # the mapping so subsequent bookings are deterministic.
    for package in base:
        if _package_matches(package.definition, service_slug, service_name):
            PackageBookingService.objects.get_or_create(
                package_definition=package.definition,
                service_slug=service_slug,
                defaults={"service_name": service_name[:180], "auto_created": True, "active": True},
            )
            return package
    return None


def _payload(redemption=None, package=None, used=False, released=False):
    package = package or (redemption.member_package if redemption else None)
    return {
        "ok": True,
        "package_used": bool(used),
        "package_released": bool(released),
        "redemption_id": redemption.pk if redemption else None,
        "package": None if not package else {
            "id": package.pk,
            "name": package.definition.name,
            "remaining_sessions": package.remaining_sessions,
            "status": package.status,
            "expires_at": package.expires_at.isoformat(),
        },
    }


@csrf_exempt
@require_http_methods(["POST"])
def mobile_package_booking(request):
    user, error = legacy_mobile_api._auth(request)
    if error:
        return error

    data = _json(request)
    action = str(data.get("action") or "reserve").strip().lower()
    booking_public_id = str(data.get("booking_public_id") or "").strip()[:64]
    service_slug = str(data.get("service_slug") or "").strip().lower()[:160]
    service_name = str(data.get("service_name") or "").strip()[:180]

    if not booking_public_id:
        return JsonResponse({"ok": False, "error": "booking_public_id_required"}, status=400)
    if action not in {"reserve", "release"}:
        return JsonResponse({"ok": False, "error": "invalid_package_action"}, status=400)

    if action == "release":
        with transaction.atomic():
            redemption = PackageBookingRedemption.objects.select_for_update().select_related(
                "member_package", "member_package__definition"
            ).filter(user=user, booking_public_id=booking_public_id).first()
            if not redemption:
                return _payload()
            if redemption.status == "released":
                return _payload(redemption=redemption, released=True)

            package = MemberPackage.objects.select_for_update().select_related("definition").get(pk=redemption.member_package_id)
            package.remaining_sessions += 1
            package.status = "active" if package.expires_at >= timezone.localdate() else "expired"
            package.save(update_fields=["remaining_sessions", "status"])
            redemption.status = "released"
            redemption.released_at = timezone.now()
            redemption.save(update_fields=["status", "released_at"])
            WalletTransaction.objects.get_or_create(
                user=user,
                kind="package",
                direction="in",
                reference=f"book:{booking_public_id}:release"[:80],
                defaults={"description": f"Paket-Sitzung freigegeben: {package.definition.name}"[:200]},
            )
            AuditLog.objects.create(
                actor=user,
                action="Package booking released",
                entity_type="MemberPackage",
                entity_id=str(package.pk),
                metadata={"booking_public_id": booking_public_id, "service_slug": redemption.service_slug},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            return _payload(redemption=redemption, package=package, released=True)

    if not service_slug:
        return JsonResponse({"ok": False, "error": "service_slug_required"}, status=400)

    with transaction.atomic():
        existing = PackageBookingRedemption.objects.select_for_update().select_related(
            "member_package", "member_package__definition"
        ).filter(user=user, booking_public_id=booking_public_id).first()
        if existing:
            return _payload(
                redemption=existing,
                used=existing.status == "reserved",
                released=existing.status == "released",
            )

        package = _select_package(user, service_slug, service_name)
        if not package:
            return _payload()

        package.remaining_sessions -= 1
        if package.remaining_sessions <= 0:
            package.remaining_sessions = 0
            package.status = "used"
        package.save(update_fields=["remaining_sessions", "status"])

        redemption = PackageBookingRedemption.objects.create(
            user=user,
            member_package=package,
            booking_public_id=booking_public_id,
            service_slug=service_slug,
            status="reserved",
        )
        WalletTransaction.objects.get_or_create(
            user=user,
            kind="package",
            direction="out",
            reference=f"book:{booking_public_id}:reserve"[:80],
            defaults={"description": f"Paket-Sitzung für Termin: {package.definition.name}"[:200]},
        )
        AuditLog.objects.create(
            actor=user,
            action="Package booking reserved",
            entity_type="MemberPackage",
            entity_id=str(package.pk),
            metadata={"booking_public_id": booking_public_id, "service_slug": service_slug},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return _payload(redemption=redemption, package=package, used=True)
