import json
import os
import re
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import requests
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import mobile_api
from .account_state import account_state
from .models import AccountVerification, AuditLog, Referral, UserProfile, WalletAccount, WalletTransaction


VERIFY_TTL = timedelta(minutes=15)
REFERRAL_POINTS = 300
MAIL_RELAY_URL = "https://book.a-esthetic.de/api/internal/app-mail/"


def _json(request):
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


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


def _relay_mail(payload):
    token = _sync_token()
    if not token:
        raise RuntimeError("mail_relay_not_configured")
    request = Request(
        MAIL_RELAY_URL,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-Aesthetic-Patient-Sync": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "A+Esthetic-Onboarding/1.0",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            if response.status not in {200, 201} or not result.get("ok"):
                raise RuntimeError("mail_relay_failed")
            return result
    except HTTPError as exc:
        raise RuntimeError(f"mail_relay_http_{exc.code}") from exc
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("mail_relay_unavailable") from exc


def _normalize_phone(value):
    raw = re.sub(r"[^0-9+]", "", str(value or "").strip())
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    elif raw.startswith("0"):
        raw = "+49" + raw[1:]
    digits = re.sub(r"\D", "", raw)
    if not raw.startswith("+") or len(digits) < 9:
        raise ValueError("invalid_phone")
    return raw[:40]


def _issue_challenge(user, channel):
    code = f"{secrets.randbelow(1000000):06d}"
    AccountVerification.objects.update_or_create(
        user=user,
        channel=channel,
        defaults={
            "code_digest": make_password(code),
            "expires_at": timezone.now() + VERIFY_TTL,
            "verified_at": None,
            "attempts": 0,
        },
    )
    return code


def _send_email_code(user):
    code = _issue_challenge(user, "email")
    return _relay_mail({
        "kind": "email_verification",
        "recipient": user.email,
        "name": user.first_name or user.get_full_name() or "A+ Mitglied",
        "code": code,
    })


def _send_sms(phone, code):
    webhook = str(os.environ.get("SMS_WEBHOOK_URL") or "").strip()
    if webhook:
        token = str(os.environ.get("SMS_WEBHOOK_TOKEN") or "").strip()
        response = requests.post(
            webhook,
            json={
                "to": phone,
                "message": f"A+ Esthetic: Ihr Bestätigungscode lautet {code}. Gültig für 15 Minuten.",
            },
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=15,
        )
        if not response.ok:
            raise RuntimeError(f"sms_webhook_{response.status_code}")
        return {"provider": "webhook"}

    sid = str(os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    auth = str(os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    sender = str(os.environ.get("TWILIO_FROM_NUMBER") or "").strip()
    if not (sid and auth and sender):
        raise RuntimeError("sms_not_configured")

    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data={
            "To": phone,
            "From": sender,
            "Body": f"A+ Esthetic: Ihr Bestätigungscode lautet {code}. Gültig für 15 Minuten.",
        },
        auth=(sid, auth),
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(f"sms_twilio_{response.status_code}")
    return {"provider": "twilio"}


def _send_sms_code(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not profile.phone:
        raise RuntimeError("phone_required")
    code = _issue_challenge(user, "sms")
    return _send_sms(profile.phone, code)


def _attach_referral(user, code):
    code = str(code or "").strip().upper()
    if not code:
        return None
    referral = Referral.objects.select_for_update().filter(code__iexact=code).first()
    if not referral:
        raise ValueError("invalid_referral_code")
    if referral.referrer_id == user.pk:
        raise ValueError("cannot_refer_yourself")
    if referral.referred_user_id and referral.referred_user_id != user.pk:
        raise ValueError("referral_code_used")
    referral.referred_user = user
    referral.invited_email = user.email
    referral.status = "registered"
    referral.registered_at = referral.registered_at or timezone.now()
    referral.save(update_fields=["referred_user", "invited_email", "status", "registered_at"])
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.referral_code_used = referral.code
    profile.save(update_fields=["referral_code_used"])
    return referral


def _grant_new_member_referral_points(user):
    referral = Referral.objects.filter(referred_user=user).first()
    if not referral:
        return 0
    reference = f"referral_signup:{referral.pk}"
    with transaction.atomic():
        wallet, _ = WalletAccount.objects.select_for_update().get_or_create(user=user)
        if WalletTransaction.objects.filter(
            user=user, kind="coin", reference=reference
        ).exists():
            return 0
        wallet.coin_balance += REFERRAL_POINTS
        wallet.save(update_fields=["coin_balance", "updated_at"])
        WalletTransaction.objects.create(
            user=user,
            kind="coin",
            direction="in",
            coin_amount=REFERRAL_POINTS,
            description="Willkommensbonus durch Empfehlung",
            reference=reference,
        )
    return REFERRAL_POINTS


def _maybe_complete(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    state = account_state(user)
    if not state.get("missing") and profile.onboarding_required and not profile.profile_completed_at:
        profile.profile_completed_at = timezone.now()
        profile.save(update_fields=["profile_completed_at"])
        _grant_new_member_referral_points(user)
    return account_state(user)


def award_referrer_first_booking(email, booking_public_id=""):
    user = User.objects.filter(
        email__iexact=str(email or "").strip()
    ).order_by("id").first()
    if not user:
        return {"ok": True, "awarded": False, "reason": "app_user_not_found"}

    referral = Referral.objects.select_related("referrer").filter(
        referred_user=user
    ).first()
    if not referral:
        return {"ok": True, "awarded": False, "reason": "referral_not_found"}

    reference = f"referral_first_booking:{referral.pk}"
    with transaction.atomic():
        wallet, _ = WalletAccount.objects.select_for_update().get_or_create(
            user=referral.referrer
        )
        if WalletTransaction.objects.filter(
            user=referral.referrer, kind="coin", reference=reference
        ).exists():
            return {"ok": True, "awarded": False, "reason": "already_awarded"}
        points = int(referral.reward_coins or REFERRAL_POINTS)
        wallet.coin_balance += points
        wallet.save(update_fields=["coin_balance", "updated_at"])
        WalletTransaction.objects.create(
            user=referral.referrer,
            kind="coin",
            direction="in",
            coin_amount=points,
            description="Erste Buchung einer Empfehlung",
            reference=reference,
        )
        referral.status = "rewarded"
        referral.rewarded_at = timezone.now()
        referral.save(update_fields=["status", "rewarded_at"])

    try:
        from p0_app.push import create_notification
        create_notification(
            referral.referrer,
            "Empfehlung erfolgreich",
            f"Ihre Empfehlung hat den ersten Termin gebucht. +{points} A+ Punkte.",
            category="referral",
            deeplink="friends",
            data={"booking_public_id": booking_public_id},
        )
    except Exception:
        pass
    return {"ok": True, "awarded": True, "points": points}


@csrf_exempt
@require_http_methods(["GET"])
def auth_config(request):
    google_enabled = bool(getattr(settings, "GOOGLE_SOCIAL_LOGIN_ENABLED", False))
    apple_enabled = bool(getattr(settings, "APPLE_SOCIAL_LOGIN_ENABLED", False))
    return JsonResponse({
        "ok": True,
        "google": google_enabled,
        "apple": apple_enabled,
        # OAuth client identifiers are public by design and are needed by the
        # providers' official web button libraries. Secrets remain server-only.
        "google_client_id": settings.GOOGLE_CLIENT_ID if google_enabled else "",
        "apple_client_id": settings.APPLE_CLIENT_ID if apple_enabled else "",
    })


@csrf_exempt
@require_http_methods(["POST"])
def signup(request):
    data = _json(request)
    email = str(data.get("email") or "").strip().lower()
    first_name = str(data.get("first_name") or "").strip()[:80]
    last_name = str(data.get("last_name") or "").strip()[:80]
    salutation = str(data.get("salutation") or "").strip().lower()
    password = str(data.get("password") or "")
    try:
        validate_email(email)
        phone = _normalize_phone(data.get("phone"))
        if salutation not in {"herr", "frau", "divers"}:
            raise ValueError("invalid_salutation")
        if not first_name or not last_name:
            raise ValueError("name_required")
        validate_password(password)
    except ValidationError as exc:
        return JsonResponse(
            {"ok": False, "error": "invalid_signup", "message": " ".join(exc.messages)},
            status=400,
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"ok": False, "error": "email_in_use"}, status=409)

    with transaction.atomic():
        base = re.sub(r"[^a-zA-Z0-9._-]", "", email.split("@", 1)[0])[:120] or "member"
        username = base
        suffix = 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{base[:130]}-{suffix}"
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        UserProfile.objects.create(
            user=user,
            role="customer",
            phone=phone,
            salutation=salutation,
            onboarding_required=True,
            auth_provider="password",
        )
        referral_code = str(data.get("referral_code") or "").strip()
        if referral_code:
            try:
                _attach_referral(user, referral_code)
            except ValueError as exc:
                transaction.set_rollback(True)
                return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    email_sent = False
    sms_sent = False
    sms_error = ""
    try:
        _send_email_code(user)
        email_sent = True
    except Exception:
        pass
    try:
        _send_sms_code(user)
        sms_sent = True
    except Exception as exc:
        sms_error = str(exc)

    AuditLog.objects.create(
        actor=user,
        action="Mobile Registrierung",
        entity_type="UserAccount",
        entity_id=str(user.pk),
        metadata={"email_sent": email_sent, "sms_sent": sms_sent},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({
        "ok": True,
        "token": mobile_api._token_for(user),
        "account": account_state(user),
        "email_sent": email_sent,
        "sms_sent": sms_sent,
        "sms_error": sms_error,
    }, status=201)


def _incomplete_user(request):
    return mobile_api._auth(request, allow_incomplete=True)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def onboarding(request):
    user, error = _incomplete_user(request)
    if error:
        return error
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        data = _json(request)
        first_name = str(data.get("first_name") or user.first_name).strip()[:80]
        last_name = str(data.get("last_name") or user.last_name).strip()[:80]
        salutation = str(data.get("salutation") or profile.salutation).strip().lower()
        if salutation not in {"herr", "frau", "divers"}:
            return JsonResponse({"ok": False, "error": "invalid_salutation"}, status=400)

        new_phone = profile.phone
        if "phone" in data:
            try:
                new_phone = _normalize_phone(data.get("phone"))
            except ValueError:
                return JsonResponse({"ok": False, "error": "invalid_phone"}, status=400)
        if new_phone != profile.phone:
            profile.phone_verified_at = None

        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])
        profile.phone = new_phone
        profile.salutation = salutation
        profile.onboarding_required = True
        profile.save(
            update_fields=["phone", "salutation", "phone_verified_at", "onboarding_required"]
        )

        referral_code = str(data.get("referral_code") or "").strip()
        if referral_code and not profile.referral_code_used:
            try:
                with transaction.atomic():
                    _attach_referral(user, referral_code)
            except ValueError as exc:
                return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    state = _maybe_complete(user)
    return JsonResponse({
        "ok": True,
        "account": state,
        "profile": {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": profile.phone,
            "salutation": profile.salutation,
            "referral_code": profile.referral_code_used,
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def email_request(request):
    user, error = _incomplete_user(request)
    if error:
        return error
    try:
        _send_email_code(user)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    return JsonResponse({"ok": True, "sent": True})


@csrf_exempt
@require_http_methods(["POST"])
def email_confirm(request):
    user, error = _incomplete_user(request)
    if error:
        return error
    code = str(_json(request).get("code") or "").strip()
    item = AccountVerification.objects.filter(user=user, channel="email").first()
    if not item or item.verified_at or item.expires_at < timezone.now():
        return JsonResponse({"ok": False, "error": "verification_expired"}, status=400)
    if item.attempts >= 6:
        return JsonResponse({"ok": False, "error": "too_many_attempts"}, status=429)
    if not check_password(code, item.code_digest):
        item.attempts += 1
        item.save(update_fields=["attempts"])
        return JsonResponse({"ok": False, "error": "invalid_code"}, status=400)

    now = timezone.now()
    item.verified_at = now
    item.save(update_fields=["verified_at"])
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.email_verified_at = now
    profile.save(update_fields=["email_verified_at"])
    return JsonResponse({"ok": True, "account": _maybe_complete(user)})


@csrf_exempt
@require_http_methods(["POST"])
def sms_request(request):
    user, error = _incomplete_user(request)
    if error:
        return error
    try:
        result = _send_sms_code(user)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    return JsonResponse({"ok": True, "sent": True, "provider": result.get("provider")})


@csrf_exempt
@require_http_methods(["POST"])
def sms_confirm(request):
    user, error = _incomplete_user(request)
    if error:
        return error
    code = str(_json(request).get("code") or "").strip()
    item = AccountVerification.objects.filter(user=user, channel="sms").first()
    if not item or item.verified_at or item.expires_at < timezone.now():
        return JsonResponse({"ok": False, "error": "verification_expired"}, status=400)
    if item.attempts >= 6:
        return JsonResponse({"ok": False, "error": "too_many_attempts"}, status=429)
    if not check_password(code, item.code_digest):
        item.attempts += 1
        item.save(update_fields=["attempts"])
        return JsonResponse({"ok": False, "error": "invalid_code"}, status=400)

    now = timezone.now()
    item.verified_at = now
    item.save(update_fields=["verified_at"])
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.phone_verified_at = now
    profile.save(update_fields=["phone_verified_at"])
    return JsonResponse({"ok": True, "account": _maybe_complete(user)})


@csrf_exempt
@require_http_methods(["GET"])
def social_session(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "social_session_required"}, status=401)

    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if profile.role == "customer":
        provider = "social"
        try:
            account = user.socialaccount_set.first()
            if account:
                provider = account.provider
        except Exception:
            pass
        profile.auth_provider = provider
        profile.onboarding_required = True
        if user.email and not profile.email_verified_at:
            profile.email_verified_at = timezone.now()
        profile.save(
            update_fields=["auth_provider", "onboarding_required", "email_verified_at"]
        )

    return JsonResponse({
        "ok": True,
        "token": mobile_api._token_for(user),
        "account": _maybe_complete(user),
    })
