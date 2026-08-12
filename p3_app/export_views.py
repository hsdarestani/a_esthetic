import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from p0_app import views as p0_views
from p2_app import export_views as p2_export_views
from platform_app.models import Thread

from .models import ChallengeParticipation, ConciergeRequest, EventRegistration, QuizAttempt, UserBadge


@csrf_exempt
@require_http_methods(["GET"])
def mobile_full_export(request):
    base_response = p2_export_views.mobile_full_export(request)
    if base_response.status_code != 200:
        return base_response

    payload = json.loads(base_response.content.decode("utf-8"))
    user, error = p0_views._auth(request)
    if error:
        return error

    payload["data"]["gamification"] = {
        "challenge_participations": list(
            ChallengeParticipation.objects.filter(user=user).values(
                "id",
                "challenge_id",
                "progress",
                "last_progress_on",
                "completed_at",
                "reward_granted",
                "created_at",
                "updated_at",
            )
        ),
        "badges": [
            {
                "id": award.pk,
                "badge_id": award.badge_id,
                "badge_key": award.badge.key,
                "badge_name": award.badge.name,
                "source_type": award.source_type,
                "source_id": award.source_id,
                "awarded_at": award.created_at.isoformat(),
            }
            for award in UserBadge.objects.filter(user=user).select_related("badge")
        ],
        "quiz_attempts": list(
            QuizAttempt.objects.filter(user=user).values(
                "id",
                "quiz_id",
                "answers",
                "score",
                "total_questions",
                "percent",
                "completed",
                "passed",
                "reward_granted",
                "completed_at",
                "created_at",
                "updated_at",
            )
        ),
    }
    payload["data"]["event_registrations"] = [
        {
            "id": item.pk,
            "event_id": item.event_id,
            "event_title": item.event.title,
            "guest_name": item.guest_name,
            "seat_count": item.seat_count,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in EventRegistration.objects.filter(user=user).select_related("event")
    ]
    payload["data"]["concierge_requests"] = list(
        ConciergeRequest.objects.filter(user=user).values(
            "id",
            "thread_id",
            "request_type",
            "title",
            "details",
            "status",
            "closed_at",
            "created_at",
            "updated_at",
        )
    )
    payload["data"]["conversations"] = [
        {
            "id": thread.pk,
            "subject": thread.subject,
            "status": thread.status,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "messages": [
                {
                    "id": message.pk,
                    "body": message.body,
                    "sender_id": message.sender_id,
                    "created_at": message.created_at.isoformat(),
                }
                for message in thread.messages.filter(is_internal=False).select_related("sender")
            ],
        }
        for thread in Thread.objects.filter(user=user).prefetch_related("messages")
    ]

    response = JsonResponse(payload)
    response["Content-Disposition"] = base_response.get(
        "Content-Disposition",
        f'attachment; filename="a-plus-esthetic-data-{user.pk}.json"',
    )
    return response
