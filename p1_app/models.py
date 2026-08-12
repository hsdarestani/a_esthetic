from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProgressAlbum(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p1_progress_albums")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    marketing_use_allowed = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ProgressPhoto(TimeStampedModel):
    KIND = [("before", "Vorher"), ("after", "Nachher"), ("progress", "Verlauf")]

    album = models.ForeignKey(ProgressAlbum, on_delete=models.CASCADE, related_name="photos")
    kind = models.CharField(max_length=12, choices=KIND)
    image = models.FileField(upload_to="progress/%Y/%m/")
    taken_at = models.DateTimeField(default=timezone.now)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="p1_uploaded_progress_photos")
    sha256 = models.CharField(max_length=64, editable=False)
    visible_to_customer = models.BooleanField(default=True)

    class Meta:
        ordering = ["taken_at", "id"]

    def __str__(self):
        return f"{self.album} – {self.get_kind_display()}"


class AftercareTemplate(TimeStampedModel):
    service = models.ForeignKey("platform_app.Service", on_delete=models.CASCADE, related_name="p1_aftercare_templates")
    title = models.CharField(max_length=180)
    introduction = models.TextField(blank=True)
    approved_by = models.CharField(max_length=140, blank=True, help_text="Interne fachliche Freigabe; keine automatische medizinische Empfehlung")
    version = models.CharField(max_length=20, default="1.0")
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["service", "version"], name="p1_aftercare_service_version")]
        ordering = ["service__name", "-created_at"]

    def __str__(self):
        return f"{self.service} – {self.title} v{self.version}"


class AftercareTask(TimeStampedModel):
    TYPE = [("do", "Empfohlen"), ("avoid", "Vermeiden"), ("contact", "A+ kontaktieren")]

    template = models.ForeignKey(AftercareTemplate, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=15, choices=TYPE)
    sort_order = models.PositiveIntegerField(default=100)
    warning_sign = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class AssignedAftercare(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p1_assigned_aftercare")
    appointment = models.ForeignKey("platform_app.Appointment", on_delete=models.CASCADE, related_name="p1_assigned_aftercare")
    template = models.ForeignKey(AftercareTemplate, on_delete=models.PROTECT)
    starts_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["appointment", "template"], name="p1_unique_aftercare_assignment")]
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{self.user} – {self.template.title}"


class AftercareTaskStatus(TimeStampedModel):
    assigned = models.ForeignKey(AssignedAftercare, on_delete=models.CASCADE, related_name="task_statuses")
    task = models.ForeignKey(AftercareTask, on_delete=models.PROTECT)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assigned", "task"], name="p1_unique_aftercare_task_status")]
        ordering = ["task__sort_order", "id"]


class BeautyPlan(TimeStampedModel):
    STATUS = [("draft", "Entwurf"), ("active", "Aktiv"), ("completed", "Abgeschlossen"), ("archived", "Archiviert")]
    JOURNEY = [
        ("custom", "Individuell"),
        ("wedding", "Wedding"),
        ("birthday", "Birthday Glow"),
        ("summer", "Summer"),
        ("winter", "Winter Skin"),
        ("travel", "Travel"),
        ("photoshoot", "Photoshoot"),
        ("event", "Special Event"),
        ("hair", "Hair Recovery"),
        ("skin", "Skin Reset"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p1_beauty_plans")
    title = models.CharField(max_length=180)
    journey_type = models.CharField(max_length=20, choices=JOURNEY, default="custom")
    goal = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    monthly_budget_cents = models.PositiveIntegerField(default=0)
    annual_budget_cents = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=15, choices=STATUS, default="draft")
    medical_decision_support = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["-updated_at"]

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


class BeautyPlanStep(TimeStampedModel):
    TYPE = [
        ("care", "Pflege"),
        ("product", "Produkt"),
        ("consultation", "Beratung anfragen"),
        ("appointment", "Organisatorischer Termin"),
        ("content", "Lerninhalt"),
    ]

    plan = models.ForeignKey(BeautyPlan, on_delete=models.CASCADE, related_name="steps")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    due_on = models.DateField(null=True, blank=True)
    step_type = models.CharField(max_length=20, choices=TYPE)
    estimated_cost_cents = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "due_on", "id"]

    def __str__(self):
        return self.title
