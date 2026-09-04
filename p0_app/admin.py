from django.contrib import admin

from .models import (
    AccountDeletionRequest,
    DataExportRequest,
    DeviceSession,
    PackageBookingRedemption,
    PackageBookingService,
)


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("requested_email", "user", "source", "status", "requested_at", "scheduled_for")
    list_filter = ("source", "status")
    search_fields = ("requested_email", "user__username", "user__email")
    readonly_fields = ("requested_at",)


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "device_name", "ip_address", "last_seen_at", "revoked_at")
    list_filter = ("revoked_at",)
    search_fields = ("user__username", "user__email", "device_name", "user_agent")
    readonly_fields = ("token_hash", "created_at", "last_seen_at")


@admin.register(DataExportRequest)
class DataExportRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "requested_at", "completed_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("requested_at", "completed_at")


@admin.register(PackageBookingService)
class PackageBookingServiceAdmin(admin.ModelAdmin):
    list_display = ("package_definition", "service_name", "service_slug", "active", "auto_created")
    list_filter = ("active", "auto_created")
    search_fields = ("package_definition__name", "service_name", "service_slug")


@admin.register(PackageBookingRedemption)
class PackageBookingRedemptionAdmin(admin.ModelAdmin):
    list_display = ("booking_public_id", "user", "member_package", "service_slug", "status", "reserved_at")
    list_filter = ("status", "service_slug")
    search_fields = ("booking_public_id", "user__email", "user__username", "member_package__definition__name")
    readonly_fields = ("booking_public_id", "user", "member_package", "service_slug", "reserved_at", "released_at")
