import json
import secrets

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, Campaign, GiftCard, Referral

from .push import create_notification


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


def _send_referral_email(referral):
    referrer_name = referral.referrer.get_full_name() or referral.referrer.username
    invite_url = f"https://esthetic.smarbiz.sbs/?ref={referral.code}"
    subject = f"{referrer_name} lädt Sie zu A+ Esthetic ein"
    text = (
        f"Hallo,\n\n{referrer_name} hat Sie zum A+ Esthetic Customer Club eingeladen.\n\n"
        f"Einladung öffnen: {invite_url}\n\n"
        "Mit freundlichen Grüßen\nA+ Esthetic"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#172027">
      <div style="font-size:28px;font-weight:800;letter-spacing:.04em;margin-bottom:20px">A+ ESTHETIC</div>
      <h1 style="font-size:25px;margin:0 0 14px">Eine persönliche Einladung</h1>
      <p style="font-size:16px;line-height:1.6"><strong>{referrer_name}</strong> hat Sie zum A+ Esthetic Customer Club eingeladen.</p>
      <p style="margin:26px 0"><a href="{invite_url}" style="display:inline-block;background:#172027;color:#fff;text-decoration:none;padding:14px 22px;border-radius:12px;font-weight:700">Einladung öffnen</a></p>
      <p style="font-size:13px;line-height:1.5;color:#66717a">Diese Einladung wurde von einem A+ Esthetic Mitglied an diese E-Mail-Adresse gesendet. Falls Sie keine Einladung erwartet haben, können Sie diese Nachricht ignorieren.</p>
    </div>
    """
    connection = get_connection(fail_silently=False)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        to=[referral.invited_email],
        connection=connection,
    )
    message.attach_alternative(html, "text/html")
    sent = message.send(fail_silently=False)
    if sent != 1:
        raise RuntimeError("referral_email_not_sent")
    return invite_url


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
            invite_url = _send_referral_email(referral)
            email_sent = True
        except Exception as exc:
            AuditLog.objects.create(
                actor=user,
                action="Referral-E-Mail fehlgeschlagen",
                entity_type="Referral",
                entity_id=str(referral.pk),
                metadata={"error": str(exc)[:500]},
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
            metadata={"invite_url": invite_url},
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
