from django.contrib import admin

from .models import AccountDeletionRequest, DataExportRequest, DeviceSession


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
