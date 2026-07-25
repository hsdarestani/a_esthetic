import secrets
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .storage import private_storage


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class APlusIssuedModel(models.Model):
    issuer = models.CharField(max_length=80, default="A+ Esthetic", editable=False)

    class Meta:
        abstract = True


class MembershipBenefit(APlusIssuedModel, TimestampedModel):
    tier = models.ForeignKey("platform_app.MembershipTier", on_delete=models.CASCADE, related_name="benefits")
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    benefit_type = models.CharField(max_length=30, choices=[
        ("service", "Servicevorteil von A+ Esthetic"),
        ("product", "Produktvorteil von A+ Esthetic"),
        ("priority", "Organisatorische Priorität"),
        ("event", "A+ Eventzugang"),
        ("support", "A+ Supportvorteil"),
    ])
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    is_medical_reward = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["tier__priority", "sort_order", "title"]
        verbose_name = "Mitgliedsvorteil"
        verbose_name_plural = "Mitgliedsvorteile"

    def clean(self):
        if self.is_medical_reward:
            raise ValidationError("Medizinische Leistungen dürfen nicht als Mitgliedsvorteil ausgegeben werden.")

    def __str__(self):
        return f"{self.tier}: {self.title}"


class MembershipSubscription(APlusIssuedModel, TimestampedModel):
    STATUS = [("active", "Aktiv"), ("paused", "Pausiert"), ("cancelled", "Gekündigt"), ("expired", "Abgelaufen")]
    INTERVAL = [("monthly", "Monatlich"), ("yearly", "Jährlich")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership_subscriptions")
    tier = models.ForeignKey("platform_app.MembershipTier", on_delete=models.PROTECT)
    interval = models.CharField(max_length=12, choices=INTERVAL, default="monthly")
    status = models.CharField(max_length=15, choices=STATUS, default="active")
    starts_on = models.DateField(default=timezone.localdate)
    renews_on = models.DateField(null=True, blank=True)
    paused_until = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    external_payment_reference = models.CharField(max_length=140, blank=True)

    def __str__(self):
        return f"{self.user} – {self.tier} – {self.get_status_display()}"


class MemberPass(APlusIssuedModel, TimestampedModel):
    PROVIDER = [("apple", "Apple Wallet"), ("google", "Google Wallet")]
    STATUS = [("pending", "Konfiguration erforderlich"), ("active", "Aktiv"), ("revoked", "Widerrufen"), ("failed", "Fehlgeschlagen")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet_passes")
    provider = models.CharField(max_length=10, choices=PROVIDER)
    serial_number = models.CharField(max_length=80, unique=True, default=secrets.token_urlsafe, editable=False)
    external_object_id = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=15, choices=STATUS, default="pending")
    last_error = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "provider")]

    def __str__(self):
        return f"{self.user} – {self.get_provider_display()}"


class CoinRule(APlusIssuedModel, TimestampedModel):
    EVENT = [
        ("purchase_product", "Produktkauf"),
        ("booking", "Buchung über die App"),
        ("punctual", "Pünktliches Erscheinen"),
        ("profile", "Profil vervollständigt"),
        ("referral", "Verifizierte Empfehlung"),
        ("review", "Verifiziertes Feedback"),
        ("quiz", "Quiz abgeschlossen"),
        ("aftercare", "Nachsorge abgeschlossen"),
        ("challenge", "Challenge abgeschlossen"),
        ("off_peak", "Organisatorische Randzeit"),
    ]
    event = models.CharField(max_length=30, choices=EVENT, unique=True)
    coins = models.PositiveIntegerField(default=0)
    daily_limit = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    medical_treatment_count_based = models.BooleanField(default=False, editable=False)

    def clean(self):
        if self.medical_treatment_count_based:
            raise ValidationError("Coins dürfen nicht die Häufigkeit medizinischer Behandlungen belohnen.")

    def __str__(self):
        return f"{self.get_event_display()}: {self.coins} Coins"


