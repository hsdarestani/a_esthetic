import json
import subprocess
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from platform_app.models import (
    Appointment,
    FeatureModule,
    FollowUp,
    GiftCard,
    MemberAccount,
    Reminder,
    Reward,
    Service,
    StaffMember,
    WalletAccount,
    WalletTransaction,
)

from .forms import (
    AccountDeletionForm,
    AppointmentChangeForm,
    BeautyPlanForm,
    CabinetProductForm,
    CallbackRequestForm,
    CheckoutForm,
    ComplaintForm,
    ConciergeRequestForm,
    FeedbackForm,
    FollowUpResponseForm,
    ProgressAlbumForm,
    ProgressPhotoForm,
    SlotBookingForm,
    SlotSearchForm,
)
from .models import *
from .passes import build_apple_pass, google_save_url
from .services import (
    available_slots,
    award_coins,
    build_user_export,
    create_slot_appointment,
    hash_progress_photo,
    integration_ready,
    log_action,
    queue_notification,
    redeem_reward,
    safe_assistant_answer,
)


def module_enabled(key):
    return FeatureModule.objects.filter(key=key, enabled=True).exists()


def staff_required(view):
    return user_passes_test(lambda user: user.is_authenticated and user.is_staff)(view)


def module_guard(key):
    def decorator(view):
        @login_required
        def wrapped(request, *args, **kwargs):
            if not module_enabled(key):
                raise Http404
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def _render(request, template, *, section, title, subtitle, **context):
    return render(request, template, {"section": section, "page_title": title, "page_subtitle": subtitle, **context})



