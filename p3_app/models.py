from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Badge(TimeStampedModel):
    key = models.SlugField(unique=True, max_length=80)
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=24, default="✦")
    active = models.BooleanField(default=True)
    is_medical_reward = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "Achievement"
        verbose_name_plural = "Achievements"

    def clean(self):
        if self.is_medical_reward:
            raise ValidationError("Medizinische Leistungen dürfen nicht als Achievement belohnt werden.")

    def __str__(self):
        return self.name


class Challenge(TimeStampedModel):
    TYPE = [
        ("care", "Pflegeroutine"),
        ("learning", "Lernen"),
        ("profile", "Profil"),
        ("seasonal", "Saisonal"),
        ("community", "Community"),
    ]

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    challenge_type = models.CharField(max_length=20, choices=TYPE)
    target_count = models.PositiveIntegerField(default=1)
    reward_coins = models.PositiveIntegerField(default=0)
    badge = models.ForeignKey(Badge, null=True, blank=True, on_delete=models.SET_NULL, related_name="challenges")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    medical_treatment_count_based = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["ends_at", "title"]

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError("Challenge-Ende muss nach dem Start liegen.")
        if self.target_count < 1 or self.target_count > 365:
            raise ValidationError("Challenge-Ziel muss zwischen 1 und 365 liegen.")
        if self.reward_coins > 5000:
            raise ValidationError("Challenge-Reward ist zu hoch.")
        if self.medical_treatment_count_based:
            raise ValidationError("Die Häufigkeit medizinischer Behandlungen darf nicht gamifiziert werden.")

    def __str__(self):
        return self.title


class ChallengeParticipation(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p3_challenge_participations")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="participations")
    progress = models.PositiveIntegerField(default=0)
    last_progress_on = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_granted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "challenge"], name="p3_unique_challenge_participation"),
        ]

    def __str__(self):
        return f"{self.user} – {self.challenge}"


class UserBadge(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p3_badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awards")
    source_type = models.CharField(max_length=30, blank=True)
    source_id = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "badge"], name="p3_unique_user_badge")]

    def __str__(self):
        return f"{self.user} – {self.badge}"


class Quiz(TimeStampedModel):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    passing_percent = models.PositiveSmallIntegerField(default=70)
    reward_coins = models.PositiveIntegerField(default=0)
    badge = models.ForeignKey(Badge, null=True, blank=True, on_delete=models.SET_NULL, related_name="quizzes")
    active = models.BooleanField(default=True)
    approved = models.BooleanField(default=False)
    medical_advice = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["title"]

    def clean(self):
        if self.passing_percent < 1 or self.passing_percent > 100:
            raise ValidationError("Bestehensgrenze muss zwischen 1 und 100 Prozent liegen.")
        if self.reward_coins > 5000:
            raise ValidationError("Quiz-Reward ist zu hoch.")
        if self.medical_advice:
            raise ValidationError("Quiz-Inhalte dürfen keine individuelle medizinische Empfehlung erzeugen.")

    def __str__(self):
        return self.title


class QuizQuestion(TimeStampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    question = models.TextField()
    options = models.JSONField(default=list)
    correct_index = models.PositiveSmallIntegerField()
    explanation = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "id"]

    def clean(self):
        if not isinstance(self.options, list) or len(self.options) < 2 or len(self.options) > 6:
            raise ValidationError("Eine Quizfrage benötigt 2 bis 6 Antwortoptionen.")
        if any(not str(option).strip() for option in self.options):
            raise ValidationError("Antwortoptionen dürfen nicht leer sein.")
        if self.correct_index >= len(self.options):
            raise ValidationError("Korrekte Antwort liegt außerhalb der Antwortoptionen.")

    def __str__(self):
        return f"{self.quiz}: {self.question[:50]}"


class QuizAttempt(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p3_quiz_attempts")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    answers = models.JSONField(default=list)
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    percent = models.PositiveSmallIntegerField(default=0)
    completed = models.BooleanField(default=False)
    passed = models.BooleanField(default=False)
    reward_granted = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["user", "quiz"], name="p3_unique_quiz_attempt")]

    def __str__(self):
        return f"{self.user} – {self.quiz}"


class BeautyEvent(TimeStampedModel):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=220, blank=True)
    capacity = models.PositiveIntegerField(default=20)
    allow_guest = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    medical_service_reward = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["starts_at", "title"]
        verbose_name = "A+ Event"
        verbose_name_plural = "A+ Events"

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError("Event-Ende muss nach dem Start liegen.")
        if self.capacity < 1 or self.capacity > 5000:
            raise ValidationError("Event-Kapazität ist ungültig.")
        if self.medical_service_reward:
            raise ValidationError("Events dürfen keine medizinische Leistung als Reward vergeben.")

    def __str__(self):
        return self.title


class EventRegistration(TimeStampedModel):
    STATUS = [
        ("registered", "Angemeldet"),
        ("waitlist", "Warteliste"),
        ("cancelled", "Storniert"),
        ("attended", "Teilgenommen"),
    ]

    event = models.ForeignKey(BeautyEvent, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p3_event_registrations")
    guest_name = models.CharField(max_length=120, blank=True)
    seat_count = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=15, choices=STATUS, default="registered")

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="p3_unique_event_registration")]

    def clean(self):
        if self.seat_count not in {1, 2}:
            raise ValidationError("Pro Anmeldung sind maximal zwei Plätze möglich.")
        if self.seat_count == 2 and not self.event.allow_guest:
            raise ValidationError("Dieses Event erlaubt keine Begleitperson.")

    def __str__(self):
        return f"{self.event} – {self.user}"


class ConciergeRequest(TimeStampedModel):
    TYPE = [
        ("priority_booking", "Priority Booking"),
        ("travel_coordination", "Terminabstimmung für Reise"),
        ("companion", "Termin für Begleitperson"),
        ("event_support", "Event-Support"),
        ("product_pickup", "Produktabholung"),
        ("accessibility", "Barrierefreiheit / Unterstützung"),
        ("other", "Sonstiges"),
    ]
    STATUS = [
        ("open", "Offen"),
        ("in_progress", "In Bearbeitung"),
        ("waiting_customer", "Rückfrage an Kunde"),
        ("completed", "Abgeschlossen"),
        ("declined", "Nicht verfügbar"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p3_concierge_requests")
    thread = models.OneToOneField("platform_app.Thread", null=True, blank=True, on_delete=models.SET_NULL, related_name="p3_concierge")
    request_type = models.CharField(max_length=24, choices=TYPE)
    title = models.CharField(max_length=180)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="open")
    staff_note = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    medical_decision_support = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Concierge-Anfrage"
        verbose_name_plural = "Concierge-Anfragen"

    def clean(self):
        if self.medical_decision_support:
            raise ValidationError("Concierge darf keine medizinische Entscheidung automatisieren.")
        if self.thread_id and self.thread.user_id != self.user_id:
            raise ValidationError("Concierge-Anfrage und Unterhaltung müssen demselben Kunden gehören.")

    def __str__(self):
        return f"{self.user} – {self.title}"
