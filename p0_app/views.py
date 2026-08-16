import json
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import (
    Appointment,
    AuditLog,
    ConsentRecord,
    MemberPackage,
    Reward,
    Service,
    StaffMember,
    UserProfile,
    WalletAccount,
    WalletTransaction,
)

from .models import AccountDeletionRequest, DataExportRequest, DeviceSession
from .services import available_slots, create_slot_appointment


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _auth(request):
    return legacy_mobile_api._auth(request)


def _iso(value):
    return value.isoformat() if value else None


def _open_deletion_request(*, user=None, requested_email="", source, ip_address=None, reason=""):
    requested_email = (requested_email or (user.email if user else "") or (user.username if user else "")).strip()
    existing = AccountDeletionRequest.objects.filter(
        user=user,
        requested_email=requested_email,
        status__in=["requested", "identity_check", "scheduled"],
    ).first()
    if existing:
        existing.source = source
        existing.reason = reason[:3000]
        existing.ip_address = ip_address
        existing.requested_at = timezone.now()
        existing.save(update_fields=["source", "reason", "ip_address", "requested_at"])
        return existing

    return AccountDeletionRequest.objects.create(
        user=user,
        requested_email=requested_email,
        source=source,
        status="identity_check" if user else "requested",
        reason=reason[:3000],
        ip_address=ip_address,
    )


