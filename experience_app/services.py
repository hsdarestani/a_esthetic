import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from platform_app.models import (
    Appointment,
    AuditLog,
    BlockedPeriod,
    IntegrationConfig,
    MemberAccount,
    Reminder,
    Service,
    StaffMember,
    WalletAccount,
    WalletTransaction,
    WorkingHour,
)

from .models import (
    AssistantConversation,
    CoinRule,
    DataExportRequest,
    KnowledgeArticle,
    NotificationOutbox,
    ProgressPhoto,
    PushSubscription,
    RewardRedemption,
)


MEDICAL_BLOCK_TERMS = {
    "diagnose", "diagnosis", "dosis", "dosierung", "welche behandlung", "welcher filler",
    "bin ich geeignet", "was habe ich", "krankheit", "symptom beurteilen", "notfall",
    "wie viel botox", "einheiten botox", "therapie", "medikament", "verschreibung",
}


def integration_ready(provider: str) -> bool:
    try:
        config = IntegrationConfig.objects.get(provider=provider, enabled=True)
    except IntegrationConfig.DoesNotExist:
        return False
    required = {
        "google": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
        "apple": ["APPLE_CLIENT_ID", "APPLE_TEAM_ID", "APPLE_KEY_ID", "APPLE_PRIVATE_KEY"],
        "doctolib": ["DOCTOLIB_API_BASE", "DOCTOLIB_CLIENT_ID", "DOCTOLIB_CLIENT_SECRET"],
        "simplybook": ["SIMPLYBOOK_COMPANY", "SIMPLYBOOK_LOGIN", "SIMPLYBOOK_API_KEY"],
    }.get(provider, [])
    return config.sync_enabled and all(os.environ.get(key) for key in required)


def available_slots(service: Service, staff: StaffMember, day, *, step_minutes=15):
    """Return available timezone-aware slot datetimes for one date."""
    if not service.active or not service.bookable_in_app or not staff.active:
        return []
    if not staff.services.filter(pk=service.pk).exists():
        return []
    weekday = day.weekday()
    duration = timedelta(minutes=service.duration_minutes + service.buffer_minutes)
    timezone_obj = timezone.get_current_timezone()
    slots = []
    hours = WorkingHour.objects.filter(staff=staff, weekday=weekday, active=True).order_by("start_time")
    for working in hours:
        cursor = timezone.make_aware(datetime.combine(day, working.start_time), timezone_obj)
        end_of_day = timezone.make_aware(datetime.combine(day, working.end_time), timezone_obj)
        while cursor + duration <= end_of_day:
            slot_end = cursor + duration
            if cursor >= timezone.now():
                blocked = BlockedPeriod.objects.filter(
                    staff=staff, starts_at__lt=slot_end, ends_at__gt=cursor
                ).exists()
                conflict = Appointment.objects.filter(
                    staff=staff,
                    status__in=["requested", "confirmed"],
                    starts_at__lt=slot_end,
                    ends_at__gt=cursor,
                ).exists()
                if not blocked and not conflict:
                    slots.append(cursor)
            cursor += timedelta(minutes=step_minutes)
    return slots


def create_slot_appointment(*, user, service, staff, starts_at, notes="", consent=False, source="app"):
    duration = timedelta(minutes=service.duration_minutes + service.buffer_minutes)
    with transaction.atomic():
        StaffMember.objects.select_for_update().get(pk=staff.pk)
        appointment = Appointment(
            user=user,
            service=service,
            staff=staff,
            starts_at=starts_at,
            ends_at=starts_at + duration,
            status="requested" if service.requires_medical_confirmation else "confirmed",
            source=source,
            notes_customer=notes,
            consent_acknowledged=consent,
        )
        appointment.full_clean()
        appointment.save()
    Reminder.objects.create(
        user=user,
        title="Termin gespeichert",
        body=f"{service.name} am {starts_at:%d.%m.%Y um %H:%M}",
        scheduled_for=max(timezone.now(), starts_at - timedelta(days=1)),
        channel="inapp",
        status="scheduled",
    )
    return appointment


def award_coins(user, event: str, description: str, reference=""):
    try:
        rule = CoinRule.objects.get(event=event, active=True)
    except CoinRule.DoesNotExist:
        return 0
    today = timezone.localdate()
    already = WalletTransaction.objects.filter(
        user=user,
        kind="coin",
        direction="in",
        reference__startswith=f"{event}:{today.isoformat()}",
    ).count()
    if already >= rule.daily_limit:
        return 0
    with transaction.atomic():
        wallet, _ = WalletAccount.objects.select_for_update().get_or_create(user=user)
        wallet.coin_balance += rule.coins
        wallet.save(update_fields=["coin_balance", "updated_at"])
        WalletTransaction.objects.create(
            user=user,
            kind="coin",
            direction="in",
            coin_amount=rule.coins,
            description=description,
            reference=f"{event}:{today.isoformat()}:{reference}"[:80],
        )
    return rule.coins


def redeem_reward(user, reward):
    reward.full_clean()
    if reward.is_medical_service:
        raise ValidationError("Medizinische Leistungen sind als Reward ausgeschlossen.")
    with transaction.atomic():
        wallet = WalletAccount.objects.select_for_update().get(user=user)
        if wallet.coin_balance < reward.coin_cost:
            raise ValidationError("Nicht genügend A+ Coins.")
        if reward.inventory is not None and reward.inventory < 1:
            raise ValidationError("Diese Prämie ist nicht verfügbar.")
        wallet.coin_balance -= reward.coin_cost
        wallet.save(update_fields=["coin_balance", "updated_at"])
        WalletTransaction.objects.create(
            user=user,
            kind="coin",
            direction="out",
            coin_amount=reward.coin_cost,
            description=f"Reward: {reward.name}",
            reference=f"reward:{reward.pk}",
        )
        redemption = RewardRedemption.objects.create(
            user=user, reward=reward, coins_spent=reward.coin_cost
        )
        if reward.inventory is not None:
            reward.inventory -= 1
            reward.save(update_fields=["inventory"])
    return redemption