@require_GET
def manifest_v2(request):
    return JsonResponse({
        "name": "A+ Esthetic Beauty Club",
        "short_name": "A+ Esthetic",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f6f1ea",
        "theme_color": "#17212a",
        "lang": "de",
        "categories": ["beauty", "lifestyle", "medical"],
        "icons": [{"src": "/static/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    })


@require_GET
def service_worker_v2(request):
    body = r'''const CACHE='aplus-complete-v1';
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/','/static/app.css','/static/experience.css','/static/app.js','/static/icon.svg'])).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(Promise.all([self.clients.claim(),caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))])));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.pathname.startsWith('/secure-admin/')||u.pathname.startsWith('/accounts/')||u.pathname.includes('/dokument/')||u.pathname.includes('/fotos/'))return;e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();if(r.ok)caches.open(CACHE).then(c=>c.put(e.request,copy));return r}).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))))});
self.addEventListener('push',e=>{let data={title:'A+ Esthetic',body:'Neue Information in der A+ App',url:'/'};try{data={...data,...e.data.json()}}catch(_){}e.waitUntil(self.registration.showNotification(data.title,{body:data.body,icon:'/static/icon.svg',badge:'/static/icon.svg',data:{url:data.url}}))});
self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{const url=e.notification.data?.url||'/';for(const client of list){if('focus'in client){client.navigate(url);return client.focus()}}return clients.openWindow(url)}))});'''
    return HttpResponse(body, content_type="application/javascript")


@login_required
def member_qr_v2(request):
    import io
    import qrcode
    member, _ = MemberAccount.objects.get_or_create(user=request.user)
    image = qrcode.make(request.build_absolute_uri(reverse("experience:checkin_token", args=[member.qr_token])))
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return FileResponse(output, content_type="image/png")


@module_guard("membership")
def member_center(request):
    member, _ = MemberAccount.objects.get_or_create(user=request.user)
    wallet, _ = WalletAccount.objects.get_or_create(user=request.user)
    subscription = MembershipSubscription.objects.filter(user=request.user).order_by("-created_at").first()
    benefits = MembershipBenefit.objects.filter(tier=member.tier, active=True) if member.tier else MembershipBenefit.objects.none()
    return _render(
        request,
        "experience/member.html",
        section="member_center",
        title="Mitgliedskarte & Membership",
        subtitle="Ihre von A+ Esthetic ausgegebenen Vorteile",
        member=member,
        wallet=wallet,
        subscription=subscription,
        benefits=benefits,
        passes={item.provider: item for item in MemberPass.objects.filter(user=request.user)},
        apple_ready=integration_ready("apple") and bool(settings.__dict__.get("SECRET_KEY")),
        google_ready=integration_ready("google") and bool(settings.__dict__.get("SECRET_KEY")),
    )


@module_guard("membership")
def apple_wallet_pass(request):
    try:
        output = build_apple_pass(request.user)
    except (ImproperlyConfigured, subprocess.SubprocessError, OSError) as exc:  # noqa: F821
        messages.error(request, str(exc))
        return redirect("experience:member_center")
    response = FileResponse(output, content_type="application/vnd.apple.pkpass")
    response["Content-Disposition"] = 'attachment; filename="a-plus-esthetic.pkpass"'
    return response


@module_guard("membership")
def google_wallet_pass(request):
    try:
        return redirect(google_save_url(request.user))
    except (ImproperlyConfigured, ValueError, KeyError) as exc:
        messages.error(request, str(exc))
        return redirect("experience:member_center")



@module_guard("wallet")
def wallet_center(request):
    wallet, _ = WalletAccount.objects.get_or_create(user=request.user)
    member, _ = MemberAccount.objects.get_or_create(user=request.user)
    rewards = Reward.objects.filter(active=True, is_medical_service=False)
    giftcards = GiftCard.objects.filter(purchaser=request.user).order_by("-created_at")
    subscriptions = MembershipSubscription.objects.filter(user=request.user).select_related("tier")
    return _render(
        request,
        "experience/wallet.html",
        section="wallet_center",
        title="A+ Wallet, Coins & Gift Cards",
        subtitle="Ausschließlich von A+ Esthetic ausgegeben",
        wallet=wallet,
        member=member,
        rewards=rewards,
        redemptions=RewardRedemption.objects.filter(user=request.user).select_related("reward"),
        transactions=request.user.wallet_transactions.all()[:60],
        giftcards=giftcards,
        subscriptions=subscriptions,
        packages=request.user.packages.select_related("definition"),
    )


@module_guard("wallet")
@require_POST
def redeem_reward_action(request, reward_id):
    reward = get_object_or_404(Reward, pk=reward_id, active=True, is_medical_service=False)
    try:
        redemption = redeem_reward(request.user, reward)
        messages.success(request, f"Reward reserviert. Code: {redemption.code}")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("experience:wallet_center")


@module_guard("giftcards")
@require_POST
def create_giftcard(request):
    try:
        amount = int(request.POST.get("amount_cents", "0"))
    except ValueError:
        amount = 0
    if amount < 1000 or amount > 100000:
        messages.error(request, "Bitte wählen Sie einen Betrag zwischen 10 € und 1.000 €.")
        return redirect("experience:wallet_center")
    wallet, _ = WalletAccount.objects.get_or_create(user=request.user)
    if wallet.balance_cents < amount:
        messages.error(request, "Für die Demo-Zahlung ist nicht genügend A+ Credit vorhanden. Eine externe Zahlung kann nach Provider-Konfiguration ergänzt werden.")
        return redirect("experience:wallet_center")
    with transaction.atomic():
        wallet = WalletAccount.objects.select_for_update().get(pk=wallet.pk)
        wallet.balance_cents -= amount
        wallet.save(update_fields=["balance_cents", "updated_at"])
        card = GiftCard.objects.create(
            code="APLUS-" + secrets.token_hex(5).upper(),
            purchaser=request.user,
            recipient_email=request.POST.get("recipient_email", "")[:254],
            initial_cents=amount,
            balance_cents=amount,
            status="active",
            expires_at=timezone.localdate() + timedelta(days=365),
        )
        GiftCardDelivery.objects.create(
            gift_card=card,
            recipient_name=request.POST.get("recipient_name", "")[:120],
            personal_message=request.POST.get("personal_message", "")[:2000],
            hidden_until_opened=request.POST.get("hidden_until_opened") == "on",
        )
        WalletTransaction.objects.create(
            user=request.user,
            kind="credit",
            direction="out",
            amount_cents=amount,
            description=f"Gift Card {card.code}",
            reference=f"giftcard:{card.pk}",
        )
    messages.success(request, f"Gift Card {card.code} wurde von A+ Esthetic erstellt.")
    return redirect("experience:wallet_center")


@module_guard("booking")
def booking_calendar(request):
    search_form = SlotSearchForm(request.GET or None)
    slots = []
    selected = None
    if search_form.is_valid():
        service = search_form.cleaned_data["service"]
        staff = search_form.cleaned_data["staff"]
        day = search_form.cleaned_data["day"]
        slots = available_slots(service, staff, day)
        selected = {"service": service, "staff": staff, "day": day}
    appointments = request.user.appointments.order_by("-starts_at")[:40]
    return _render(
        request,
        "experience/booking.html",
        section="booking_calendar",
        title="Intelligente Terminbuchung",
        subtitle="Freie Zeiten, Warteliste und Terminverwaltung",
        search_form=search_form,
        slots=slots,
        selected=selected,
        appointments=appointments,
        change_form=AppointmentChangeForm(),
    )


@module_guard("booking")
@require_POST
def book_slot(request):
    form = SlotBookingForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Die Buchungsdaten sind nicht vollständig.")
        return redirect("experience:booking_calendar")
    service = get_object_or_404(Service, pk=form.cleaned_data["service_id"], active=True, bookable_in_app=True)
    staff = get_object_or_404(StaffMember, pk=form.cleaned_data["staff_id"], active=True)
    starts_at = form.cleaned_data["starts_at"]
    if starts_at not in available_slots(service, staff, starts_at.date()):
        messages.error(request, "Dieser Termin ist nicht mehr verfügbar.")
        return redirect("experience:booking_calendar")
    try:
        appointment = create_slot_appointment(
            user=request.user,
            service=service,
            staff=staff,
            starts_at=starts_at,
            notes=form.cleaned_data["notes"],
            consent=form.cleaned_data["consent_acknowledged"],
        )
        award_coins(request.user, "booking", "Buchung über die A+ App", str(appointment.pk))
        messages.success(request, "Der Termin wurde gespeichert.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("experience:booking_calendar")


@module_guard("booking")
@require_POST
def appointment_change(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id, user=request.user)
    form = AppointmentChangeForm(request.POST)
    if form.is_valid():
        change = AppointmentChangeRequest.objects.create(
            appointment=appointment,
            request_type=form.cleaned_data["request_type"],
            requested_start=form.cleaned_data.get("requested_start"),
            delay_minutes=form.cleaned_data.get("delay_minutes") or 0,
            message=form.cleaned_data.get("message") or "",
        )
        if change.request_type == "cancel":
            policy = getattr(appointment.service, "booking_policy", None)
            deadline = appointment.starts_at - timedelta(hours=policy.cancellation_hours if policy else 24)
            if timezone.now() <= deadline:
                appointment.status = "cancelled"
                appointment.save(update_fields=["status", "updated_at"])
                change.status = "approved"
                change.handled_at = timezone.now()
                change.save(update_fields=["status", "handled_at", "updated_at"])
        queue_notification(request.user, "Terminanfrage aktualisiert", change.get_request_type_display(), sensitive=True)
        messages.success(request, "Ihre Anfrage wurde an A+ Esthetic übermittelt.")
    else:
        messages.error(request, "Bitte prüfen Sie die Angaben.")
    return redirect("experience:booking_calendar")


@module_guard("booking")
def appointment_ical(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id, user=request.user)
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//A+ Esthetic//Beauty Club//DE", "BEGIN:VEVENT",
        f"UID:aesthetic-{appointment.pk}@esthetic.smarbiz.sbs",
        f"DTSTAMP:{timezone.now().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{appointment.starts_at.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{appointment.ends_at.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:A+ Esthetic – {appointment.service.name}",
        "DESCRIPTION:Organisatorischer Termin. Medizinische Entscheidungen erfolgen erst nach persönlicher ärztlicher Aufklärung.",
        "END:VEVENT", "END:VCALENDAR", "",
    ])
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="aesthetic-termin-{appointment.pk}.ics"'
    return response


@staff_required
def checkin_token(request, token):
    member = get_object_or_404(MemberAccount, qr_token=token)
    appointment = Appointment.objects.filter(
        user=member.user,
        status__in=["requested", "confirmed"],
        starts_at__date=timezone.localdate(),
    ).order_by("starts_at").first()
    checkin = None
    if request.method == "POST" and appointment:
        checkin, _ = CheckIn.objects.update_or_create(
            appointment=appointment,
            defaults={"method": "qr", "checked_in_at": timezone.now(), "status": "arrived", "staff_notified_at": timezone.now()},
        )
        award_coins(member.user, "punctual", "Verifizierter Check-in", str(appointment.pk))
        log_action(request, "QR Check-in", checkin, {"appointment": appointment.pk})
        messages.success(request, "Check-in wurde registriert und das A+ Team informiert.")
    return _render(
        request,
        "experience/checkin.html",
        section="checkin",
        title="A+ Check-in",
        subtitle="Nur für autorisierte A+ Mitarbeitende",
        member=member,
        appointment=appointment,
        checkin=checkin or (getattr(appointment, "checkin", None) if appointment else None),
    )


@module_guard("before_after")
def photo_center(request):
    albums = ProgressAlbum.objects.filter(user=request.user).prefetch_related("photos")
    if request.method == "POST" and request.POST.get("action") == "album":
        form = ProgressAlbumForm(request.POST)
        if form.is_valid():
            album = form.save(commit=False)
            album.user = request.user
            album.save()
            messages.success(request, "Privates Fotoalbum wurde erstellt.")
            return redirect("experience:photo_center")
    else:
        form = ProgressAlbumForm()
    return _render(
        request,
        "experience/photos.html",
        section="photo_center",
        title="Vorher-Nachher & Verlauf",
        subtitle="Geschützte Fotos mit separater Marketingfreigabe",
        albums=albums,
        album_form=form,
        photo_form=ProgressPhotoForm(),
    )


@module_guard("before_after")
@require_POST
def upload_photo(request, album_id):
    album = get_object_or_404(ProgressAlbum, pk=album_id, user=request.user)
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.health_data_consent:
        messages.error(request, "Vor dem Foto-Upload ist eine Einwilligung zur Verarbeitung besonderer Daten erforderlich.")
        return redirect("experience:photo_center")
    form = ProgressPhotoForm(request.POST, request.FILES)
    if form.is_valid():
        photo = form.save(commit=False)
        photo.album = album
        photo.uploaded_by = request.user
        photo.save()
        hash_progress_photo(photo)
        messages.success(request, "Foto wurde geschützt gespeichert.")
    else:
        messages.error(request, "Das Foto konnte nicht gespeichert werden.")
    return redirect("experience:photo_center")


@login_required
def protected_progress_photo(request, photo_id):
    photo = get_object_or_404(ProgressPhoto, pk=photo_id)
    if photo.album.user_id != request.user.id and not request.user.is_staff:
        raise Http404
    return FileResponse(photo.image.open("rb"), content_type="image/jpeg")


@module_guard("followup")
def aftercare_center(request):
    assigned = AssignedAftercare.objects.filter(user=request.user).select_related("template", "appointment").prefetch_related("task_statuses__task")
    followups = request.user.followups.order_by("-due_at")
    return _render(
        request,
        "experience/aftercare.html",
        section="aftercare",
        title="Nachsorge & Follow-up",
        subtitle="Freigegebene Hinweise und direkter Kontakt mit A+ Esthetic",
        assigned_aftercare=assigned,
        followups=followups,
        response_form=FollowUpResponseForm(),
    )


@module_guard("followup")
@require_POST
def toggle_aftercare_task(request, status_id):
    status = get_object_or_404(AftercareTaskStatus, pk=status_id, assigned__user=request.user)
    status.completed = not status.completed
    status.completed_at = timezone.now() if status.completed else None
    status.save(update_fields=["completed", "completed_at", "updated_at"])
    all_complete = not status.assigned.task_statuses.filter(completed=False).exists()
    if all_complete and not status.assigned.completed_at:
        status.assigned.completed_at = timezone.now()
        status.assigned.save(update_fields=["completed_at", "updated_at"])
        award_coins(request.user, "aftercare", "Nachsorge-Checkliste abgeschlossen", str(status.assigned.pk))
    return redirect("experience:aftercare_center")


@module_guard("followup")
@require_POST
def respond_followup(request, followup_id):
    followup = get_object_or_404(FollowUp, pk=followup_id, user=request.user)
    form = FollowUpResponseForm(request.POST)
    if form.is_valid():
        followup.customer_response = {"text": form.cleaned_data["response"], "request_contact": form.cleaned_data["request_contact"]}
        followup.status = "review" if form.cleaned_data["request_contact"] else "answered"
        followup.requires_review = form.cleaned_data["request_contact"]
        followup.save(update_fields=["customer_response", "status", "requires_review"])
        messages.success(request, "Ihre Rückmeldung wurde an A+ Esthetic übermittelt.")
    return redirect("experience:aftercare_center")


@module_guard("beauty_plan")
def beauty_plans(request):
    if request.method == "POST":
        form = BeautyPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.user = request.user
            plan.save()
            messages.success(request, "Beauty Plan wurde als organisatorischer Entwurf erstellt.")
            return redirect("experience:beauty_plans")
    else:
        form = BeautyPlanForm()
    return _render(
        request,
        "experience/beauty_plans.html",
        section="beauty_plan",
        title="Persönlicher Beauty Plan",
        subtitle="Ziele, Budget und Journeys – keine medizinische Entscheidung",
        plans=BeautyPlan.objects.filter(user=request.user).prefetch_related("steps"),
        form=form,
    )


@module_guard("beauty_plan")
@require_POST
def toggle_plan_step(request, step_id):
    step = get_object_or_404(BeautyPlanStep, pk=step_id, plan__user=request.user)
    step.completed = not step.completed
    step.completed_at = timezone.now() if step.completed else None
    step.save(update_fields=["completed", "completed_at", "updated_at"])
    return redirect("experience:beauty_plans")


@module_guard("ai")
def assistant(request):
    answer = ""
    question = ""
    if request.method == "POST":
        question = request.POST.get("question", "").strip()[:4000]
        if question:
            profile = getattr(request.user, "profile", None)
            answer, conversation = safe_assistant_answer(request.user, question, getattr(profile, "preferred_language", "de"))
            if conversation.blocked_medical_request:
                messages.warning(request, "Die medizinische Anfrage wurde aus Sicherheitsgründen nicht beantwortet.")
    return _render(
        request,
        "experience/assistant.html",
        section="assistant_v2",
        title="A+ Beauty Wissensassistent",
        subtitle="Nur freigegebene Informationen, keine medizinische Beratung",
        question=question,
        answer=answer,
        history=AssistantConversation.objects.filter(user=request.user)[:10],
        articles=KnowledgeArticle.objects.filter(approved=True, active=True)[:8],
    )


@module_guard("cabinet")
def cabinet(request):
    if request.method == "POST":
        form = CabinetProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            messages.success(request, "Produkt wurde Ihrem Beauty Cabinet hinzugefügt.")
            return redirect("experience:cabinet")
    else:
        form = CabinetProductForm()
    return _render(
        request,
        "experience/cabinet.html",
        section="cabinet",
        title="Beauty Cabinet",
        subtitle="Produkte, Ablaufdaten und persönliche Routinen",
        products=CabinetProduct.objects.filter(user=request.user, active=True).prefetch_related("routine_steps"),
        routines=RoutineStep.objects.filter(user=request.user, active=True).select_related("product"),
        form=form,
    )


@module_guard("cabinet")
@require_POST
def remove_cabinet_product(request, product_id):
    product = get_object_or_404(CabinetProduct, pk=product_id, user=request.user)
    product.active = False
    product.save(update_fields=["active", "updated_at"])
    messages.success(request, "Produkt wurde archiviert.")
    return redirect("experience:cabinet")


def _cart(request):
    cart = request.session.setdefault("shop_cart", {})
    return {str(key): int(value) for key, value in cart.items() if int(value) > 0}


@module_guard("shop")
def shop(request):
    cart = _cart(request)
    products = ShopProduct.objects.filter(active=True).select_related("category")
    cart_products = ShopProduct.objects.filter(pk__in=cart.keys())
    cart_rows = [{"product": p, "quantity": cart.get(str(p.pk), 0), "line": p.price_cents * cart.get(str(p.pk), 0)} for p in cart_products]
    total = sum(row["line"] for row in cart_rows)
    return _render(
        request,
        "experience/shop.html",
        section="shop",
        title="A+ Shop",
        subtitle="Produkte, Gift Cards und Click & Collect",
        products=products,
        categories=ShopCategory.objects.filter(active=True),
        cart_rows=cart_rows,
        cart_total=total,
        checkout_form=CheckoutForm(),
        stripe_ready=bool(getattr(settings, "STRIPE_SECRET_KEY", "")),
    )


@module_guard("shop")
@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(ShopProduct, pk=product_id, active=True)
    cart = _cart(request)
    cart[str(product.pk)] = min(product.stock, cart.get(str(product.pk), 0) + 1)
    request.session["shop_cart"] = cart
    request.session.modified = True
    messages.success(request, f"{product.name} wurde hinzugefügt.")
    return redirect("experience:shop")


@module_guard("shop")
@require_POST
def checkout(request):
    cart = _cart(request)
    if not cart:
        messages.error(request, "Ihr Warenkorb ist leer.")
        return redirect("experience:shop")
    form = CheckoutForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Bitte prüfen Sie die Checkout-Daten.")
        return redirect("experience:shop")
    with transaction.atomic():
        products = list(ShopProduct.objects.select_for_update().filter(pk__in=cart.keys(), active=True))
        subtotal = sum(product.price_cents * cart.get(str(product.pk), 0) for product in products)
        wallet, _ = WalletAccount.objects.select_for_update().get_or_create(user=request.user)
        requested_credit = min(form.cleaned_data.get("use_credit_cents") or 0, wallet.balance_cents, subtotal)
        gift_used = 0
        gift = None
        gift_code = form.cleaned_data.get("giftcard_code", "").strip()
        if gift_code:
            gift = GiftCard.objects.select_for_update().filter(code=gift_code, status="active").first()
            if gift:
                gift_used = min(gift.balance_cents, subtotal - requested_credit)
        total = subtotal - requested_credit - gift_used
        order = form.save(commit=False)
        order.user = request.user
        order.subtotal_cents = subtotal
        order.credit_used_cents = requested_credit
        order.giftcard_used_cents = gift_used
        order.total_cents = total
        order.status = "paid" if total == 0 else "pending"
        order.payment_provider = "a-plus-credit" if total == 0 else "external-payment-required"
        order.save()
        for product in products:
            quantity = cart.get(str(product.pk), 0)
            if quantity > product.stock:
                raise ValidationError(f"Nicht genügend Bestand für {product.name}.")
            ShopOrderItem.objects.create(order=order, product=product, quantity=quantity, unit_price_cents=product.price_cents, line_total_cents=product.price_cents * quantity)
            if total == 0:
                product.stock -= quantity
                product.save(update_fields=["stock", "updated_at"])
        if requested_credit:
            wallet.balance_cents -= requested_credit
            wallet.save(update_fields=["balance_cents", "updated_at"])
            WalletTransaction.objects.create(user=request.user, kind="credit", direction="out", amount_cents=requested_credit, description=f"Shop-Bestellung {order.order_number}")
        if gift and gift_used:
            gift.balance_cents -= gift_used
            gift.status = "redeemed" if gift.balance_cents == 0 else "active"
            gift.save(update_fields=["balance_cents", "status"])
    request.session["shop_cart"] = {}
    messages.success(request, f"Bestellung {order.order_number} wurde angelegt." + (" Externe Zahlung ist noch erforderlich." if total else ""))
    return redirect("experience:shop")


@module_guard("gamification")
def gamification(request):
    active_challenges = Challenge.objects.filter(active=True, starts_at__lte=timezone.now(), ends_at__gte=timezone.now())
    participations = {p.challenge_id: p for p in ChallengeParticipation.objects.filter(user=request.user, challenge__in=active_challenges)}
    return _render(
        request,
        "experience/gamification.html",
        section="gamification",
        title="Challenges & Achievements",
        subtitle="Pflege, Lernen und Community – keine Behandlungsanreize",
        challenges=active_challenges,
        participations=participations,
        badges=UserBadge.objects.filter(user=request.user).select_related("badge"),
        quizzes=Quiz.objects.filter(active=True),
        attempts=QuizAttempt.objects.filter(user=request.user),
    )


@module_guard("gamification")
@require_POST
def join_challenge(request, challenge_id):
    challenge = get_object_or_404(Challenge, pk=challenge_id, active=True)
    ChallengeParticipation.objects.get_or_create(user=request.user, challenge=challenge)
    messages.success(request, "Challenge wurde gestartet.")
    return redirect("experience:gamification")


@module_guard("gamification")
@require_POST
def challenge_progress(request, challenge_id):
    participation = get_object_or_404(ChallengeParticipation, user=request.user, challenge_id=challenge_id)
    if not participation.completed_at:
        participation.progress = min(participation.challenge.target_count, participation.progress + 1)
        if participation.progress >= participation.challenge.target_count:
            participation.completed_at = timezone.now()
            coins = award_coins(request.user, "challenge", f"Challenge abgeschlossen: {participation.challenge.title}", str(participation.pk))
            if coins == 0 and participation.challenge.reward_coins:
                with transaction.atomic():
                    wallet = WalletAccount.objects.select_for_update().get(user=request.user)
                    wallet.coin_balance += participation.challenge.reward_coins
                    wallet.save(update_fields=["coin_balance", "updated_at"])
                    WalletTransaction.objects.create(user=request.user, kind="coin", direction="in", coin_amount=participation.challenge.reward_coins, description=f"Challenge: {participation.challenge.title}")
                participation.reward_granted = True
        participation.save()
    return redirect("experience:gamification")


@module_guard("communication")
def communication_center(request):
    callback_form = CallbackRequestForm(prefix="callback")
    if request.method == "POST" and request.POST.get("form_type") == "callback":
        callback_form = CallbackRequestForm(request.POST, prefix="callback")
        if callback_form.is_valid():
            item = callback_form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, "Rückrufwunsch wurde gespeichert.")
            return redirect("experience:communication_center")
    return _render(
        request,
        "experience/communication.html",
        section="communication",
        title="Kontakt & Support",
        subtitle="Sicherer Kontakt mit A+ Esthetic",
        callback_form=callback_form,
        callbacks=CallbackRequest.objects.filter(user=request.user),
        faqs=FAQ.objects.filter(active=True),
        threads=request.user.threads.all(),
    )


@module_guard("offers")
def offers_events(request):
    now = timezone.now()
    offers = Offer.objects.filter(active=True, starts_at__lte=now, ends_at__gte=now)
    events = BeautyEvent.objects.filter(active=True, starts_at__gte=now).prefetch_related("registrations")
    return _render(
        request,
        "experience/offers_events.html",
        section="offers",
        title="Angebote & Events",
        subtitle="Ausschließlich von A+ Esthetic herausgegeben",
        offers=offers,
        events=events,
        registrations=EventRegistration.objects.filter(user=request.user),
    )


@module_guard("events")
@require_POST
def register_event(request, event_id):
    event = get_object_or_404(BeautyEvent, pk=event_id, active=True)
    count = event.registrations.exclude(status="cancelled").count()
    status = "registered" if count < event.capacity else "waitlist"
    EventRegistration.objects.update_or_create(event=event, user=request.user, defaults={"status": status, "guest_name": request.POST.get("guest_name", "")[:120]})
    messages.success(request, "Anmeldung wurde gespeichert." if status == "registered" else "Sie wurden auf die Event-Warteliste gesetzt.")
    return redirect("experience:offers_events")


@module_guard("content")
def content_library(request):
    articles = ContentArticle.objects.filter(active=True, approved=True).order_by("-published_at", "title")
    saved_ids = set(SavedContent.objects.filter(user=request.user).values_list("article_id", flat=True))
    return _render(
        request,
        "experience/content.html",
        section="content",
        title="Inhalte & Weiterbildung",
        subtitle="Von A+ Esthetic freigegebene Informationen",
        articles=articles,
        saved_ids=saved_ids,
        quizzes=Quiz.objects.filter(active=True),
    )


@module_guard("content")
@require_POST
def save_content(request, article_id):
    article = get_object_or_404(ContentArticle, pk=article_id, active=True, approved=True)
    saved, created = SavedContent.objects.get_or_create(user=request.user, article=article)
    if not created:
        saved.delete()
    return redirect("experience:content_library")


@module_guard("feedback")
def feedback_center(request):
    feedback_form = FeedbackForm(prefix="feedback", user=request.user)
    complaint_form = ComplaintForm(prefix="complaint")
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "feedback":
            feedback_form = FeedbackForm(request.POST, prefix="feedback", user=request.user)
            if feedback_form.is_valid():
                item = feedback_form.save(commit=False)
                item.user = request.user
                item.save()
                award_coins(request.user, "review", "Verifiziertes Feedback eingereicht", str(item.pk))
                messages.success(request, "Vielen Dank für Ihre Rückmeldung.")
                return redirect("experience:feedback_center")
        elif form_type == "complaint":
            complaint_form = ComplaintForm(request.POST, prefix="complaint")
            if complaint_form.is_valid():
                item = complaint_form.save(commit=False)
                item.user = request.user
                item.save()
                messages.success(request, "Ihre Anfrage wurde vertraulich an das A+ Management übermittelt.")
                return redirect("experience:feedback_center")
    return _render(
        request,
        "experience/feedback.html",
        section="feedback",
        title="Feedback & Anliegen",
        subtitle="Bewertungen, Umfragen und transparente Bearbeitung",
        feedback_form=feedback_form,
        complaint_form=complaint_form,
        feedback_entries=Feedback.objects.filter(user=request.user),
        complaints=Complaint.objects.filter(user=request.user),
        surveys=Survey.objects.filter(active=True, starts_at__lte=timezone.now(), ends_at__gte=timezone.now()),
    )


@module_guard("concierge")
def concierge(request):
    if request.method == "POST":
        form = ConciergeRequestForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, "Ihre A+ Concierge-Anfrage wurde gespeichert.")
            return redirect("experience:concierge")
    else:
        form = ConciergeRequestForm()
    return _render(
        request,
        "experience/concierge.html",
        section="concierge",
        title="A+ Premium Support",
        subtitle="Organisatorische VIP- und Concierge-Anfragen",
        form=form,
        requests=ConciergeRequest.objects.filter(user=request.user),
    )


@module_guard("privacy")
def privacy_center(request):
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    deletion_form = AccountDeletionForm()
    if request.method == "POST" and request.POST.get("form_type") == "preferences":
        for field in ["push_enabled", "email_enabled", "appointment_reminders", "aftercare_reminders", "product_reminders", "membership_messages", "marketing_messages", "hide_sensitive_text"]:
            setattr(preferences, field, request.POST.get(field) == "on")
        preferences.save()
        messages.success(request, "Benachrichtigungseinstellungen wurden gespeichert.")
        return redirect("experience:privacy_center")
    return _render(
        request,
        "experience/privacy.html",
        section="privacy",
        title="Datenschutz-Center",
        subtitle="Einwilligungen, Geräte, Export und Löschanfragen",
        preferences=preferences,
        devices=DeviceSession.objects.filter(user=request.user),
        exports=DataExportRequest.objects.filter(user=request.user),
        deletions=AccountDeletionRequest.objects.filter(user=request.user),
        deletion_form=deletion_form,
        subscriptions=PushSubscription.objects.filter(user=request.user, active=True),
        vapid_public_key=getattr(settings, "WEBPUSH_VAPID_PUBLIC_KEY", ""),
    )


@module_guard("privacy")
@require_POST
def request_export(request):
    export = DataExportRequest.objects.create(user=request.user, status="processing")
    stream = build_user_export(request.user)
    from django.core.files.base import ContentFile
    export.export_file.save(f"a-plus-export-{request.user.pk}.zip", ContentFile(stream.read()))
    export.status = "ready"
    export.completed_at = timezone.now()
    export.expires_at = timezone.now() + timedelta(days=7)
    export.save(update_fields=["status", "completed_at", "expires_at", "updated_at"])
    messages.success(request, "Ihre Datenkopie wurde erstellt und steht sieben Tage bereit.")
    return redirect("experience:privacy_center")


@module_guard("privacy")
def download_export(request, export_id):
    export = get_object_or_404(DataExportRequest, pk=export_id, user=request.user, status="ready")
    if export.expires_at and export.expires_at < timezone.now():
        raise Http404
    return FileResponse(export.export_file.open("rb"), as_attachment=True, filename="a-plus-esthetic-daten.zip")


@module_guard("privacy")
@require_POST
def request_deletion(request):
    form = AccountDeletionForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.user = request.user
        item.status = "identity_check"
        item.save()
        messages.success(request, "Ihre Löschanfrage wurde registriert. Gesetzliche Aufbewahrungspflichten werden separat geprüft.")
    else:
        messages.error(request, "Bitte bestätigen Sie die Löschanfrage.")
    return redirect("experience:privacy_center")


@module_guard("privacy")
@require_POST
def revoke_device(request, device_id):
    device = get_object_or_404(DeviceSession, pk=device_id, user=request.user)
    device.revoked_at = timezone.now()
    device.save(update_fields=["revoked_at", "updated_at"])
    messages.success(request, "Gerät wurde abgemeldet.")
    return redirect("experience:privacy_center")


@login_required
@require_POST
def push_subscribe(request):
    try:
        payload = json.loads(request.body)
        keys = payload["keys"]
        subscription, _ = PushSubscription.objects.update_or_create(
            endpoint=payload["endpoint"],
            defaults={"user": request.user, "p256dh": keys["p256dh"], "auth": keys["auth"], "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300], "active": True},
        )
        return JsonResponse({"ok": True, "id": subscription.pk})
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False, "error": "Ungültige Push-Daten"}, status=400)


