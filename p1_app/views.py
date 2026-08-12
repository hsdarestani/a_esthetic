import json
import mimetypes
from datetime import date

from django.core.exceptions import ValidationError
from django.http import FileResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, FollowUp, UserProfile

from .models import (
    AftercareTaskStatus,
    BeautyPlan,
    BeautyPlanStep,
    ProgressAlbum,
    ProgressPhoto,
)
from .services import ensure_aftercare_assignments, sha256_upload


MAX_PROGRESS_PHOTO_BYTES = 8 * 1024 * 1024
ALLOWED_PROGRESS_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _auth(request):
    return legacy_mobile_api._auth(request)


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _audit(request, user, action, entity, metadata=None):
    AuditLog.objects.create(
        actor=user,
        action=action,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        metadata=metadata or {},
        ip_address=request.META.get("REMOTE_ADDR"),
    )


def _plan_payload(plan):
    return {
        "id": plan.pk,
        "title": plan.title,
        "journey_type": plan.journey_type,
        "journey_label": plan.get_journey_type_display(),
        "goal": plan.goal,
        "target_date": plan.target_date.isoformat() if plan.target_date else None,
        "monthly_budget_cents": plan.monthly_budget_cents,
        "annual_budget_cents": plan.annual_budget_cents,
        "status": plan.status,
        "progress_percent": plan.progress_percent,
        "steps": [
            {
                "id": step.pk,
                "title": step.title,
                "description": step.description,
                "due_on": step.due_on.isoformat() if step.due_on else None,
                "step_type": step.step_type,
                "step_type_label": step.get_step_type_display(),
                "estimated_cost_cents": step.estimated_cost_cents,
                "completed": step.completed,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            }
            for step in plan.steps.all()
        ],
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_progress(request):
    user, error = _auth(request)
    if error:
        return error

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if request.method == "POST":
        data = _json(request)
        title = str(data.get("title") or "").strip()[:160]
        if not title:
            return JsonResponse({"ok": False, "error": "title_required"}, status=400)
        album = ProgressAlbum.objects.create(
            user=user,
            title=title,
            description=str(data.get("description") or "").strip()[:3000],
        )
        _audit(request, user, "Privates Verlaufsalbum erstellt", album)
        return JsonResponse({"ok": True, "album_id": album.pk}, status=201)

    albums = ProgressAlbum.objects.filter(user=user).prefetch_related("photos")
    return JsonResponse({
        "ok": True,
        "health_data_consent": profile.health_data_consent,
        "privacy_note": "Fotos bleiben privat und werden niemals automatisch für Marketing freigegeben.",
        "albums": [
            {
                "id": album.pk,
                "title": album.title,
                "description": album.description,
                "marketing_use_allowed": album.marketing_use_allowed,
                "created_at": album.created_at.isoformat(),
                "photos": [
                    {
                        "id": photo.pk,
                        "kind": photo.kind,
                        "kind_label": photo.get_kind_display(),
                        "taken_at": photo.taken_at.isoformat(),
                        "sha256": photo.sha256,
                        "url": f"/progress/photo/{photo.pk}/",
                    }
                    for photo in album.photos.all() if photo.visible_to_customer
                ],
            }
            for album in albums
        ],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_progress_upload(request, album_id):
    user, error = _auth(request)
    if error:
        return error

    album = ProgressAlbum.objects.filter(pk=album_id, user=user).first()
    if not album:
        return JsonResponse({"ok": False, "error": "album_not_found"}, status=404)
    profile = UserProfile.objects.filter(user=user).first()
    if not profile or not profile.health_data_consent:
        return JsonResponse({"ok": False, "error": "health_data_consent_required"}, status=403)

    upload = request.FILES.get("photo")
    if not upload:
        return JsonResponse({"ok": False, "error": "photo_required"}, status=400)
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if content_type not in ALLOWED_PROGRESS_MIME:
        return JsonResponse({"ok": False, "error": "unsupported_image_type"}, status=415)
    if upload.size > MAX_PROGRESS_PHOTO_BYTES:
        return JsonResponse({"ok": False, "error": "photo_too_large"}, status=413)

    kind = str(request.POST.get("kind") or "progress")
    if kind not in {choice[0] for choice in ProgressPhoto.KIND}:
        return JsonResponse({"ok": False, "error": "invalid_photo_kind"}, status=400)

    digest = sha256_upload(upload)
    photo = ProgressPhoto.objects.create(
        album=album,
        kind=kind,
        image=upload,
        uploaded_by=user,
        sha256=digest,
        visible_to_customer=True,
    )
    _audit(request, user, "Privates Verlaufsfoto hochgeladen", photo, {"kind": kind, "sha256": digest})
    return JsonResponse({"ok": True, "photo_id": photo.pk, "sha256": digest}, status=201)


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def mobile_progress_photo(request, photo_id):
    user, error = _auth(request)
    if error:
        return error
    photo = ProgressPhoto.objects.select_related("album").filter(pk=photo_id, album__user=user).first()
    if not photo:
        return JsonResponse({"ok": False, "error": "photo_not_found"}, status=404)

    if request.method == "DELETE":
        storage = photo.image.storage
        name = photo.image.name
        _audit(request, user, "Privates Verlaufsfoto gelöscht", photo)
        photo.delete()
        if name:
            storage.delete(name)
        return JsonResponse({"ok": True})

    content_type = mimetypes.guess_type(photo.image.name)[0] or "application/octet-stream"
    response = FileResponse(photo.image.open("rb"), content_type=content_type)
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@csrf_exempt
@require_http_methods(["DELETE"])
def mobile_progress_album_delete(request, album_id):
    user, error = _auth(request)
    if error:
        return error
    album = ProgressAlbum.objects.prefetch_related("photos").filter(pk=album_id, user=user).first()
    if not album:
        return JsonResponse({"ok": False, "error": "album_not_found"}, status=404)
    files = [(photo.image.storage, photo.image.name) for photo in album.photos.all() if photo.image.name]
    _audit(request, user, "Privates Verlaufsalbum gelöscht", album)
    album.delete()
    for storage, name in files:
        storage.delete(name)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET"])
def mobile_aftercare(request):
    user, error = _auth(request)
    if error:
        return error
    ensure_aftercare_assignments(user)
    assigned = user.p1_assigned_aftercare.select_related("template", "appointment__service").prefetch_related("task_statuses__task")
    followups = user.followups.order_by("-due_at")[:30]
    return JsonResponse({
        "ok": True,
        "safety_note": "Nachsorgeinhalte werden ausschließlich aus intern freigegebenen Vorlagen angezeigt; individuelle medizinische Entscheidungen erfolgen nicht in der App.",
        "assigned": [
            {
                "id": item.pk,
                "title": item.template.title,
                "introduction": item.template.introduction,
                "approved_by": item.template.approved_by,
                "version": item.template.version,
                "service": item.appointment.service.name,
                "appointment_id": item.appointment_id,
                "starts_at": item.starts_at.isoformat(),
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "tasks": [
                    {
                        "status_id": status.pk,
                        "title": status.task.title,
                        "description": status.task.description,
                        "task_type": status.task.task_type,
                        "task_type_label": status.task.get_task_type_display(),
                        "warning_sign": status.task.warning_sign,
                        "completed": status.completed,
                    }
                    for status in item.task_statuses.all()
                ],
            }
            for item in assigned
        ],
        "followups": [
            {
                "id": item.pk,
                "title": item.title,
                "questions": item.questions,
                "due_at": item.due_at.isoformat(),
                "status": item.status,
                "requires_review": item.requires_review,
                "customer_response": item.customer_response,
            }
            for item in followups
        ],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_aftercare_task_toggle(request, status_id):
    user, error = _auth(request)
    if error:
        return error
    status = AftercareTaskStatus.objects.select_related("assigned", "task").filter(pk=status_id, assigned__user=user).first()
    if not status:
        return JsonResponse({"ok": False, "error": "aftercare_task_not_found"}, status=404)
    status.completed = not status.completed
    status.completed_at = timezone.now() if status.completed else None
    status.save(update_fields=["completed", "completed_at", "updated_at"])

    assigned = status.assigned
    all_complete = not assigned.task_statuses.filter(completed=False).exists()
    new_completed_at = timezone.now() if all_complete else None
    if assigned.completed_at != new_completed_at:
        assigned.completed_at = new_completed_at
        assigned.save(update_fields=["completed_at", "updated_at"])
    _audit(request, user, "Nachsorge-Aufgabe aktualisiert", status, {"completed": status.completed})
    return JsonResponse({"ok": True, "completed": status.completed, "assigned_complete": all_complete})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_followup_response(request, followup_id):
    user, error = _auth(request)
    if error:
        return error
    followup = FollowUp.objects.filter(pk=followup_id, user=user).first()
    if not followup:
        return JsonResponse({"ok": False, "error": "followup_not_found"}, status=404)
    data = _json(request)
    response_text = str(data.get("response") or "").strip()[:3000]
    request_contact = bool(data.get("request_contact"))
    if not response_text and not request_contact:
        return JsonResponse({"ok": False, "error": "response_required"}, status=400)
    followup.customer_response = {"text": response_text, "request_contact": request_contact}
    followup.status = "review" if request_contact else "answered"
    followup.requires_review = request_contact
    followup.save(update_fields=["customer_response", "status", "requires_review"])
    _audit(request, user, "Follow-up beantwortet", followup, {"request_contact": request_contact})
    return JsonResponse({"ok": True, "status": followup.status, "requires_review": followup.requires_review})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_beauty_plans(request):
    user, error = _auth(request)
    if error:
        return error

    if request.method == "POST":
        data = _json(request)
        title = str(data.get("title") or "").strip()[:180]
        if not title:
            return JsonResponse({"ok": False, "error": "title_required"}, status=400)
        journey = str(data.get("journey_type") or "custom")
        if journey not in {choice[0] for choice in BeautyPlan.JOURNEY}:
            return JsonResponse({"ok": False, "error": "invalid_journey_type"}, status=400)
        target_date = None
        if data.get("target_date"):
            try:
                target_date = date.fromisoformat(str(data["target_date"]))
            except ValueError:
                return JsonResponse({"ok": False, "error": "invalid_target_date"}, status=400)
        try:
            monthly = max(0, min(int(data.get("monthly_budget_cents") or 0), 10_000_000))
            annual = max(0, min(int(data.get("annual_budget_cents") or 0), 100_000_000))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "invalid_budget"}, status=400)
        plan = BeautyPlan(
            user=user,
            title=title,
            journey_type=journey,
            goal=str(data.get("goal") or "").strip()[:5000],
            target_date=target_date,
            monthly_budget_cents=monthly,
            annual_budget_cents=annual,
            status="active",
        )
        try:
            plan.full_clean()
        except ValidationError:
            return JsonResponse({"ok": False, "error": "invalid_beauty_plan"}, status=400)
        plan.save()
        _audit(request, user, "Beauty Plan erstellt", plan, {"journey_type": journey})
        return JsonResponse({"ok": True, "plan": _plan_payload(plan)}, status=201)

    plans = BeautyPlan.objects.filter(user=user).prefetch_related("steps")
    return JsonResponse({
        "ok": True,
        "safety_note": "Beauty Plans organisieren persönliche Ziele, Budget und Aufgaben. Sie ersetzen keine medizinische Beratung und treffen keine Behandlungsentscheidung.",
        "journeys": [{"value": value, "label": label} for value, label in BeautyPlan.JOURNEY],
        "step_types": [{"value": value, "label": label} for value, label in BeautyPlanStep.TYPE],
        "plans": [_plan_payload(plan) for plan in plans],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_beauty_plan_step(request, plan_id):
    user, error = _auth(request)
    if error:
        return error
    plan = BeautyPlan.objects.filter(pk=plan_id, user=user).exclude(status="archived").first()
    if not plan:
        return JsonResponse({"ok": False, "error": "beauty_plan_not_found"}, status=404)
    data = _json(request)
    title = str(data.get("title") or "").strip()[:180]
    step_type = str(data.get("step_type") or "care")
    if not title:
        return JsonResponse({"ok": False, "error": "title_required"}, status=400)
    if step_type not in {choice[0] for choice in BeautyPlanStep.TYPE}:
        return JsonResponse({"ok": False, "error": "invalid_step_type"}, status=400)
    due_on = None
    if data.get("due_on"):
        try:
            due_on = date.fromisoformat(str(data["due_on"]))
        except ValueError:
            return JsonResponse({"ok": False, "error": "invalid_due_date"}, status=400)
    try:
        cost = max(0, min(int(data.get("estimated_cost_cents") or 0), 10_000_000))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_budget"}, status=400)
    step = BeautyPlanStep.objects.create(
        plan=plan,
        title=title,
        description=str(data.get("description") or "").strip()[:3000],
        due_on=due_on,
        step_type=step_type,
        estimated_cost_cents=cost,
        sort_order=plan.steps.count() * 10 + 10,
    )
    _audit(request, user, "Beauty-Plan-Schritt erstellt", step, {"plan_id": plan.pk, "step_type": step_type})
    return JsonResponse({"ok": True, "step_id": step.pk}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def mobile_beauty_plan_step_toggle(request, step_id):
    user, error = _auth(request)
    if error:
        return error
    step = BeautyPlanStep.objects.select_related("plan").filter(pk=step_id, plan__user=user).first()
    if not step:
        return JsonResponse({"ok": False, "error": "beauty_plan_step_not_found"}, status=404)
    step.completed = not step.completed
    step.completed_at = timezone.now() if step.completed else None
    step.save(update_fields=["completed", "completed_at", "updated_at"])
    plan = step.plan
    if plan.steps.exists() and not plan.steps.filter(completed=False).exists() and plan.status == "active":
        plan.status = "completed"
        plan.save(update_fields=["status", "updated_at"])
    elif not step.completed and plan.status == "completed":
        plan.status = "active"
        plan.save(update_fields=["status", "updated_at"])
    _audit(request, user, "Beauty-Plan-Schritt aktualisiert", step, {"completed": step.completed})
    return JsonResponse({"ok": True, "completed": step.completed, "plan_status": plan.status, "progress_percent": plan.progress_percent})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_beauty_plan_archive(request, plan_id):
    user, error = _auth(request)
    if error:
        return error
    plan = BeautyPlan.objects.filter(pk=plan_id, user=user).first()
    if not plan:
        return JsonResponse({"ok": False, "error": "beauty_plan_not_found"}, status=404)
    plan.status = "archived"
    plan.save(update_fields=["status", "updated_at"])
    _audit(request, user, "Beauty Plan archiviert", plan)
    return JsonResponse({"ok": True})
