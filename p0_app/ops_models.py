from django.conf import settings
from django.db import models
from django.utils import timezone


class RewardRedemption(models.Model):
    STATUS = [
        ("pending", "Offen"),
        ("processing", "In Bearbeitung"),
        ("fulfilled", "Erfüllt"),
        ("cancelled", "Storniert"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reward_redemptions",
    )
    reward = models.ForeignKey(
        "platform_app.Reward",
        on_delete=models.PROTECT,
        related_name="redemptions",
    )
    fulfillment_code = models.CharField(max_length=32, unique=True)
    coin_cost = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=STATUS, default="pending")
    customer_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfilled_reward_redemptions",
    )

    class Meta:
        app_label = "p0_app"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.fulfillment_code} – {self.user} – {self.reward}"


class PushDevice(models.Model):
    PLATFORM = [("android", "Android"), ("ios", "iOS")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_devices",
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=12, choices=PLATFORM)
    app_version = models.CharField(max_length=40, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "p0_app"
        ordering = ["-last_seen_at"]

    def __str__(self):
        return f"{self.user} – {self.platform}"


class AppNotification(models.Model):
    CATEGORY = [
        ("general", "Allgemein"),
        ("reward", "Reward"),
        ("referral", "Empfehlung"),
        ("booking", "Termin"),
        ("campaign", "Kampagne"),
        ("system", "System"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_notifications",
    )
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY, default="general")
    deeplink = models.CharField(max_length=240, blank=True)
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    push_attempted_at = models.DateTimeField(null=True, blank=True)
    push_result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "p0_app"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "created_at"], name="p0_notify_user_read_idx")]

    def __str__(self):
        return f"{self.user} – {self.title}"