@staff_required
def management_catalog(request):
    model_counts = {
        "Mitgliedsvorteile": MembershipBenefit.objects.count(),
        "Wallet-Pässe": MemberPass.objects.count(),
        "Check-ins": CheckIn.objects.count(),
        "Fotoalben": ProgressAlbum.objects.count(),
        "Aftercare-Pläne": AssignedAftercare.objects.count(),
        "Beauty-Pläne": BeautyPlan.objects.count(),
        "Cabinet-Produkte": CabinetProduct.objects.count(),
        "Shop-Bestellungen": ShopOrder.objects.count(),
        "Challenges": Challenge.objects.count(),
        "Events": BeautyEvent.objects.count(),
        "Feedbacks": Feedback.objects.count(),
        "Datenschutzanfragen": DataExportRequest.objects.count() + AccountDeletionRequest.objects.count(),
    }
    integrations = IntegrationConfig.objects.all()
    return _render(
        request,
        "experience/management.html",
        section="management_catalog",
        title="A+ Management – Vollständiger Modulkatalog",
        subtitle="Status, externe Credentials und operative Daten",
        modules=FeatureModule.objects.all(),
        model_counts=model_counts,
        integrations=integrations,
        recent_orders=ShopOrder.objects.order_by("-created_at")[:10],
        recent_complaints=Complaint.objects.order_by("-created_at")[:10],
        recent_checkins=CheckIn.objects.order_by("-checked_in_at")[:10],
    )


