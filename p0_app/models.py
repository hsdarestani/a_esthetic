from django.conf import settings
from django.db import models
from django.utils import timezone


class AccountDeletionRequest(models.Model):
    STATUS = [
        ("requested", "Angefordert"),
        ("identity_check", "Identitätsprüfung"),
        ("scheduled", "Vorgemerkt"),
        ("completed", "Abgeschlossen"),
        ("cancelled", "Storniert"),
        ("partially_retained", "Teilweise gesetzlich aufbewahrt"),
    ]
    SOURCE = [
        ("mobile_app", "Mobile App"),
        ("public_web", "Öffentliche Webseite"),
        ("authenticated_web", "Angemeldete Webseite"),
        ("support", "Support"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="p0_deletion_requests",
    )
    requested_email = models.EmailField(blank=True)
    source = models.CharField(max_length=24, choices=SOURCE, default="mobile_app")
    status = models.CharField(max_length=24, choices=STATUS, default="requested")
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    retention_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        identity = self.requested_email or (self.user.get_username() if self.user_id else "anonymous")
        return f"{identity} – {self.get_status_display()}"


class DeviceSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="p0_device_sessions",
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    device_name = models.CharField(max_length=180, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]

    @property
    def active(self):
        return self.revoked_at is None

    def __str__(self):
        return f"{self.user.get_username()} – {self.device_name or 'Gerät'}"


class DataExportRequest(models.Model):
    STATUS = [
        ("requested", "Angefordert"),
        ("processing", "In Bearbeitung"),
        ("ready", "Bereit"),
        ("expired", "Abgelaufen"),
        ("failed", "Fehlgeschlagen"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="p0_data_exports",
    )
    status = models.CharField(max_length=16, choices=STATUS, default="requested")
    requested_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]


class PackageBookingService(models.Model):
    """Deterministic mapping between a Customer Club package and a book service."""

    package_definition = models.ForeignKey(
        "platform_app.PackageDefinition",
        on_delete=models.CASCADE,
        related_name="booking_service_mappings",
    )
    service_slug = models.SlugField(max_length=160)
    service_name = models.CharField(max_length=180, blank=True)
    active = models.BooleanField(default=True)
    auto_created = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("package_definition", "service_slug")]
        ordering = ["package_definition_id", "service_slug"]

    def __str__(self):
        return f"{self.package_definition} → {self.service_slug}"


class PackageBookingRedemption(models.Model):
    STATUS = [("reserved", "Reserviert"), ("released", "Freigegeben")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="package_booking_redemptions",
    )
    member_package = models.ForeignKey(
        "platform_app.MemberPackage",
        on_delete=models.PROTECT,
        related_name="booking_redemptions",
    )
    booking_public_id = models.CharField(max_length=64, unique=True)
    service_slug = models.SlugField(max_length=160)
    status = models.CharField(max_length=16, choices=STATUS, default="reserved")
    reserved_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-reserved_at"]

    def __str__(self):
        return f"{self.booking_public_id} – {self.member_package} – {self.status}"