def account_deletion_page(request):
    error = ""
    submitted = False
    requested_email = ""
    actor = request.user if request.user.is_authenticated else None
    if actor:
        requested_email = actor.email or actor.username

    if request.method == "POST":
        if not actor:
            requested_email = request.POST.get("email", "").strip()
            try:
                validate_email(requested_email)
            except ValidationError:
                error = "Bitte geben Sie die E-Mail-Adresse ein, die zu Ihrem A+ Esthetic Konto gehört."

        if not error:
            item = _open_deletion_request(
                user=actor,
                requested_email=requested_email,
                source="authenticated_web" if actor else "public_web",
                ip_address=request.META.get("REMOTE_ADDR"),
                reason=request.POST.get("reason", ""),
            )
            if actor:
                UserProfile.objects.filter(user=actor).update(marketing_consent=False)
            AuditLog.objects.create(
                actor=actor,
                action="Kontolöschung angefordert",
                entity_type="AccountDeletionRequest",
                entity_id=str(item.pk),
                metadata={"source": item.source, "status": item.status, "requested_email": requested_email},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            submitted = True

    return render(request, "legal.html", {
        "page": "account_deletion",
        "legal_title": "Konto & Daten löschen",
        "legal_subtitle": "Löschung Ihres Customer-Club-Kontos und der zugehörigen Daten anfordern",
        "deletion_error": error,
        "deletion_submitted": submitted,
        "requested_email": requested_email,
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_account_deletion(request):
    user, error = _auth(request)
    if error:
        return error
    data = _json(request)
    item = _open_deletion_request(
        user=user,
        requested_email=user.email,
        source="mobile_app",
        ip_address=request.META.get("REMOTE_ADDR"),
        reason=str(data.get("reason") or ""),
    )
    UserProfile.objects.filter(user=user).update(marketing_consent=False)
    AuditLog.objects.create(
        actor=user,
        action="Kontolöschung angefordert",
        entity_type="AccountDeletionRequest",
        entity_id=str(item.pk),
        metadata={"source": "mobile_app", "status": item.status},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({
        "ok": True,
        "message": "deletion_requested",
        "request": {"id": item.pk, "status": item.status, "requested_at": item.requested_at.isoformat()},
    })


@csrf_exempt
@require_http_methods(["GET"])
def mobile_slots(request):
    user, error = _auth(request)
    if error:
        return error
    service = Service.objects.filter(
        pk=request.GET.get("service_id"),
        active=True,
        bookable_in_app=True,
    ).first()
    if not service:
        return JsonResponse({"ok": False, "error": "service_not_found"}, status=400)
    try:
        day = date.fromisoformat(str(request.GET.get("day") or ""))
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid_day"}, status=400)

    exclude_appointment_id = None
    raw_exclude = request.GET.get("exclude_appointment_id")
    if raw_exclude:
        owned = Appointment.objects.filter(pk=raw_exclude, user=user).first()
        if owned:
            exclude_appointment_id = owned.pk

    eligible = StaffMember.objects.filter(active=True, services=service).distinct().order_by("display_name")
    requested_staff_id = request.GET.get("staff_id")
    if requested_staff_id:
        eligible = eligible.filter(pk=requested_staff_id)
    if not eligible.exists():
        return JsonResponse({"ok": False, "error": "staff_not_found"}, status=400)

    unique_slots = set()
    for member in eligible:
        unique_slots.update(available_slots(
            service,
            member,
            day,
            exclude_appointment_id=exclude_appointment_id,
        ))

    slots = sorted(unique_slots)
    return JsonResponse({
        "ok": True,
        "service_id": service.pk,
        "day": day.isoformat(),
        "slots": [slot.isoformat() for slot in slots],
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_booking(request):
    user, error = _auth(request)
    if error:
        return error

    if request.method == "POST":
        data = _json(request)
        service = Service.objects.filter(
            pk=data.get("service_id"),
            active=True,
            bookable_in_app=True,
        ).first()
        if not service:
            return JsonResponse({"ok": False, "error": "service_not_found"}, status=400)

        starts_at = parse_datetime(str(data.get("starts_at") or ""))
        if not starts_at:
            return JsonResponse({"ok": False, "error": "invalid_start_time"}, status=400)
        if timezone.is_naive(starts_at):
            starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
        if starts_at < timezone.now() + timedelta(hours=1):
            return JsonResponse({"ok": False, "error": "start_time_too_soon"}, status=400)

        eligible = StaffMember.objects.filter(active=True, services=service).distinct().order_by("display_name")
        selected_staff = None
        if data.get("staff_id"):
            selected_staff = eligible.filter(pk=data.get("staff_id")).first()
            if not selected_staff:
                return JsonResponse({"ok": False, "error": "staff_not_found"}, status=400)
        else:
            local_day = starts_at.astimezone(timezone.get_current_timezone()).date()
            for candidate in eligible:
                if starts_at in available_slots(service, candidate, local_day):
                    selected_staff = candidate
                    break

        if not selected_staff:
            return JsonResponse({"ok": False, "error": "time_not_available"}, status=409)

        try:
            appointment = create_slot_appointment(
                user=user,
                service=service,
                staff=selected_staff,
                starts_at=starts_at,
                notes=str(data.get("notes") or ""),
                consent=bool(data.get("consent_acknowledged")),
            )
        except ValueError:
            return JsonResponse({"ok": False, "error": "time_not_available"}, status=409)
        except ValidationError as exc:
            return JsonResponse({"ok": False, "error": "invalid_appointment", "details": exc.messages}, status=400)

        return JsonResponse({
            "ok": True,
            "appointment_id": appointment.pk,
            "status": appointment.status,
            "staff": selected_staff.display_name,
            "starts_at": appointment.starts_at.isoformat(),
        }, status=201)

    services = Service.objects.filter(active=True, bookable_in_app=True).order_by("name")
    staff = StaffMember.objects.filter(active=True).prefetch_related("services").order_by("display_name")
    appointments = Appointment.objects.filter(user=user).select_related("service", "staff").order_by("-starts_at")[:20]
    return JsonResponse({
        "ok": True,
        "slot_mode": True,
        "services": [
            {
                "id": service.pk,
                "name": service.name,
                "duration_minutes": service.duration_minutes,
                "price_label": service.price_label,
            }
            for service in services
        ],
        "staff": [
            {
                "id": member.pk,
                "name": member.display_name,
                "service_ids": list(member.services.filter(active=True, bookable_in_app=True).values_list("id", flat=True)),
            }
            for member in staff
        ],
        "appointments": [
            {
                "id": item.pk,
                "service": item.service.name,
                "starts_at": _iso(item.starts_at),
                "status": item.status,
                "staff": item.staff.display_name if item.staff else "",
            }
            for item in appointments
        ],
    })


@csrf_exempt
@require_http_methods(["GET"])
def mobile_wallet(request):
    user, error = _auth(request)
    if error:
        return error
    account, _ = WalletAccount.objects.get_or_create(user=user)
    transactions = WalletTransaction.objects.filter(user=user)[:30]
    rewards = Reward.objects.filter(active=True, is_medical_service=False).order_by("coin_cost")
    packages = MemberPackage.objects.filter(user=user, status="active").select_related("definition")
    return JsonResponse({
        "ok": True,
        "balance_cents": account.balance_cents,
        "coin_balance": account.coin_balance,
        "transactions": [
            {
                "id": tx.pk,
                "description": tx.description,
                "kind": tx.kind,
                "direction": tx.direction,
                "amount_cents": tx.amount_cents,
                "coin_amount": tx.coin_amount,
                "created_at": _iso(tx.created_at),
            }
            for tx in transactions
        ],
        "rewards": [
            {"id": reward.pk, "name": reward.name, "description": reward.description, "coin_cost": reward.coin_cost}
            for reward in rewards
        ],
        "packages": [
            {
                "id": package.pk,
                "name": package.definition.name,
                "remaining_sessions": package.remaining_sessions,
                "expires_at": package.expires_at.isoformat(),
            }
            for package in packages
        ],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_redeem_reward(request, reward_id):
    user, error = _auth(request)
    if error:
        return error

    with transaction.atomic():
        reward = Reward.objects.select_for_update().filter(
            pk=reward_id,
            active=True,
            is_medical_service=False,
        ).first()
        if not reward:
            return JsonResponse({"ok": False, "error": "reward_not_found"}, status=404)
        try:
            reward.full_clean()
        except ValidationError:
            return JsonResponse({"ok": False, "error": "reward_not_available"}, status=409)

        wallet, _ = WalletAccount.objects.select_for_update().get_or_create(user=user)
        if wallet.coin_balance < reward.coin_cost:
            return JsonResponse({"ok": False, "error": "not_enough_coins"}, status=409)
        if reward.inventory is not None and reward.inventory < 1:
            return JsonResponse({"ok": False, "error": "reward_unavailable"}, status=409)

        wallet.coin_balance -= reward.coin_cost
        wallet.save(update_fields=["coin_balance", "updated_at"])
        WalletTransaction.objects.create(
            user=user,
            kind="coin",
            direction="out",
            coin_amount=reward.coin_cost,
            description=f"Reward: {reward.name}",
            reference=f"reward:{reward.pk}",
        )
        if reward.inventory is not None:
            reward.inventory -= 1
            reward.save(update_fields=["inventory"])

    return JsonResponse({"ok": True, "coin_balance": wallet.coin_balance})


@csrf_exempt
@require_http_methods(["GET"])
def mobile_devices(request):
    user, error = _auth(request)
    if error:
        return error
    current_id = getattr(getattr(request, "mobile_device_session", None), "pk", None)
    devices = DeviceSession.objects.filter(user=user)
    return JsonResponse({
        "ok": True,
        "devices": [
            {
                "id": item.pk,
                "device_name": item.device_name,
                "ip_address": item.ip_address,
                "last_seen_at": item.last_seen_at.isoformat(),
                "revoked_at": _iso(item.revoked_at),
                "current": item.pk == current_id,
            }
            for item in devices
        ],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_revoke_device(request, device_id):
    user, error = _auth(request)
    if error:
        return error
    item = DeviceSession.objects.filter(pk=device_id, user=user).first()
    if not item:
        return JsonResponse({"ok": False, "error": "device_not_found"}, status=404)
    if not item.revoked_at:
        item.revoked_at = timezone.now()
        item.save(update_fields=["revoked_at"])
    AuditLog.objects.create(
        actor=user,
        action="Gerätesitzung widerrufen",
        entity_type="DeviceSession",
        entity_id=str(item.pk),
        metadata={"current": getattr(getattr(request, "mobile_device_session", None), "pk", None) == item.pk},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"ok": True, "revoked_at": item.revoked_at.isoformat()})


@csrf_exempt
@require_http_methods(["GET"])
def mobile_export(request):
    user, error = _auth(request)
    if error:
        return error

    export = DataExportRequest.objects.create(user=user, status="processing")
    try:
        payload = {
            "exported_at": timezone.now().isoformat(),
            "account": {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "date_joined": user.date_joined.isoformat(),
            },
            "profile": list(UserProfile.objects.filter(user=user).values(
                "phone", "preferred_language", "marketing_consent", "health_data_consent", "created_at"
            )),
            "appointments": list(user.appointments.values(
                "id", "service__name", "staff__display_name", "starts_at", "ends_at", "status", "source", "created_at"
            )),
            "wallet_transactions": list(user.wallet_transactions.values(
                "id", "kind", "direction", "amount_cents", "coin_amount", "description", "reference", "created_at"
            )),
            "packages": list(user.packages.values(
                "id", "definition__name", "remaining_sessions", "expires_at", "status", "created_at"
            )),
            "consents": list(ConsentRecord.objects.filter(user=user).values(
                "id", "template__key", "template__version", "accepted", "accepted_at", "withdrawn_at"
            )),
            "reminders": list(user.reminders.values(
                "id", "title", "body", "scheduled_for", "channel", "status"
            )),
            "messages": list(user.threads.values(
                "id", "subject", "status", "messages__id", "messages__body", "messages__created_at"
            )),
            "deletion_requests": list(user.p0_deletion_requests.values(
                "id", "status", "source", "requested_at", "scheduled_for", "completed_at", "retention_note"
            )),
        }
        export.status = "ready"
        export.completed_at = timezone.now()
        export.expires_at = timezone.now() + timedelta(days=7)
        export.save(update_fields=["status", "completed_at", "expires_at"])
        AuditLog.objects.create(
            actor=user,
            action="Datenexport erstellt",
            entity_type="DataExportRequest",
            entity_id=str(export.pk),
            metadata={"source": "mobile_app"},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        response = JsonResponse({"ok": True, "export_request_id": export.pk, "data": payload})
        response["Content-Disposition"] = f'attachment; filename="a-plus-esthetic-data-{user.pk}.json"'
        return response
    except Exception as exc:
        export.status = "failed"
        export.error = str(exc)[:2000]
        export.save(update_fields=["status", "error"])
        return JsonResponse({"ok": False, "error": "export_failed"}, status=500)
