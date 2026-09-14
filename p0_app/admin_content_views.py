import base64
import binascii
import json
import uuid
from datetime import timedelta

from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, UserProfile

from .ops_models import DashboardBanner


def _json(request):
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
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


def _payload(item, request=None):
    return {
        "id": item.pk,
        "title": item.title,
        "text": item.text,
        "image_url": request.build_absolute_uri(reverse("p0_dashboard_banner_cover", kwargs={"banner_id": item.pk})) if request and item.cover_image else item.image_url,
        "cta_label": item.cta_label,
        "cta_url": item.cta_url,
        "active": item.active,
        "starts_at": item.starts_at.isoformat(),
        "ends_at": item.ends_at.isoformat() if item.ends_at else None,
        "sort_order": item.sort_order,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_admin_dashboard_banners(request):
    actor, error = _admin_auth(request)
    if error:
        return error

    if request.method == "POST":
        data = _json(request)
        action = str(data.get("action") or "save").strip().lower()
        banner_id = data.get("id")
        item = DashboardBanner.objects.filter(pk=banner_id).first() if banner_id else None
        if action == "delete":
            if not item:
                return JsonResponse({"ok": False, "error": "banner_not_found"}, status=404)
            item.delete()
            AuditLog.objects.create(actor=actor, action="Dashboard-Kampagne gelöscht", entity_type="DashboardBanner", entity_id=str(banner_id))
            return JsonResponse({"ok": True, "deleted": int(banner_id)})

        title = str(data.get("title") or "").strip()
        if not title:
            return JsonResponse({"ok": False, "error": "title_required"}, status=400)
        starts = parse_datetime(str(data.get("starts_at") or "")) or timezone.now()
        ends = parse_datetime(str(data.get("ends_at") or "")) if data.get("ends_at") else None
        if ends and ends <= starts:
            return JsonResponse({"ok": False, "error": "invalid_date_range"}, status=400)
        if not ends:
            ends = starts + timedelta(days=45)
        values = {
            "title": title[:160],
            "text": str(data.get("text") or "").strip()[:3000],
            "image_url": str(data.get("image_url") or "").strip()[:500],
            "cta_label": str(data.get("cta_label") or "").strip()[:80],
            "cta_url": str(data.get("cta_url") or "").strip()[:500],
            "active": bool(data.get("active", True)),
            "starts_at": starts,
            "ends_at": ends,
            "sort_order": max(0, min(9999, int(data.get("sort_order") or 100))),
        }
        cover_data = str(data.get("cover_data") or "").strip()
        cover_name = str(data.get("cover_name") or "banner.jpg").strip()
        cover_type = str(data.get("cover_type") or "").lower()
        if cover_data:
            if cover_type not in {"image/jpeg", "image/png", "image/webp"}:
                return JsonResponse({"ok": False, "error": "invalid_cover_type"}, status=400)
            try:
                decoded = base64.b64decode(cover_data, validate=True)
            except (binascii.Error, ValueError):
                return JsonResponse({"ok": False, "error": "invalid_cover_data"}, status=400)
            if not decoded or len(decoded) > 6 * 1024 * 1024:
                return JsonResponse({"ok": False, "error": "cover_too_large"}, status=400)
        if item:
            for key, value in values.items():
                setattr(item, key, value)
        else:
            item = DashboardBanner(**values)
        if cover_data:
            extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[cover_type]
            safe_name = f"{uuid.uuid4().hex}{extension}"
            item.cover_image.save(safe_name, ContentFile(decoded), save=False)
        item.save()
        AuditLog.objects.create(actor=actor, action="Dashboard-Kampagne gespeichert", entity_type="DashboardBanner", entity_id=str(item.pk), metadata={"title": item.title})

    items = DashboardBanner.objects.all()[:100]
    return JsonResponse({"ok": True, "banners": [_payload(item, request) for item in items]})


@require_http_methods(["GET"])
def dashboard_banner_cover(request, banner_id):
    item = DashboardBanner.objects.filter(pk=banner_id, active=True).first()
    if not item or not item.cover_image:
        raise Http404
    try:
        response = FileResponse(item.cover_image.open("rb"), content_type="image/*")
    except (FileNotFoundError, OSError):
        raise Http404
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response