class RewardRedemption(APlusIssuedModel, TimestampedModel):
    STATUS = [("reserved", "Reserviert"), ("issued", "Ausgegeben"), ("cancelled", "Storniert")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reward_redemptions")
    reward = models.ForeignKey("platform_app.Reward", on_delete=models.PROTECT)
    coins_spent = models.PositiveIntegerField()
    status = models.CharField(max_length=15, choices=STATUS, default="reserved")
    code = models.CharField(max_length=32, unique=True, editable=False)
    issued_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = "RWD-" + secrets.token_hex(6).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class GiftCardDelivery(APlusIssuedModel, TimestampedModel):
    gift_card = models.OneToOneField("platform_app.GiftCard", on_delete=models.CASCADE, related_name="delivery")
    recipient_name = models.CharField(max_length=120, blank=True)
    personal_message = models.TextField(blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    hidden_until_opened = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Versand {self.gift_card.code}"


class PackageUsage(APlusIssuedModel, TimestampedModel):
    member_package = models.ForeignKey("platform_app.MemberPackage", on_delete=models.PROTECT, related_name="usages")
    appointment = models.ForeignKey("platform_app.Appointment", null=True, blank=True, on_delete=models.SET_NULL)
    sessions_used = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="recorded_package_usages")

    def clean(self):
        if self.member_package_id and self.sessions_used > self.member_package.remaining_sessions:
            raise ValidationError("Nicht genügend Sitzungen im Paket verfügbar.")

    def __str__(self):
        return f"{self.member_package} – {self.sessions_used}"


class BookingPolicy(APlusIssuedModel, TimestampedModel):
    service = models.OneToOneField("platform_app.Service", on_delete=models.CASCADE, related_name="booking_policy")
    minimum_notice_hours = models.PositiveIntegerField(default=2)
    maximum_days_ahead = models.PositiveIntegerField(default=180)
    cancellation_hours = models.PositiveIntegerField(default=24)
    reschedule_hours = models.PositiveIntegerField(default=24)
    deposit_cents = models.PositiveIntegerField(default=0)
    allow_same_day = models.BooleanField(default=False)
    allow_booking_for_other = models.BooleanField(default=False)
    allow_multiple_services = models.BooleanField(default=False)
    external_confirmation_required = models.BooleanField(default=False)

    def __str__(self):
        return f"Buchungsregeln – {self.service}"


class AppointmentChangeRequest(TimestampedModel):
    TYPE = [("cancel", "Stornierung"), ("reschedule", "Verschiebung"), ("late", "Verspätung"), ("on_way", "Unterwegs")]
    STATUS = [("open", "Offen"), ("approved", "Bestätigt"), ("declined", "Abgelehnt"), ("closed", "Erledigt")]
    appointment = models.ForeignKey("platform_app.Appointment", on_delete=models.CASCADE, related_name="change_requests")
    request_type = models.CharField(max_length=15, choices=TYPE)
    requested_start = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    delay_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=15, choices=STATUS, default="open")
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="handled_appointment_changes")
    handled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.appointment} – {self.get_request_type_display()}"


class CheckIn(TimestampedModel):
    METHOD = [("qr", "QR-Code"), ("staff", "A+ Team"), ("manual", "Manuell")]
    appointment = models.OneToOneField("platform_app.Appointment", on_delete=models.CASCADE, related_name="checkin")
    method = models.CharField(max_length=10, choices=METHOD, default="qr")
    checked_in_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[("arrived", "Angekommen"), ("waiting", "Wartet"), ("called", "Aufgerufen"), ("closed", "Abgeschlossen")], default="arrived")
    staff_notified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Check-in {self.appointment}"


