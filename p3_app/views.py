import json
from datetime import timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, Message, Thread, WalletAccount

from .models import (
    BeautyEvent,
    Challenge,
    ChallengeParticipation,
    ConciergeRequest,
    EventRegistration,
    Quiz,
    QuizAttempt,
    UserBadge,
)
from .services import (
    cancel_event_registration,
    create_concierge_request,
    create_conversation,
    grade_quiz,
    record_challenge_progress,
    register_for_event,
)


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


def _challenge_payload(challenge, participation=None):
    today = timezone.localdate()
    return {
        "id": challenge.pk,
        "title": challenge.title,
        "description": challenge.description,
        "type": challenge.challenge_type,
        "type_label": challenge.get_challenge_type_display(),
        "target_count": challenge.target_count,
        "reward_coins": challenge.reward_coins,
        "starts_at": challenge.starts_at.isoformat(),
        "ends_at": challenge.ends_at.isoformat(),
        "badge": None if not challenge.badge else {
            "key": challenge.badge.key,
            "name": challenge.badge.name,
            "icon": challenge.badge.icon,
        },
        "participation": None if not participation else {
            "id": participation.pk,
            "progress": participation.progress,
            "completed": bool(participation.completed_at),
            "completed_at": participation.completed_at.isoformat() if participation.completed_at else None,
            "can_progress_today": not participation.completed_at and participation.last_progress_on != today,
        },
    }


