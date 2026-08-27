from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, ConsentRecord, ConsentTemplate, UserProfile


@csrf_exempt
@require_http_methods(["POST"])
def mobile_progress_consent(request):
    user, error = legacy_mobile_api._auth(request)
    if error:
        return error

    try:
        import json
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
    except (ValueError, UnicodeDecodeError):
        data = {}

    accepted = data.get("accepted") is True
    profile, _ = UserProfile.objects.get_or_create(user=user)
    template, _ = ConsentTemplate.objects.get_or_create(
        key="progress-photos",
        version="1.0",
        defaults={
            "title": "Private Vorher-/Nachher- und Verlaufsfotos",
            "text": "Ich willige in die Verarbeitung meiner freiwillig hochgeladenen privaten Verlaufsfotos innerhalb meines A+ Esthetic Customer-Club-Kontos ein. Die Fotos werden nicht automatisch für Marketing verwendet.",
            "health_data": True,
            "marketing": False,
            "active": True,
        },
    )

    if accepted:
        active = ConsentRecord.objects.filter(
            user=user,
            template=template,
            accepted=True,
            withdrawn_at__isnull=True,
        ).first()
        if not active:
            active = ConsentRecord.objects.create(
                user=user,
                template=template,
                accepted=True,
                ip_address=request.META.get("REMOTE_ADDR"),
                evidence={"source": "mobile_app", "purpose": "private_progress_photos"},
            )
        profile.health_data_consent = True
        profile.save(update_fields=["health_data_consent"])
        action = "Einwilligung für private Verlaufsfotos erteilt"
    else:
        withdrawal_time = timezone.now()
        active_records = list(ConsentRecord.objects.filter(
            user=user,
            template=template,
            accepted=True,
            withdrawn_at__isnull=True,
        ))
        for record in active_records:
            record.withdrawn_at = withdrawal_time
            # save() deliberately triggers the patient-file synchronization signal,
            # preserving the withdrawal as a separate immutable audit event.
            record.save(update_fields=["withdrawn_at"])
        profile.health_data_consent = False
        profile.save(update_fields=["health_data_consent"])
        active = None
        action = "Einwilligung für private Verlaufsfotos widerrufen"

    AuditLog.objects.create(
        actor=user,
        action=action,
        entity_type="ConsentTemplate",
        entity_id=str(template.pk),
        metadata={"accepted": accepted, "version": template.version, "source": "mobile_app"},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({
        "ok": True,
        "health_data_consent": profile.health_data_consent,
        "consent_record_id": active.pk if active else None,
        "version": template.version,
    })
