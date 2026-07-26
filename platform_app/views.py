import io
from datetime import timedelta

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AppointmentForm
from .models import *


def module_enabled(key):
    return FeatureModule.objects.filter(key=key, enabled=True).exists()


def staff_required(view):
    return user_passes_test(lambda user: user.is_staff)(view)


def health(request):
    return JsonResponse(
        {
            "ok": True,
            "service": "A+ Esthetic Platform",
            "database": "connected",
            "time": timezone.now().isoformat(),
        }
    )


def manifest(request):
    return JsonResponse(
        {
            "name": "A+ Esthetic Beauty Club",
            "short_name": "A+ Esthetic",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f5f1eb",
            "theme_color": "#17212a",
            "lang": "de",
            "icons": [],
        }
    )


def service_worker(request):
    body = """const C='aplus-v4';self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/static/app.css','/static/app.js'])).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('fetch',e=>{if(e.request.method==='GET')e.respondWith(fetch(e.request).then(r=>{let c=r.clone();caches.open(C).then(x=>x.put(e.request,c));return r}).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))))});"""
    return HttpResponse(body, content_type="application/javascript")


@login_required
def dashboard(request):
    member, _ = MemberAccount.objects.get_or_create(user=request.user)
    wallet, _ = WalletAccount.objects.get_or_create(user=request.user)
    next_appointment = (
        Appointment.objects.filter(
            user=request.user,
            status__in=["requested", "confirmed"],
            starts_at__gte=timezone.now(),
        )
        .order_by("starts_at")
        .first()
    )
    context = {
        "member": member,
        "wallet": wallet,
        "next_appointment": next_appointment,
        "upcoming_reminders": Reminder.objects.filter(
            user=request.user, status="scheduled"
        ).order_by("scheduled_for")[:4],
        "packages": MemberPackage.objects.filter(
            user=request.user, status="active"
        )[:4],
        "recent_transactions": WalletTransaction.objects.filter(user=request.user)[:5],
    }
    return render(
        request,
        "app.html",
        {
            **context,
            "section": "dashboard",
            "page_title": "Übersicht",
            "page_subtitle": "Ihre persönliche A+ Übersicht",
        },
    )


@login_required
def club(request):
    if not module_enabled("membership"):
        raise Http404
    member, _ = MemberAccount.objects.get_or_create(user=request.user)
    wallet, _ = WalletAccount.objects.get_or_create(user=request.user)
    if request.method == "POST" and module_enabled("referrals"):
        email = request.POST.get("invited_email", "").strip()
        if email:
            code = (
                "APLUS-"
                + request.user.username[:8].upper().replace("@", "")
                + "-"
                + str(Referral.objects.count() + 1)
            )
            Referral.objects.create(
                referrer=request.user,
                code=code,
                invited_email=email,
                reward_coins=300,
            )
            messages.success(
                request,
                "Einladung gespeichert. Coins werden erst nach einem verifizierten ersten Besuch vergeben.",
            )
            return redirect("club")
    campaigns = Campaign.objects.filter(
        active=True, starts_at__lte=timezone.now(), ends_at__gte=timezone.now()
    )
    return render(
        request,
        "app.html",
        {
            "section": "club",
            "page_title": "A+ Beauty Club",
            "page_subtitle": "Membership, Gift Cards und Empfehlungen",
            "member": member,
            "wallet": wallet,
            "tiers": MembershipTier.objects.filter(active=True),
            "giftcards": GiftCard.objects.filter(purchaser=request.user),
            "referrals": Referral.objects.filter(referrer=request.user),
            "campaigns": campaigns,
        },
    )


@login_required
def beauty_assistant(request):
    if not module_enabled("ai"):
        raise Http404
    query = request.POST.get("question", "").strip() if request.method == "POST" else ""
    answer = ""
    if query:
        lowered = query.lower()
        if any(
            word in lowered
            for word in [
                "diagnose",
                "dosis",
                "dosierung",
                "behandlung empfehlen",
                "welche behandlung",
                "krankheit",
            ]
        ):
            answer = "Dabei kann der A+ Wissensassistent nicht helfen. Für Diagnose, Dosierung oder eine individuelle Behandlungsempfehlung ist eine persönliche ärztliche Beratung erforderlich."
        elif "botox" in lowered:
            answer = "Allgemeine Information: Vor einer medizinisch-ästhetischen Behandlung ist eine persönliche ärztliche Aufklärung notwendig. Die App kann weder Eignung noch Dosierung beurteilen. Sie können über die Terminseite eine Beratung anfragen."
        elif "laser" in lowered:
            answer = "Allgemeine Information: Vorbereitung und Abstände hängen von Gerät, Haut, Region und individueller Situation ab. Bitte verwenden Sie die von A+ Esthetic für Ihren Termin freigegebenen Hinweise oder kontaktieren Sie das Team."
        elif any(
            word in lowered for word in ["produkt", "serum", "creme", "inhaltsstoff"]
        ):
            answer = "Ich kann allgemeine, von A+ freigegebene Produktinformationen erklären. Für Hautreaktionen, medizinische Beschwerden oder individuelle Eignung wenden Sie sich bitte an qualifiziertes Fachpersonal."
        else:
            answer = "Ich kann allgemeine Informationen zu A+ Abläufen, Terminorganisation, Mitgliedschaft und freigegebenen Pflegehinweisen geben. Medizinische Diagnosen und individuelle Therapieempfehlungen sind ausgeschlossen."
    return render(
        request,
        "app.html",
        {
            "section": "assistant",
            "page_title": "A+ Beauty Wissensassistent",
            "page_subtitle": "Allgemeine Informationen, keine medizinische Beratung",
            "question": query,
            "answer": answer,
        },
    )