class WaitlistOffer(TimestampedModel):
    STATUS = [("sent", "Gesendet"), ("accepted", "Angenommen"), ("expired", "Abgelaufen"), ("declined", "Abgelehnt")]
    waitlist_entry = models.ForeignKey("platform_app.WaitlistEntry", on_delete=models.CASCADE, related_name="offers")
    offered_start = models.DateTimeField()
    expires_at = models.DateTimeField()
    token = models.CharField(max_length=80, unique=True, default=secrets.token_urlsafe, editable=False)
    status = models.CharField(max_length=15, choices=STATUS, default="sent")

    def __str__(self):
        return f"Wartelistenangebot {self.offered_start:%d.%m.%Y %H:%M}"


class ProgressAlbum(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progress_albums")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    private = models.BooleanField(default=True)
    marketing_use_allowed = models.BooleanField(default=False)
    marketing_consent_record = models.ForeignKey("platform_app.ConsentRecord", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.title


class ProgressPhoto(TimestampedModel):
    KIND = [("before", "Vorher"), ("after", "Nachher"), ("progress", "Verlauf")]
    album = models.ForeignKey(ProgressAlbum, on_delete=models.CASCADE, related_name="photos")
    kind = models.CharField(max_length=12, choices=KIND)
    image = models.ImageField(upload_to="progress/%Y/%m/", storage=private_storage)
    taken_at = models.DateTimeField(default=timezone.now)
    angle = models.CharField(max_length=40, blank=True)
    lighting_note = models.CharField(max_length=120, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_progress_photos")
    sha256 = models.CharField(max_length=64, blank=True, editable=False)
    visible_to_customer = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.album} – {self.get_kind_display()}"


class AftercareTemplate(APlusIssuedModel, TimestampedModel):
    service = models.ForeignKey("platform_app.Service", on_delete=models.CASCADE, related_name="aftercare_templates")
    title = models.CharField(max_length=180)
    introduction = models.TextField(blank=True)
    approved_by = models.CharField(max_length=140, blank=True, help_text="Interne fachliche Freigabe; keine automatische medizinische Empfehlung")
    version = models.CharField(max_length=20, default="1.0")
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("service", "version")]

    def __str__(self):
        return f"{self.service} – {self.title} v{self.version}"


class AftercareTask(APlusIssuedModel, TimestampedModel):
    template = models.ForeignKey(AftercareTemplate, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=15, choices=[("do", "Empfohlen"), ("avoid", "Vermeiden"), ("contact", "A+ kontaktieren")])
    offset_hours = models.IntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=100)
    warning_sign = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class AssignedAftercare(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assigned_aftercare")
    appointment = models.ForeignKey("platform_app.Appointment", on_delete=models.CASCADE, related_name="assigned_aftercare")
    template = models.ForeignKey(AftercareTemplate, on_delete=models.PROTECT)
    starts_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("appointment", "template")]


class AftercareTaskStatus(TimestampedModel):
    assigned = models.ForeignKey(AssignedAftercare, on_delete=models.CASCADE, related_name="task_statuses")
    task = models.ForeignKey(AftercareTask, on_delete=models.PROTECT)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("assigned", "task")]


class BeautyPlan(APlusIssuedModel, TimestampedModel):
    STATUS = [("draft", "Entwurf"), ("active", "Aktiv"), ("completed", "Abgeschlossen"), ("archived", "Archiviert")]
    JOURNEY = [("custom", "Individuell"), ("wedding", "Wedding"), ("birthday", "Birthday Glow"), ("summer", "Summer"), ("winter", "Winter Skin"), ("travel", "Travel"), ("photoshoot", "Photoshoot"), ("event", "Special Event"), ("hair", "Hair Recovery"), ("skin", "Skin Reset")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="beauty_plans")
    title = models.CharField(max_length=180)
    journey_type = models.CharField(max_length=20, choices=JOURNEY, default="custom")
    goal = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    monthly_budget_cents = models.PositiveIntegerField(default=0)
    annual_budget_cents = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=15, choices=STATUS, default="draft")
    approved_by_staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_beauty_plans")
    approved_at = models.DateTimeField(null=True, blank=True)
    medical_decision_support = models.BooleanField(default=False, editable=False)

    def clean(self):
        if self.medical_decision_support:
            raise ValidationError("Beauty-Pläne dürfen keine medizinischen Entscheidungen automatisieren.")

    @property
    def progress_percent(self):
        total = self.steps.count()
        if not total:
            return 0
        return round(self.steps.filter(completed=True).count() * 100 / total)

    def __str__(self):
        return self.title