# Mobile/web API. It exposes only the authenticated user's data and no medical decision endpoint.
@login_required
@require_GET
def api_modules(request):
    return JsonResponse({"modules": list(FeatureModule.objects.filter(enabled=True, customer_visible=True).values("key", "name_de", "description_de", "sort_order"))})


@login_required
@require_GET
def api_dashboard(request):
    member, _ = MemberAccount.objects.get_or_create(user=request.user)
    wallet, _ = WalletAccount.objects.get_or_create(user=request.user)
    next_appointment = request.user.appointments.filter(status__in=["requested", "confirmed"], starts_at__gte=timezone.now()).order_by("starts_at").first()
    return JsonResponse({
        "member": {"number": member.member_number, "tier": member.tier.name if member.tier else "A+ Member", "status": member.status},
        "wallet": {"credit_cents": wallet.balance_cents, "coins": wallet.coin_balance},
        "next_appointment": None if not next_appointment else {"id": next_appointment.pk, "service": next_appointment.service.name, "starts_at": next_appointment.starts_at.isoformat(), "status": next_appointment.status},
        "packages": list(request.user.packages.filter(status="active").values("id", "remaining_sessions", "expires_at", "definition__name")),
        "reminders": list(request.user.reminders.filter(status="scheduled").values("id", "title", "body", "scheduled_for", "channel")[:10]),
    })


