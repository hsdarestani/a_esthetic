import io
import mimetypes
from urllib.parse import urlencode

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
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

from .ops_models import DashboardBanner, DashboardHeroImage


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


HERO_LABELS = {
    "frau": "Damen",
    "herr": "Herren",
    "default": "Standard",
}


def hero_image_url(request, hero):
    """Public marketing image URL; cache-busted when a slot is replaced."""
    return request.build_absolute_uri(
        reverse("p0_dashboard_hero_image", kwargs={"variant": hero.variant})
    ) + "?v=" + str(int(hero.updated_at.timestamp()))


def _hero_slot_payload(request, slot):
    hero = DashboardHeroImage.objects.filter(variant=slot).first()
    return {
        "variant": slot,
        "label": HERO_LABELS[slot],
        "image_url": hero_image_url(request, hero) if hero and hero.image else "",
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_admin_dashboard_hero(request):
    actor, error = _admin_auth(request)
    if error:
        return error

    if request.method == "POST":
        data = _json(request)
        slot = str(data.get("variant") or "")
        if slot not in HERO_LABELS:
            return JsonResponse({"ok": False, "error": "invalid_hero_variant"}, status=400)

        action = str(data.get("action") or "save").lower()
        previous = DashboardHeroImage.objects.filter(variant=slot).first()
        if action == "clear":
            if previous:
                old_file = previous.image
                previous.delete()
                if old_file:
                    old_file.delete(save=False)
        elif action == "save":
            encoded = str(data.get("image_data") or "")
            mime = str(data.get("image_type") or "").lower()
            mime_formats = {
                "image/jpeg": ("JPEG", ".jpg"),
                "image/png": ("PNG", ".png"),
                "image/webp": ("WEBP", ".webp"),
            }
            if mime not in mime_formats or not encoded:
                return JsonResponse({"ok": False, "error": "invalid_image_type"}, status=400)
            # The admin bridge sends base64 JSON; reject oversized data before decode.
            if len(encoded) > 9 * 1024 * 1024:
                return JsonResponse({"ok": False, "error": "hero_image_too_large"}, status=400)
            try:
                decoded = base64.b64decode(encoded, validate=True)
                if not decoded or len(decoded) > 6 * 1024 * 1024:
                    raise ValueError("image_too_large")
                with Image.open(io.BytesIO(decoded)) as img:
                    fmt, width, height = img.format, img.width, img.height
                    if fmt != mime_formats[mime][0] or width < 600 or height < 350 or width > 6000 or height > 6000:
                        raise ValueError("invalid_image_dimensions")
                    img.verify()
            except (binascii.Error, ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
                return JsonResponse({"ok": False, "error": "invalid_hero_image"}, status=400)

            hero = previous or DashboardHeroImage(variant=slot)
            old_name = hero.image.name if previous and hero.image else ""
            hero.image.save(uuid.uuid4().hex + mime_formats[mime][1], ContentFile(decoded), save=False)
            hero.full_clean()
            hero.save()
            if old_name and old_name != hero.image.name:
                hero.image.storage.delete(old_name)
        else:
            return JsonResponse({"ok": False, "error": "invalid_action"}, status=400)

        AuditLog.objects.create(
            actor=actor,
            action="Startseitenbild " + ("gelöscht" if action == "clear" else "gespeichert"),
            entity_type="DashboardHeroImage",
            entity_id=slot,
        )

    return JsonResponse({
        "ok": True,
        "hero_images": [_hero_slot_payload(request, slot) for slot in HERO_LABELS],
    })


@require_http_methods(["GET"])
def dashboard_hero_image(request, variant):
    if variant not in HERO_LABELS:
        raise Http404
    hero = DashboardHeroImage.objects.filter(variant=variant).first()
    if not hero or not hero.image:
        raise Http404
    mime = mimetypes.guess_type(hero.image.name)[0] or "application/octet-stream"
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise Http404
    try:
        response = FileResponse(hero.image.open("rb"), content_type=mime)
    except (FileNotFoundError, OSError):
        raise Http404
    response["Cache-Control"] = "public, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response