class BeautyPlanStep(APlusIssuedModel, TimestampedModel):
    plan = models.ForeignKey(BeautyPlan, on_delete=models.CASCADE, related_name="steps")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    due_on = models.DateField(null=True, blank=True)
    step_type = models.CharField(max_length=20, choices=[("care", "Pflege"), ("product", "Produkt"), ("consultation", "Beratung anfragen"), ("appointment", "Organisatorischer Termin"), ("content", "Lerninhalt")])
    estimated_cost_cents = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "due_on", "id"]


class KnowledgeArticle(APlusIssuedModel, TimestampedModel):
    CATEGORY = [("service", "A+ Leistungen"), ("product", "Produkte"), ("care", "Freigegebene Pflegeinformation"), ("process", "Abläufe"), ("membership", "Membership"), ("safety", "Sicherheit")]
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY)
    summary = models.TextField(blank=True)
    body = models.TextField()
    language = models.CharField(max_length=10, default="de")
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_knowledge_articles")
    approved_at = models.DateTimeField(null=True, blank=True)
    medical_advice = models.BooleanField(default=False, editable=False)
    active = models.BooleanField(default=True)

    def clean(self):
        if self.medical_advice:
            raise ValidationError("Die Wissensdatenbank darf keine individuelle medizinische Beratung enthalten.")

    def __str__(self):
        return self.title