@login_required
@require_GET
def api_slots(request):
    service = get_object_or_404(Service, pk=request.GET.get("service"), active=True)
    staff = get_object_or_404(StaffMember, pk=request.GET.get("staff"), active=True)
    try:
        day = datetime.strptime(request.GET.get("day", ""), "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"error": "Ungültiges Datum"}, status=400)
    return JsonResponse({"slots": [slot.isoformat() for slot in available_slots(service, staff, day)]})


@login_required
@require_GET
def api_wallet(request):
    wallet, _ = WalletAccount.objects.get_or_create(user=request.user)
    return JsonResponse({
        "credit_cents": wallet.balance_cents,
        "coins": wallet.coin_balance,
        "transactions": list(request.user.wallet_transactions.values("id", "kind", "direction", "amount_cents", "coin_amount", "description", "created_at")[:50]),
        "redemptions": list(request.user.reward_redemptions.values("id", "code", "coins_spent", "status", "reward__name", "created_at")[:50]),
    })


@login_required
@require_GET
def api_passport(request):
    return JsonResponse({
        "entries": list(request.user.passport_entries.filter(visible_to_customer=True).values()),
        "documents": list(request.user.secure_documents.values("id", "title", "category", "created_at")),
        "followups": list(request.user.followups.values("id", "title", "due_at", "status", "requires_review")),
    })