def _quiz_payload(quiz, attempt=None):
    return {
        "id": quiz.pk,
        "title": quiz.title,
        "description": quiz.description,
        "passing_percent": quiz.passing_percent,
        "reward_coins": quiz.reward_coins,
        "badge": None if not quiz.badge else {
            "key": quiz.badge.key,
            "name": quiz.badge.name,
            "icon": quiz.badge.icon,
        },
        "questions": [
            {"id": q.pk, "question": q.question, "options": q.options}
            for q in quiz.questions.all()
        ],
        "attempt": None if not attempt else {
            "completed": attempt.completed,
            "score": attempt.score,
            "total_questions": attempt.total_questions,
            "percent": attempt.percent,
            "passed": attempt.passed,
            "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        },
    }


def _registration_payload(registration):
    return {
        "id": registration.pk,
        "status": registration.status,
        "status_label": registration.get_status_display(),
        "guest_name": registration.guest_name,
        "seat_count": registration.seat_count,
        "created_at": registration.created_at.isoformat(),
    }


def _thread_payload(thread, concierge=None):
    last_message = thread.messages.filter(is_internal=False).order_by("-created_at").first()
    return {
        "id": thread.pk,
        "subject": thread.subject,
        "status": thread.status,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
        "last_message": None if not last_message else {
            "body": last_message.body,
            "mine": last_message.sender_id == thread.user_id,
            "created_at": last_message.created_at.isoformat(),
        },
        "concierge_id": concierge.pk if concierge else None,
    }


@csrf_exempt
@require_http_methods(["GET"])
def mobile_gamification(request):
    user, error = _auth(request)
    if error:
        return error

    now = timezone.now()
    challenges = list(
        Challenge.objects.filter(active=True, starts_at__lte=now, ends_at__gte=now).select_related("badge")
    )
    participations = {
        item.challenge_id: item
        for item in ChallengeParticipation.objects.filter(user=user, challenge__in=challenges)
    }
    quizzes = list(
        Quiz.objects.filter(active=True, approved=True).select_related("badge").prefetch_related("questions")
    )
    attempts = {
        item.quiz_id: item
        for item in QuizAttempt.objects.filter(user=user, quiz__in=quizzes)
    }
    wallet, _ = WalletAccount.objects.get_or_create(user=user)

    return JsonResponse({
        "ok": True,
        "coin_balance": wallet.coin_balance,
        "safety_note": "Challenges und Quiz belohnen Pflege, Lernen und Community-Aktivitäten – niemals die Häufigkeit medizinischer Behandlungen.",
        "challenges": [_challenge_payload(item, participations.get(item.pk)) for item in challenges],
        "badges": [
            {
                "id": award.badge_id,
                "key": award.badge.key,
                "name": award.badge.name,
                "description": award.badge.description,
                "icon": award.badge.icon,
                "awarded_at": award.created_at.isoformat(),
            }
            for award in UserBadge.objects.filter(user=user, badge__active=True).select_related("badge")
        ],
        "quizzes": [_quiz_payload(item, attempts.get(item.pk)) for item in quizzes],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_challenge_join(request, challenge_id):
    user, error = _auth(request)
    if error:
        return error
    now = timezone.now()
    challenge = Challenge.objects.filter(
        pk=challenge_id, active=True, starts_at__lte=now, ends_at__gte=now
    ).select_related("badge").first()
    if not challenge:
        return JsonResponse({"ok": False, "error": "challenge_not_active"}, status=404)
    participation, created = ChallengeParticipation.objects.get_or_create(user=user, challenge=challenge)
    if created:
        _audit(request, user, "Challenge gestartet", participation, {"challenge": challenge.pk})
    return JsonResponse({"ok": True, "created": created, "challenge": _challenge_payload(challenge, participation)}, status=201 if created else 200)


@csrf_exempt
@require_http_methods(["POST"])
def mobile_challenge_progress(request, challenge_id):
    user, error = _auth(request)
    if error:
        return error
    participation = ChallengeParticipation.objects.filter(
        user=user, challenge_id=challenge_id
    ).select_related("challenge", "challenge__badge").first()
    if not participation:
        return JsonResponse({"ok": False, "error": "challenge_not_joined"}, status=404)
    try:
        participation, awarded, badge_awarded = record_challenge_progress(participation)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": exc.messages[0]}, status=409)
    _audit(
        request,
        user,
        "Challenge-Fortschritt aktualisiert",
        participation,
        {"progress": participation.progress, "coins_awarded": awarded},
    )
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    return JsonResponse({
        "ok": True,
        "challenge": _challenge_payload(participation.challenge, participation),
        "coins_awarded": awarded,
        "badge_awarded": badge_awarded,
        "coin_balance": wallet.coin_balance,
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_quiz_submit(request, quiz_id):
    user, error = _auth(request)
    if error:
        return error
    quiz = Quiz.objects.filter(pk=quiz_id, active=True, approved=True).select_related("badge").prefetch_related("questions").first()
    if not quiz:
        return JsonResponse({"ok": False, "error": "quiz_not_found"}, status=404)
    try:
        attempt, awarded, badge_awarded, questions = grade_quiz(user, quiz, _json(request).get("answers"))
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": exc.messages[0]}, status=400)
    _audit(request, user, "Quiz abgeschlossen", attempt, {"quiz": quiz.pk, "percent": attempt.percent, "passed": attempt.passed})
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    return JsonResponse({
        "ok": True,
        "result": {
            "score": attempt.score,
            "total_questions": attempt.total_questions,
            "percent": attempt.percent,
            "passed": attempt.passed,
            "passing_percent": quiz.passing_percent,
            "coins_awarded": awarded,
            "badge_awarded": badge_awarded,
            "coin_balance": wallet.coin_balance,
            "review": [
                {
                    "question_id": question.pk,
                    "correct_index": question.correct_index,
                    "explanation": question.explanation,
                }
                for question in questions
            ],
        },
    })


@csrf_exempt
@require_http_methods(["GET"])
def mobile_events(request):
    user, error = _auth(request)
    if error:
        return error
    now = timezone.now()
    events = list(BeautyEvent.objects.filter(active=True, starts_at__gte=now).prefetch_related("registrations"))
    registrations = {
        item.event_id: item
        for item in EventRegistration.objects.filter(user=user, event__in=events)
    }
    payload = []
    for event in events:
        occupied = event.registrations.filter(status__in=["registered", "attended"]).aggregate(total=Sum("seat_count"))["total"] or 0
        registration = registrations.get(event.pk)
        payload.append({
            "id": event.pk,
            "title": event.title,
            "description": event.description,
            "starts_at": event.starts_at.isoformat(),
            "ends_at": event.ends_at.isoformat(),
            "location": event.location,
            "capacity": event.capacity,
            "remaining_seats": max(0, event.capacity - occupied),
            "allow_guest": event.allow_guest,
            "registration": _registration_payload(registration) if registration else None,
        })
    return JsonResponse({
        "ok": True,
        "events": payload,
        "note": "Event-Anmeldungen sind organisatorisch. Medizinische Beratung oder Behandlung wird dadurch nicht ersetzt.",
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_event_register(request, event_id):
    user, error = _auth(request)
    if error:
        return error
    event = BeautyEvent.objects.filter(pk=event_id, active=True).first()
    if not event:
        return JsonResponse({"ok": False, "error": "event_not_found"}, status=404)
    try:
        registration, changed = register_for_event(user, event, _json(request).get("guest_name", ""))
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": exc.messages[0]}, status=409)
    _audit(request, user, "Event-Anmeldung gespeichert", registration, {"status": registration.status, "event": event.pk})
    return JsonResponse({"ok": True, "changed": changed, "registration": _registration_payload(registration)}, status=201 if changed else 200)


@csrf_exempt
@require_http_methods(["POST"])
def mobile_event_cancel(request, event_id):
    user, error = _auth(request)
    if error:
        return error
    registration = EventRegistration.objects.filter(user=user, event_id=event_id).select_related("event").first()
    if not registration:
        return JsonResponse({"ok": False, "error": "event_registration_not_found"}, status=404)
    try:
        registration, promoted = cancel_event_registration(registration)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": exc.messages[0]}, status=409)
    _audit(request, user, "Event-Anmeldung storniert", registration, {"event": event_id, "waitlist_promoted": len(promoted)})
    return JsonResponse({"ok": True, "registration": _registration_payload(registration)})


def _ical_escape(value):
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n").replace("\r", "")


@csrf_exempt
@require_http_methods(["GET"])
def mobile_event_calendar(request, event_id):
    user, error = _auth(request)
    if error:
        return error
    registration = EventRegistration.objects.filter(
        user=user, event_id=event_id, status__in=["registered", "attended"]
    ).select_related("event").first()
    if not registration:
        return JsonResponse({"ok": False, "error": "event_registration_not_found"}, status=404)
    event = registration.event
    body = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//A+ Esthetic//Events//DE",
        "BEGIN:VEVENT",
        f"UID:aesthetic-event-{event.pk}@esthetic.smarbiz.sbs",
        f"DTSTAMP:{timezone.now().astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{event.starts_at.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{event.ends_at.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{_ical_escape('A+ Esthetic – ' + event.title)}",
        f"LOCATION:{_ical_escape(event.location)}",
        f"DESCRIPTION:{_ical_escape(event.description)}",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ])
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="aesthetic-event-{event.pk}.ics"'
    response["Cache-Control"] = "private, no-store, max-age=0"
    return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_concierge(request):
    user, error = _auth(request)
    if error:
        return error
    if request.method == "POST":
        data = _json(request)
        valid_types = {value for value, _ in ConciergeRequest.TYPE}
        request_type = str(data.get("request_type") or "other")
        title = str(data.get("title") or "").strip()
        details = str(data.get("details") or "").strip()
        if request_type not in valid_types:
            return JsonResponse({"ok": False, "error": "invalid_concierge_type"}, status=400)
        if len(title) < 3:
            return JsonResponse({"ok": False, "error": "concierge_title_required"}, status=400)
        if len(details) < 5:
            return JsonResponse({"ok": False, "error": "concierge_details_required"}, status=400)
        item = create_concierge_request(user, request_type, title[:180], details[:5000])
        _audit(request, user, "Concierge-Anfrage erstellt", item, {"type": request_type})
        return JsonResponse({"ok": True, "request_id": item.pk, "thread_id": item.thread_id}, status=201)

    items = ConciergeRequest.objects.filter(user=user).select_related("thread")
    return JsonResponse({
        "ok": True,
        "types": [{"value": value, "label": label} for value, label in ConciergeRequest.TYPE],
        "note": "Concierge koordiniert organisatorische Wünsche. Medizinische Entscheidungen erfolgen ausschließlich im persönlichen fachlichen Kontakt.",
        "requests": [
            {
                "id": item.pk,
                "request_type": item.request_type,
                "request_type_label": item.get_request_type_display(),
                "title": item.title,
                "details": item.details,
                "status": item.status,
                "status_label": item.get_status_display(),
                "thread_id": item.thread_id,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ],
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_conversations(request):
    user, error = _auth(request)
    if error:
        return error
    if request.method == "POST":
        data = _json(request)
        subject = str(data.get("subject") or "").strip()
        body = str(data.get("body") or "").strip()
        if len(subject) < 3:
            return JsonResponse({"ok": False, "error": "conversation_subject_required"}, status=400)
        if len(body) < 1:
            return JsonResponse({"ok": False, "error": "message_required"}, status=400)
        if len(body) > 5000:
            return JsonResponse({"ok": False, "error": "message_too_long"}, status=400)
        thread = create_conversation(user, subject, body)
        _audit(request, user, "Unterhaltung erstellt", thread)
        return JsonResponse({"ok": True, "thread_id": thread.pk}, status=201)

    threads = list(Thread.objects.filter(user=user).prefetch_related("messages"))
    concierge_map = {
        item.thread_id: item
        for item in ConciergeRequest.objects.filter(user=user, thread__in=threads)
    }
    return JsonResponse({
        "ok": True,
        "note": "Für akute Notfälle ist dieser Nachrichtenbereich nicht geeignet.",
        "threads": [_thread_payload(thread, concierge_map.get(thread.pk)) for thread in threads],
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_conversation_detail(request, thread_id):
    user, error = _auth(request)
    if error:
        return error
    thread = Thread.objects.filter(pk=thread_id, user=user).first()
    if not thread:
        return JsonResponse({"ok": False, "error": "conversation_not_found"}, status=404)
    if request.method == "POST":
        if thread.status != "open":
            return JsonResponse({"ok": False, "error": "conversation_closed"}, status=409)
        body = str(_json(request).get("body") or "").strip()
        if not body:
            return JsonResponse({"ok": False, "error": "message_required"}, status=400)
        if len(body) > 5000:
            return JsonResponse({"ok": False, "error": "message_too_long"}, status=400)
        message = Message.objects.create(thread=thread, sender=user, body=body, is_internal=False)
        thread.save(update_fields=["updated_at"])
        _audit(request, user, "Nachricht gesendet", message, {"thread": thread.pk})

    messages = thread.messages.filter(is_internal=False).select_related("sender")
    concierge = ConciergeRequest.objects.filter(user=user, thread=thread).first()
    return JsonResponse({
        "ok": True,
        "thread": _thread_payload(thread, concierge),
        "messages": [
            {
                "id": msg.pk,
                "body": msg.body,
                "mine": msg.sender_id == user.pk,
                "sender": msg.sender.get_full_name() or msg.sender.username,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_conversation_close(request, thread_id):
    user, error = _auth(request)
    if error:
        return error
    thread = Thread.objects.filter(pk=thread_id, user=user).first()
    if not thread:
        return JsonResponse({"ok": False, "error": "conversation_not_found"}, status=404)
    thread.status = "closed"
    thread.save(update_fields=["status", "updated_at"])
    _audit(request, user, "Unterhaltung geschlossen", thread)
    return JsonResponse({"ok": True, "status": thread.status})