class AssistantConversation(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_conversations")
    question = models.TextField()
    answer = models.TextField()
    language = models.CharField(max_length=10, default="de")
    blocked_medical_request = models.BooleanField(default=False)
    handed_to_staff = models.BooleanField(default=False)
    provider = models.CharField(max_length=30, default="approved-knowledge")
    safety_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class CabinetProduct(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cabinet_products")
    name = models.CharField(max_length=180)
    brand = models.CharField(max_length=120, blank=True)
    barcode = models.CharField(max_length=64, blank=True)
    category = models.CharField(max_length=80, blank=True)
    opened_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    pao_months = models.PositiveIntegerField(default=0)
    estimated_empty_on = models.DateField(null=True, blank=True)
    personal_note = models.TextField(blank=True)
    personal_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)
    linked_shop_product = models.ForeignKey("ShopProduct", null=True, blank=True, on_delete=models.SET_NULL)

    def clean(self):
        if self.personal_rating is not None and not 1 <= self.personal_rating <= 5:
            raise ValidationError("Bewertung muss zwischen 1 und 5 liegen.")

    def __str__(self):
        return self.name


class RoutineStep(TimestampedModel):
    PERIOD = [("morning", "Morgen"), ("evening", "Abend"), ("weekly", "Wöchentlich")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="routine_steps")
    product = models.ForeignKey(CabinetProduct, on_delete=models.CASCADE, related_name="routine_steps")
    period = models.CharField(max_length=12, choices=PERIOD)
    weekdays = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["period", "sort_order"]


class ShopCategory(APlusIssuedModel, TimestampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Shop-Kategorie"
        verbose_name_plural = "Shop-Kategorien"

    def __str__(self):
        return self.name


class ShopProduct(APlusIssuedModel, TimestampedModel):
    category = models.ForeignKey(ShopCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    ingredients = models.TextField(blank=True)
    price_cents = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="shop/%Y/%m/", blank=True)
    active = models.BooleanField(default=True)
    click_collect = models.BooleanField(default=True)
    shipping = models.BooleanField(default=True)
    subscription_available = models.BooleanField(default=False)
    medically_prescribed = models.BooleanField(default=False, editable=False)

    def clean(self):
        if self.medically_prescribed:
            raise ValidationError("Verschreibungspflichtige oder ärztlich verordnete Produkte werden nicht über diesen Shop verkauft.")

    def __str__(self):
        return self.name


class ShopOrder(TimestampedModel):
    STATUS = [("draft", "Entwurf"), ("pending", "Zahlung offen"), ("paid", "Bezahlt"), ("ready", "Abholbereit"), ("shipped", "Versendet"), ("completed", "Abgeschlossen"), ("cancelled", "Storniert")]
    DELIVERY = [("collect", "Click & Collect"), ("shipping", "Versand")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shop_orders")
    order_number = models.CharField(max_length=32, unique=True, editable=False)
    status = models.CharField(max_length=15, choices=STATUS, default="draft")
    delivery_method = models.CharField(max_length=12, choices=DELIVERY, default="collect")
    subtotal_cents = models.PositiveIntegerField(default=0)
    credit_used_cents = models.PositiveIntegerField(default=0)
    giftcard_used_cents = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField(default=0)
    payment_provider = models.CharField(max_length=30, blank=True)
    payment_reference = models.CharField(max_length=140, blank=True)
    shipping_address = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = "ORD-" + secrets.token_hex(6).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number


class ShopOrderItem(TimestampedModel):
    order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(ShopProduct, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price_cents = models.PositiveIntegerField()
    line_total_cents = models.PositiveIntegerField()

    def save(self, *args, **kwargs):
        self.line_total_cents = self.quantity * self.unit_price_cents
        super().save(*args, **kwargs)


class Challenge(APlusIssuedModel, TimestampedModel):
    TYPE = [("care", "Pflegeroutine"), ("learning", "Lernen"), ("profile", "Profil"), ("aftercare", "Nachsorge"), ("referral", "Empfehlung"), ("seasonal", "Saisonal")]
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    challenge_type = models.CharField(max_length=20, choices=TYPE)
    target_count = models.PositiveIntegerField(default=1)
    reward_coins = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    encourages_medical_frequency = models.BooleanField(default=False, editable=False)

    def clean(self):
        if self.encourages_medical_frequency:
            raise ValidationError("Challenges dürfen nicht zu häufigeren medizinischen Behandlungen motivieren.")

    def __str__(self):
        return self.title


class ChallengeParticipation(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_participations")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="participations")
    progress = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_granted = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "challenge")]


class Badge(APlusIssuedModel, TimestampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=32, default="✦")
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class UserBadge(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    awarded_for = models.CharField(max_length=180, blank=True)

    class Meta:
        unique_together = [("user", "badge")]


class Quiz(APlusIssuedModel, TimestampedModel):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    reward_coins = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class QuizQuestion(TimestampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    question = models.TextField()
    options = models.JSONField(default=list)
    correct_index = models.PositiveSmallIntegerField()
    explanation = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "id"]


class QuizAttempt(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    answers = models.JSONField(default=dict)
    score = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    coins_granted = models.BooleanField(default=False)


class CallbackRequest(TimestampedModel):
    STATUS = [("open", "Offen"), ("scheduled", "Eingeplant"), ("completed", "Erledigt"), ("cancelled", "Storniert")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="callback_requests")
    subject = models.CharField(max_length=180)
    preferred_time = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=40)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS, default="open")


class FAQ(APlusIssuedModel, TimestampedModel):
    question = models.CharField(max_length=220)
    answer = models.TextField()
    category = models.CharField(max_length=80, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "question"]


class Offer(APlusIssuedModel, TimestampedModel):
    AUDIENCE = [("all", "Alle"), ("member", "A+ Member"), ("glow", "A+ Glow"), ("signature", "A+ Signature"), ("black", "A+ Black"), ("birthday", "Geburtstag"), ("inactive", "Inaktiv"), ("package_expiry", "Paket läuft ab")]
    TYPE = [("product", "Produkt"), ("event", "Event"), ("membership", "Membership"), ("organizational", "Organisatorischer Vorteil")]
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    audience = models.CharField(max_length=20, choices=AUDIENCE, default="all")
    offer_type = models.CharField(max_length=20, choices=TYPE)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    coin_bonus_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    active = models.BooleanField(default=True)
    linked_product = models.ForeignKey(ShopProduct, null=True, blank=True, on_delete=models.SET_NULL)
    medical_treatment_discount = models.BooleanField(default=False, editable=False)

    def clean(self):
        if self.medical_treatment_discount:
            raise ValidationError("Die A+ Angebotslogik darf keine ärztliche Vergütung oder medizinische Behandlung rabattieren.")

    def __str__(self):
        return self.title


class BeautyEvent(APlusIssuedModel, TimestampedModel):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=20)
    location = models.CharField(max_length=180, blank=True)
    online_url = models.URLField(blank=True)
    minimum_tier = models.ForeignKey("platform_app.MembershipTier", null=True, blank=True, on_delete=models.SET_NULL)
    coin_cost = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class EventRegistration(TimestampedModel):
    STATUS = [("registered", "Angemeldet"), ("waitlist", "Warteliste"), ("cancelled", "Storniert"), ("attended", "Teilgenommen")]
    event = models.ForeignKey(BeautyEvent, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations")
    guest_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=15, choices=STATUS, default="registered")

    class Meta:
        unique_together = [("event", "user")]


class ContentArticle(APlusIssuedModel, TimestampedModel):
    TYPE = [("article", "Artikel"), ("video", "Video"), ("myth_fact", "Mythos oder Fakt"), ("faq", "FAQ"), ("care", "Pflegeinformation")]
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    content_type = models.CharField(max_length=20, choices=TYPE)
    summary = models.TextField(blank=True)
    body = models.TextField(blank=True)
    media_url = models.URLField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    season = models.CharField(max_length=40, blank=True)
    membership_only = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class SavedContent(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_content")
    article = models.ForeignKey(ContentArticle, on_delete=models.CASCADE)

    class Meta:
        unique_together = [("user", "article")]


class Feedback(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback_entries")
    appointment = models.ForeignKey("platform_app.Appointment", null=True, blank=True, on_delete=models.SET_NULL)
    overall_rating = models.PositiveSmallIntegerField()
    cleanliness_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    staff_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    waiting_time_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    private_to_management = models.BooleanField(default=True)
    public_review_requested_at = models.DateTimeField(null=True, blank=True)
    verified = models.BooleanField(default=False)

    def clean(self):
        for value in [self.overall_rating, self.cleanliness_rating, self.staff_rating, self.waiting_time_rating]:
            if value is not None and not 1 <= value <= 5:
                raise ValidationError("Bewertungen müssen zwischen 1 und 5 liegen.")


class Survey(APlusIssuedModel, TimestampedModel):
    title = models.CharField(max_length=180)
    questions = models.JSONField(default=list)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reward_coins = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class SurveyResponse(TimestampedModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="survey_responses")
    answers = models.JSONField(default=dict)
    completed = models.BooleanField(default=True)
    coins_granted = models.BooleanField(default=False)

    class Meta:
        unique_together = [("survey", "user")]


class Complaint(TimestampedModel):
    STATUS = [("open", "Offen"), ("in_review", "In Prüfung"), ("resolved", "Gelöst"), ("closed", "Geschlossen")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="complaints")
    subject = models.CharField(max_length=180)
    description = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS, default="open")
    priority = models.CharField(max_length=10, choices=[("normal", "Normal"), ("high", "Hoch")], default="normal")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_complaints")
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.subject


class ConciergeRequest(APlusIssuedModel, TimestampedModel):
    TYPE = [("priority", "Priority Booking"), ("annual_plan", "Jährlicher Beauty Plan"), ("international", "Internationaler Support"), ("travel", "Reiseplanung"), ("companion", "Termin für Begleitperson"), ("other", "Sonstiges")]
    STATUS = [("open", "Offen"), ("in_progress", "In Bearbeitung"), ("completed", "Abgeschlossen"), ("declined", "Nicht verfügbar")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="concierge_requests")
    request_type = models.CharField(max_length=20, choices=TYPE)
    title = models.CharField(max_length=180)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS, default="open")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="concierge_assignments")

    def __str__(self):
        return self.title


class NotificationPreference(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences")
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    appointment_reminders = models.BooleanField(default=True)
    aftercare_reminders = models.BooleanField(default=True)
    product_reminders = models.BooleanField(default=True)
    membership_messages = models.BooleanField(default=True)
    marketing_messages = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    hide_sensitive_text = models.BooleanField(default=True)


class PushSubscription(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)


class NotificationOutbox(TimestampedModel):
    CHANNEL = [("push", "Push"), ("email", "E-Mail"), ("inapp", "In-App")]
    STATUS = [("queued", "Wartet"), ("sent", "Gesendet"), ("failed", "Fehlgeschlagen"), ("cancelled", "Abgebrochen")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_outbox")
    channel = models.CharField(max_length=10, choices=CHANNEL)
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    scheduled_for = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=12, choices=STATUS, default="queued")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sensitive = models.BooleanField(default=False)


class DataExportRequest(TimestampedModel):
    STATUS = [("requested", "Angefordert"), ("processing", "In Bearbeitung"), ("ready", "Bereit"), ("expired", "Abgelaufen"), ("rejected", "Abgelehnt")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="data_export_requests")
    status = models.CharField(max_length=15, choices=STATUS, default="requested")
    export_file = models.FileField(upload_to="exports/%Y/%m/", storage=private_storage, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class AccountDeletionRequest(TimestampedModel):
    STATUS = [("requested", "Angefordert"), ("identity_check", "Identitätsprüfung"), ("scheduled", "Vorgemerkt"), ("completed", "Abgeschlossen"), ("cancelled", "Storniert"), ("partially_retained", "Teilweise gesetzlich aufbewahrt")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deletion_requests")
    status = models.CharField(max_length=20, choices=STATUS, default="requested")
    reason = models.TextField(blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    retention_note = models.TextField(blank=True)


class DeviceSession(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_sessions")
    session_key = models.CharField(max_length=80, unique=True)
    device_name = models.CharField(max_length=180, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]


class IntegrationCredentialStatus(TimestampedModel):
    integration = models.OneToOneField("platform_app.IntegrationConfig", on_delete=models.CASCADE, related_name="credential_status")
    required_variables = models.JSONField(default=list)
    configured_variables = models.JSONField(default=list)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    ready = models.BooleanField(default=False)
    note = models.TextField(blank=True)


class ExternalIdentity(TimestampedModel):
    PROVIDER = [("google", "Google"), ("apple", "Apple")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="external_identities")
    provider = models.CharField(max_length=10, choices=PROVIDER)
    subject = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    email_verified = models.BooleanField(default=False)

    class Meta:
        unique_together = [("provider", "subject")]


class ExternalAppointmentLink(TimestampedModel):
    PROVIDER = [("doctolib", "Doctolib"), ("simplybook", "SimplyBook")]
    appointment = models.ForeignKey("platform_app.Appointment", on_delete=models.CASCADE, related_name="external_links")
    provider = models.CharField(max_length=15, choices=PROVIDER)
    external_id = models.CharField(max_length=180)
    sync_token = models.CharField(max_length=180, blank=True)
    last_external_update_at = models.DateTimeField(null=True, blank=True)
    conflict_state = models.CharField(max_length=30, blank=True)

    class Meta:
        unique_together = [("provider", "external_id")]