@login_required
def booking(request):
    if not module_enabled("booking"):
        raise Http404
    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    staff = form.cleaned_data.get("staff")
                    if staff:
                        type(staff).objects.select_for_update().get(pk=staff.pk)
                    appointment = form.save(user=request.user)
                Reminder.objects.create(
                    user=request.user,
                    title="Termin-Anfrage gesendet",
                    body=f"{appointment.service.name} am {appointment.starts_at:%d.%m.%Y um %H:%M}",
                    scheduled_for=timezone.now(),
                    status="sent",
                )
                messages.success(
                    request,
                    "Ihre Terminanfrage wurde gespeichert. A+ Esthetic bestätigt den Termin separat.",
                )
                return redirect("booking")
            except Exception as exc:
                form.add_error(None, str(exc))
    else:
        form = AppointmentForm()
    appointments = Appointment.objects.filter(user=request.user).order_by("-starts_at")[:20]
    return render(
        request,
        "app.html",
        {
            "section": "booking",
            "page_title": "Terminbuchung",
            "page_subtitle": "Anfrage und Warteliste",
            "form": form,
            "appointments": appointments,
            "services": Service.objects.filter(active=True),
        },
    )


@login_required
@require_POST
def join_waitlist(request):
    service = get_object_or_404(Service, pk=request.POST.get("service"))
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(days=30)
    WaitlistEntry.objects.create(
        user=request.user,
        service=service,
        preferred_from=start,
        preferred_until=end,
    )
    messages.success(request, "Sie wurden auf die Warteliste gesetzt.")
    return redirect("booking")


@login_required
def wallet(request):
    if not module_enabled("wallet"):
        raise Http404
    account, _ = WalletAccount.objects.get_or_create(user=request.user)
    return render(
        request,
        "app.html",
        {
            "section": "wallet",
            "page_title": "A+ Wallet & Rewards",
            "page_subtitle": "Ihre A+ Vorteile",
            "wallet": account,
            "transactions": WalletTransaction.objects.filter(user=request.user)[:30],
            "rewards": Reward.objects.filter(active=True),
            "packages": MemberPackage.objects.filter(user=request.user),
        },
    )


@login_required
@require_POST
def redeem_reward(request, reward_id):
    reward = get_object_or_404(Reward, pk=reward_id, active=True)
    reward.full_clean()
    with transaction.atomic():
        wallet = WalletAccount.objects.select_for_update().get(user=request.user)
        if wallet.coin_balance < reward.coin_cost:
            messages.error(request, "Nicht genügend A+ Coins.")
        elif reward.inventory is not None and reward.inventory < 1:
            messages.error(request, "Diese Prämie ist aktuell nicht verfügbar.")
        else:
            wallet.coin_balance -= reward.coin_cost
            wallet.save(update_fields=["coin_balance", "updated_at"])
            WalletTransaction.objects.create(
                user=request.user,
                kind="coin",
                direction="out",
                coin_amount=reward.coin_cost,
                description=f"Reward: {reward.name}",
            )
            if reward.inventory is not None:
                reward.inventory -= 1
                reward.save(update_fields=["inventory"])
            messages.success(request, "Reward erfolgreich reserviert.")
    return redirect("wallet")


@login_required
def passport(request):
    if not module_enabled("passport"):
        raise Http404
    return render(
        request,
        "app.html",
        {
            "section": "passport",
            "page_title": "Beauty Passport",
            "page_subtitle": "Ihr geschützter Verlauf",
            "entries": BeautyPassportEntry.objects.filter(
                user=request.user, visible_to_customer=True
            ),
            "documents": SecureDocument.objects.filter(user=request.user),
            "followups": FollowUp.objects.filter(user=request.user).order_by("-due_at"),
        },
    )


