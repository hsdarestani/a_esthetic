import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, UserProfile

from .models import GoogleReviewActivity

GOOGLE_PLACE_ID = "ChIJadEwN8QPvUcRyczqX4YoWxY"
GOOGLE_REVIEW_URL = f"https://search.google.com/local/writereview?placeid={GOOGLE_PLACE_ID}"


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _admin_auth(request):
    user, error = legacy_mobile_api._auth(request)
    if error:
        return None, error
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not (user.is_superuser or profile.role == "admin" or (user.is_staff and profile.role in {"admin", "manager"})):
        return None, JsonResponse({"ok": False, "error": "admin_required"}, status=403)
    return user, None


def _payload(item):
    user = item.user
    return {
        "id": item.pk,
        "customer_id": user.pk,
        "customer": user.get_full_name() or user.username,
        "email": user.email,
        "status": item.status,
        "status_label": item.get_status_display(),
        "rating": item.rating,
        "review_text": item.review_text,
        "google_review_url": item.google_review_url,
        "opened_at": item.opened_at.isoformat() if item.opened_at else None,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "verified_at": item.verified_at.isoformat() if item.verified_at else None,
        "created_at": item.created_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_reviews(request):
    user, error = legacy_mobile_api._auth(request)
    if error:
        return error

    if request.method == "POST":
        data = _json(request)
        action = str(data.get("action") or "").strip().lower()
        if action == "opened":
            item = GoogleReviewActivity.objects.create(user=user, place_id=GOOGLE_PLACE_ID, status="opened")
            AuditLog.objects.create(
                actor=user,
                action="Google Bewertung geöffnet",
                entity_type="GoogleReviewActivity",
                entity_id=str(item.pk),
                metadata={"place_id": GOOGLE_PLACE_ID},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        elif action == "submitted":
            raw_rating = data.get("rating")
            rating = None
            if raw_rating not in (None, ""):
                try:
                    rating = int(raw_rating)
                except (TypeError, ValueError):
                    return JsonResponse({"ok": False, "error": "invalid_rating"}, status=400)
                if rating < 1 or rating > 5:
                    return JsonResponse({"ok": False, "error": "invalid_rating"}, status=400)
            item = GoogleReviewActivity.objects.filter(user=user, status="opened").order_by("-created_at").first()
            if not item:
                item = GoogleReviewActivity(user=user, place_id=GOOGLE_PLACE_ID)
            item.status = "submitted"
            item.rating = rating
            item.review_text = str(data.get("review_text") or "").strip()[:4000]
            item.submitted_at = timezone.now()
            item.save()
            AuditLog.objects.create(
                actor=user,
                action="Google Bewertung als abgegeben markiert",
                entity_type="GoogleReviewActivity",
                entity_id=str(item.pk),
                metadata={"rating": rating},
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        else:
            return JsonResponse({"ok": False, "error": "invalid_action"}, status=400)

    items = GoogleReviewActivity.objects.filter(user=user).order_by("-created_at")[:50]
    return JsonResponse({
        "ok": True,
        "review_url": GOOGLE_REVIEW_URL,
        "place_id": GOOGLE_PLACE_ID,
        "activities": [_payload(item) for item in items],
    })


@csrf_exempt
@require_http_methods(["GET"])
def mobile_admin_reviews(request):
    actor, error = _admin_auth(request)
    if error:
        return error
    items = GoogleReviewActivity.objects.select_related("user").order_by("-created_at")[:300]
    return JsonResponse({"ok": True, "reviews": [_payload(item) for item in items]})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_admin_review(request, review_id):
    actor, error = _admin_auth(request)
    if error:
        return error
    item = GoogleReviewActivity.objects.select_related("user").filter(pk=review_id).first()
    if not item:
        return JsonResponse({"ok": False, "error": "review_not_found"}, status=404)
    data = _json(request)
    action = str(data.get("action") or "verify").strip().lower()
    if action != "verify":
        return JsonResponse({"ok": False, "error": "invalid_action"}, status=400)
    raw_rating = data.get("rating")
    if raw_rating not in (None, ""):
        try:
            rating = int(raw_rating)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "invalid_rating"}, status=400)
        if rating < 1 or rating > 5:
            return JsonResponse({"ok": False, "error": "invalid_rating"}, status=400)
        item.rating = rating
    external_url = str(data.get("google_review_url") or "").strip()
    if external_url:
        item.google_review_url = external_url[:200]
    item.status = "verified"
    item.verified_at = timezone.now()
    item.save()
    AuditLog.objects.create(
        actor=actor,
        action="Google Bewertung verifiziert",
        entity_type="GoogleReviewActivity",
        entity_id=str(item.pk),
        metadata={"customer_id": item.user_id, "rating": item.rating},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({"ok": True, "review": _payload(item)})
