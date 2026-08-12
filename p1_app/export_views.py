import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from p0_app import views as p0_views

from .models import AftercareTaskStatus, BeautyPlan, ProgressAlbum


@csrf_exempt
@require_http_methods(["GET"])
def mobile_full_export(request):
    base_response = p0_views.mobile_export(request)
    if base_response.status_code != 200:
        return base_response

    payload = json.loads(base_response.content.decode("utf-8"))
    user, error = p0_views._auth(request)
    if error:
        return error

    payload["data"]["progress_albums"] = [
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
                    "taken_at": photo.taken_at.isoformat(),
                    "sha256": photo.sha256,
                    "stored_name": photo.image.name,
                }
                for photo in album.photos.all()
            ],
        }
        for album in ProgressAlbum.objects.filter(user=user).prefetch_related("photos")
    ]
    payload["data"]["aftercare"] = list(
        AftercareTaskStatus.objects.filter(assigned__user=user).values(
            "id",
            "assigned_id",
            "assigned__appointment_id",
            "assigned__template__title",
            "task__title",
            "task__task_type",
            "completed",
            "completed_at",
            "created_at",
        )
    )
    payload["data"]["beauty_plans"] = [
        {
            "id": plan.pk,
            "title": plan.title,
            "journey_type": plan.journey_type,
            "goal": plan.goal,
            "target_date": plan.target_date.isoformat() if plan.target_date else None,
            "monthly_budget_cents": plan.monthly_budget_cents,
            "annual_budget_cents": plan.annual_budget_cents,
            "status": plan.status,
            "created_at": plan.created_at.isoformat(),
            "updated_at": plan.updated_at.isoformat(),
            "steps": list(plan.steps.values(
                "id", "title", "description", "due_on", "step_type",
                "estimated_cost_cents", "completed", "completed_at", "sort_order"
            )),
        }
        for plan in BeautyPlan.objects.filter(user=user).prefetch_related("steps")
    ]

    response = JsonResponse(payload)
    response["Content-Disposition"] = base_response.get("Content-Disposition", f'attachment; filename="a-plus-esthetic-data-{user.pk}.json"')
    return response