@login_required
def reminders(request):
    if not module_enabled("reminders"):
        raise Http404
    return render(
        request,
        "app.html",
        {
            "section": "reminders",
            "page_title": "Erinnerungen",
            "page_subtitle": "Ihre persönlichen Benachrichtigungen",
            "reminders": Reminder.objects.filter(user=request.user),
        },
    )


@login_required
@require_POST
def reminder_toggle(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, user=request.user)
    reminder.status = "dismissed" if reminder.status == "scheduled" else "scheduled"
    reminder.save(update_fields=["status"])
    return redirect("reminders")


@login_required
def chat(request):
    if not module_enabled("chat"):
        raise Http404
    thread = (
        Thread.objects.filter(user=request.user, status="open").first()
        or Thread.objects.create(user=request.user, subject="Anfrage an A+ Esthetic")
    )
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if body:
            Message.objects.create(thread=thread, sender=request.user, body=body)
            messages.success(request, "Nachricht sicher gespeichert.")
            return redirect("chat")
    return render(
        request,
        "app.html",
        {
            "section": "chat",
            "page_title": "Sichere Nachrichten",
            "page_subtitle": "Direkter Kontakt mit A+ Esthetic",
            "thread": thread,
        },
    )


@login_required
def profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        profile.phone = request.POST.get("phone", "")[:40]
        profile.marketing_consent = request.POST.get("marketing_consent") == "on"
        profile.health_data_consent = request.POST.get("health_data_consent") == "on"
        profile.save()
        messages.success(request, "Ihre Einstellungen wurden gespeichert.")
        return redirect("profile")
    return render(
        request,
        "app.html",
        {
            "section": "profile",
            "page_title": "Profil & Datenschutz",
            "page_subtitle": "Einwilligungen transparent verwalten",
            "profile": profile,
            "consents": ConsentRecord.objects.filter(user=request.user),
            "templates": ConsentTemplate.objects.filter(active=True),
        },
    )


@login_required
@require_POST
def accept_consent(request, template_id):
    template = get_object_or_404(ConsentTemplate, pk=template_id, active=True)
    ConsentRecord.objects.create(
        user=request.user,
        template=template,
        accepted=True,
        ip_address=request.META.get("REMOTE_ADDR"),
        evidence={"user_agent": request.META.get("HTTP_USER_AGENT", "")},
    )
    messages.success(request, "Einwilligung wurde protokolliert.")
    return redirect("profile")


@login_required
@require_POST
def withdraw_consent(request, record_id):
    record = get_object_or_404(
        ConsentRecord,
        pk=record_id,
        user=request.user,
        withdrawn_at__isnull=True,
    )
    record.withdrawn_at = timezone.now()
    record.accepted = False
    record.save(update_fields=["withdrawn_at", "accepted"])
    messages.success(request, "Einwilligung wurde widerrufen.")
    return redirect("profile")


@login_required
def member_qr(request):
    member, _ = MemberAccount.objects.get_or_create(user=request.user)
    image = qrcode.make(
        f"https://esthetic.smarbiz.sbs/checkin/{member.qr_token}"
    )
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return FileResponse(output, content_type="image/png")


@login_required
def protected_document(request, pk):
    document = get_object_or_404(SecureDocument, pk=pk)
    if document.user != request.user and not request.user.is_staff:
        raise Http404
    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.file.name.split("/")[-1],
    )


@login_required
@staff_required
def management(request):
    return render(
        request,
        "management_dashboard.html",
        {
            "modules": FeatureModule.objects.all(),
            "appointment_count": Appointment.objects.count(),
            "member_count": MemberAccount.objects.count(),
            "open_threads": Thread.objects.filter(status="open").count(),
            "pending_followups": FollowUp.objects.filter(
                status__in=["pending", "review"]
            ).count(),
            "recent_appointments": Appointment.objects.order_by("-created_at")[:12],
            "integrations": IntegrationConfig.objects.all(),
        },
    )


@login_required
@staff_required
@require_POST
def toggle_module(request, pk):
    module = get_object_or_404(FeatureModule, pk=pk)
    module.enabled = not module.enabled
    module.save(update_fields=["enabled", "updated_at"])
    AuditLog.objects.create(
        actor=request.user,
        action="Modulstatus geändert",
        entity_type="FeatureModule",
        entity_id=str(module.pk),
        metadata={"key": module.key, "enabled": module.enabled},
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    messages.success(
        request,
        f"{module.name_de}: {'aktiv' if module.enabled else 'deaktiviert'}.",
    )
    return redirect("management")