def _approved_context(question: str, limit=5):
    terms = [term for term in question.lower().split() if len(term) > 3][:8]
    query = Q()
    for term in terms:
        query |= Q(title__icontains=term) | Q(summary__icontains=term) | Q(body__icontains=term)
    articles = KnowledgeArticle.objects.filter(approved=True, active=True)
    if query:
        articles = articles.filter(query)
    articles = list(articles[:limit])
    return articles, "\n\n".join(
        f"Titel: {article.title}\n{article.summary or article.body[:900]}" for article in articles
    )


def safe_assistant_answer(user, question: str, language="de"):
    normalized = " ".join(question.lower().split())
    blocked = any(term in normalized for term in MEDICAL_BLOCK_TERMS)
    articles, context = _approved_context(question)
    if blocked:
        answer = (
            "Dabei darf der A+ Wissensassistent nicht helfen. Die App stellt keine Diagnose, "
            "Dosierung, Eignungsprüfung oder individuelle Behandlungsempfehlung bereit. Bitte "
            "vereinbaren Sie für medizinische Fragen eine persönliche ärztliche Beratung."
        )
        conversation = AssistantConversation.objects.create(
            user=user,
            question=question,
            answer=answer,
            language=language,
            blocked_medical_request=True,
            provider="safety-rule",
            safety_metadata={"matched": True},
        )
        return answer, conversation

    fallback = (
        "Ich kann allgemeine, von A+ Esthetic freigegebene Informationen zu Abläufen, Membership, "
        "Produkten und Pflegehinweisen erklären. Für individuelle medizinische Fragen ist eine "
        "persönliche ärztliche Beratung erforderlich."
    )
    if articles:
        fallback = articles[0].summary or articles[0].body[:1200]

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    answer = fallback
    provider = "approved-knowledge"
    error = ""
    if api_key and context:
        payload = {
            "model": model,
            "store": False,
            "safety_identifier": hashlib.sha256(f"aesthetic:{user.pk}".encode()).hexdigest(),
            "instructions": (
                "Du bist der A+ Esthetic Wissensassistent. Antworte ausschließlich auf Deutsch und "
                "nur anhand der freigegebenen Wissensbasis. Keine Diagnose, Dosierung, Eignungsprüfung, "
                "Therapie- oder Behandlungsempfehlung, Ergebnisgarantie oder Notfallbeurteilung. "
                "Bewerte niemals das Aussehen einer Person. Bei medizinischen Fragen verweise auf eine "
                "persönliche ärztliche Beratung. Gib klar an, wenn die Wissensbasis nicht ausreicht."
            ),
            "input": f"Freigegebene Wissensbasis:\n{context}\n\nFrage:\n{question}",
            "max_output_tokens": 500,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = json.load(response)
            answer = data.get("output_text") or fallback
            provider = "openai-responses"
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            error = str(exc)[:300]

    conversation = AssistantConversation.objects.create(
        user=user,
        question=question,
        answer=answer,
        language=language,
        blocked_medical_request=False,
        provider=provider,
        safety_metadata={"articles": [a.pk for a in articles], "provider_error": error},
    )
    return answer, conversation


def queue_notification(user, title, body, *, channel="inapp", scheduled_for=None, sensitive=False):
    return NotificationOutbox.objects.create(
        user=user,
        title=title,
        body=body,
        channel=channel,
        scheduled_for=scheduled_for or timezone.now(),
        sensitive=sensitive,
    )


def build_user_export(user):
    data = {
        "exported_at": timezone.now().isoformat(),
        "account": {
            "username": user.username,
            "email": user.email,
            "name": user.get_full_name(),
            "date_joined": user.date_joined.isoformat(),
        },
        "appointments": list(user.appointments.values()),
        "wallet_transactions": list(user.wallet_transactions.values()),
        "passport": list(user.passport_entries.values()),
        "consents": list(user.consents.values()),
        "reminders": list(user.reminders.values()),
        "followups": list(user.followups.values()),
        "beauty_plans": list(user.beauty_plans.values()),
        "cabinet_products": list(user.cabinet_products.values()),
        "orders": list(user.shop_orders.values()),
        "feedback": list(user.feedback_entries.values()),
        "complaints": list(user.complaints.values()),
    }
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("a-plus-esthetic-data.json", json.dumps(data, ensure_ascii=False, indent=2, default=str))
    stream.seek(0)
    return stream


def hash_progress_photo(photo: ProgressPhoto):
    digest = hashlib.sha256()
    photo.image.open("rb")
    for chunk in iter(lambda: photo.image.read(1024 * 1024), b""):
        digest.update(chunk)
    photo.image.close()
    photo.sha256 = digest.hexdigest()
    photo.save(update_fields=["sha256"])
    return photo.sha256


def log_action(request, action, entity=None, metadata=None):
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        entity_type=entity.__class__.__name__ if entity else "",
        entity_id=str(entity.pk) if entity and entity.pk else "",
        metadata=metadata or {},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
