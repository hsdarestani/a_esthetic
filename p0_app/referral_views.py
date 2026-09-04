import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, Campaign, GiftCard, Referral

from .push import create_notification


REFERRAL_RELAY_URL = "https://book.a-esthetic.de/api/mobile/referral-email/"


def _auth(request):
    return legacy_mobile_api._auth(request)


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _new_code():
    while True:
        code = "APLUS-" + secrets.token_hex(5).upper()
        if not Referral.objects.filter(code=code).exists():
            return code


def _send_referral_email(referral, request):
    auth = str(request.headers.get("Authorization") or "").strip()
    if not auth.startswith("Bearer "):
        raise RuntimeError("customer_club_auth_missing")
    body = json.dumps({
        "invited_email": referral.invited_email,
        "referral_code": referral.code,
    }).encode("utf-8")
    remote = Request(
        REFERRAL_RELAY_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "A-Esthetic-Customer-Club-Referral/1.0",
        },
    )
    try:
        with urlopen(remote, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if response.status not in {200, 201} or not payload.get("ok") or not payload.get("email_sent"):
                raise RuntimeError(f"book_referral_relay_{response.status}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"book_referral_relay_http_{exc.code}:{detail}") from exc
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"book_referral_relay_unavailable:{exc}") from exc
    return f"https://esthetic.smarbiz.sbs/?ref={referral.code}"


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_club(request):
    user, error = _auth(request)
    if error:
        return error

    email_sent = None
    referral_id = None
    if request.method == "POST":
        data = _json(request)
        invited_email = str(data.get("invited_email") or "").strip().lower()
        try:
            validate_email(invited_email)
        except ValidationError:
            return JsonResponse({"ok": False, "error": "valid_email_required"}, status=400)
        if invited_email == (user.email or "").strip().lower():
            return JsonResponse({"ok": False, "error": "cannot_refer_yourself"}, status=409)

        referral = Referral.objects.filter(
            referrer=user,
            invited_email__iexact=invited_email,
            status="invited",
        ).order_by("-created_at").first()
        if not referral:
            referral = Referral.objects.create(
                referrer=user,
                code=_new_code(),
                invited_email=invited_email,
                reward_coins=300,
            )
        referral_id = referral.pk
        try:
            invite_url = _send_referral_email(referral, request)
            email_sent = True
        except Exception as exc:
            AuditLog.objects.create(
                actor=user,
                action="Referral-E-Mail fehlgeschlagen",
                entity_type="Referral",
                entity_id=str(referral.pk),
                metadata={"error": str(exc)[:500], "relay": "book"},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
            return JsonResponse({
                "ok": False,
                "error": "referral_email_failed",
                "referral_id": referral.pk,
            }, status=503)

        AuditLog.objects.create(
            actor=user,
            action="Referral-E-Mail versendet",
            entity_type="Referral",
            entity_id=str(referral.pk),
            metadata={"invite_url": invite_url, "relay": "book"},
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        create_notification(
            user,
            "Einladung versendet",
            f"Ihre Einladung an {invited_email} wurde per E-Mail verschickt.",
            category="referral",
            deeplink="club",
            send_push=False,
        )

    campaigns = Campaign.objects.filter(
        active=True,
        starts_at__lte=timezone.now(),
        ends_at__gte=timezone.now(),
    )
    giftcards = GiftCard.objects.filter(purchaser=user)
    referrals = Referral.objects.filter(referrer=user).order_by("-created_at")[:20]
    payload = {
        "ok": True,
        "member": legacy_mobile_api._member_payload(user),
        "campaigns": [
            {"id": c.pk, "name": c.name, "message": c.message, "ends_at": c.ends_at.isoformat()}
            for c in campaigns
        ],
        "giftcards": [
            {"id": c.pk, "code": c.code, "balance_cents": c.balance_cents, "status": c.status}
            for c in giftcards
        ],
        "referrals": [
            {"id": r.pk, "code": r.code, "email": r.invited_email, "status": r.status, "reward_coins": r.reward_coins}
            for r in referrals
        ],
    }
    if email_sent is not None:
        payload.update({"email_sent": email_sent, "referral_id": referral_id})
    return JsonResponse(payload, status=201 if request.method == "POST" else 200)
