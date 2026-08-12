from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from platform_app.models import Message, Reminder, Thread, WalletAccount, WalletTransaction

from .models import (
    ChallengeParticipation,
    ConciergeRequest,
    EventRegistration,
    QuizAttempt,
    UserBadge,
)


def award_coins_once(user, amount, reference, description):
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    if amount > 5000:
        raise ValidationError("coin_reward_too_large")

    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    wallet = WalletAccount.objects.select_for_update().get(pk=wallet.pk)
    if WalletTransaction.objects.filter(user=user, kind="coin", direction="in", reference=reference).exists():
        return 0

    wallet.coin_balance += amount
    wallet.save(update_fields=["coin_balance", "updated_at"])
    WalletTransaction.objects.create(
        user=user,
        kind="coin",
        direction="in",
        coin_amount=amount,
        description=description[:200],
        reference=reference[:80],
    )
    return amount


@transaction.atomic
def record_challenge_progress(participation):
    participation = ChallengeParticipation.objects.select_for_update().select_related("challenge", "challenge__badge").get(pk=participation.pk)
    challenge = participation.challenge
    today = timezone.localdate()

    if participation.completed_at:
        return participation, 0, False
    if participation.last_progress_on == today:
        raise ValidationError("progress_already_recorded_today")
    if not challenge.active or challenge.starts_at > timezone.now() or challenge.ends_at < timezone.now():
        raise ValidationError("challenge_not_active")

    participation.progress = min(challenge.target_count, participation.progress + 1)
    participation.last_progress_on = today
    awarded = 0
    badge_awarded = False

    if participation.progress >= challenge.target_count:
        participation.completed_at = timezone.now()
        if not participation.reward_granted:
            awarded = award_coins_once(
                participation.user,
                challenge.reward_coins,
                f"p3:challenge:{challenge.pk}:u:{participation.user_id}",
                f"Challenge abgeschlossen: {challenge.title}",
            )
            participation.reward_granted = True
        if challenge.badge_id:
            _, badge_awarded = UserBadge.objects.get_or_create(
                user=participation.user,
                badge=challenge.badge,
                defaults={"source_type": "challenge", "source_id": str(challenge.pk)},
            )

    participation.save(update_fields=["progress", "last_progress_on", "completed_at", "reward_granted", "updated_at"])
    return participation, awarded, badge_awarded


@transaction.atomic
def grade_quiz(user, quiz, answers):
    questions = list(quiz.questions.all())
    if not questions:
        raise ValidationError("quiz_has_no_questions")
    if not isinstance(answers, list) or len(answers) != len(questions):
        raise ValidationError("quiz_answers_incomplete")

    normalized = []
    score = 0
    for question, answer in zip(questions, answers):
        try:
            index = int(answer)
        except (TypeError, ValueError):
            raise ValidationError("invalid_quiz_answer")
        if index < 0 or index >= len(question.options):
            raise ValidationError("invalid_quiz_answer")
        normalized.append(index)
        if index == question.correct_index:
            score += 1

    attempt, _ = QuizAttempt.objects.select_for_update().get_or_create(user=user, quiz=quiz)
    if attempt.completed:
        return attempt, 0, False, questions

    total = len(questions)
    percent = round(score * 100 / total)
    passed = percent >= quiz.passing_percent
    awarded = 0
    badge_awarded = False

    attempt.answers = normalized
    attempt.score = score
    attempt.total_questions = total
    attempt.percent = percent
    attempt.completed = True
    attempt.passed = passed
    attempt.completed_at = timezone.now()

    if passed and not attempt.reward_granted:
        awarded = award_coins_once(
            user,
            quiz.reward_coins,
            f"p3:quiz:{quiz.pk}:u:{user.pk}",
            f"Quiz bestanden: {quiz.title}",
        )
        attempt.reward_granted = True
        if quiz.badge_id:
            _, badge_awarded = UserBadge.objects.get_or_create(
                user=user,
                badge=quiz.badge,
                defaults={"source_type": "quiz", "source_id": str(quiz.pk)},
            )

    attempt.save()
    return attempt, awarded, badge_awarded, questions


def _occupied_seats(event):
    return event.registrations.filter(status__in=["registered", "attended"]).aggregate(total=Sum("seat_count"))["total"] or 0


@transaction.atomic
def register_for_event(user, event, guest_name=""):
    event = event.__class__.objects.select_for_update().get(pk=event.pk)
    if not event.active or event.starts_at <= timezone.now():
        raise ValidationError("event_not_open")

    guest_name = str(guest_name or "").strip()[:120]
    seat_count = 2 if guest_name else 1
    if seat_count == 2 and not event.allow_guest:
        raise ValidationError("event_guest_not_allowed")

    registration = EventRegistration.objects.select_for_update().filter(event=event, user=user).first()
    if registration and registration.status in {"registered", "waitlist", "attended"}:
        return registration, False

    occupied = _occupied_seats(event)
    status = "registered" if occupied + seat_count <= event.capacity else "waitlist"
    if registration:
        registration.guest_name = guest_name
        registration.seat_count = seat_count
        registration.status = status
        registration.save(update_fields=["guest_name", "seat_count", "status", "updated_at"])
    else:
        registration = EventRegistration.objects.create(
            event=event,
            user=user,
            guest_name=guest_name,
            seat_count=seat_count,
            status=status,
        )
    return registration, True


@transaction.atomic
def cancel_event_registration(registration):
    registration = EventRegistration.objects.select_for_update().select_related("event").get(pk=registration.pk)
    event = registration.event
    if registration.status not in {"registered", "waitlist"}:
        raise ValidationError("event_registration_cannot_cancel")
    if event.starts_at <= timezone.now():
        raise ValidationError("event_already_started")

    registration.status = "cancelled"
    registration.save(update_fields=["status", "updated_at"])

    promoted = []
    occupied = _occupied_seats(event)
    waitlisted = EventRegistration.objects.select_for_update().filter(event=event, status="waitlist").order_by("created_at")
    for candidate in waitlisted:
        if occupied + candidate.seat_count > event.capacity:
            continue
        candidate.status = "registered"
        candidate.save(update_fields=["status", "updated_at"])
        occupied += candidate.seat_count
        promoted.append(candidate.pk)
        Reminder.objects.create(
            user=candidate.user,
            title="Event-Platz bestätigt",
            body=f"Für {event.title} ist ein Platz frei geworden. Ihre Anmeldung ist jetzt bestätigt.",
            scheduled_for=timezone.now(),
            channel="inapp",
            status="scheduled",
            related_type="p3_event",
            related_id=str(event.pk),
        )
    return registration, promoted


@transaction.atomic
def create_concierge_request(user, request_type, title, details):
    thread = Thread.objects.create(user=user, subject=f"Concierge · {title}"[:180], status="open")
    Message.objects.create(thread=thread, sender=user, body=details[:5000], is_internal=False)
    item = ConciergeRequest.objects.create(
        user=user,
        thread=thread,
        request_type=request_type,
        title=title[:180],
        details=details[:5000],
        status="open",
    )
    return item


@transaction.atomic
def create_conversation(user, subject, body):
    thread = Thread.objects.create(user=user, subject=subject[:180], status="open")
    Message.objects.create(thread=thread, sender=user, body=body[:5000], is_internal=False)
    return thread
