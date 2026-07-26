from django.contrib import admin

from .models import *


admin.site.site_header = "A+ Esthetic Verwaltung"
admin.site.site_title = "A+ Esthetic"
admin.site.index_title = "Verwaltung"


@admin.register(FeatureModule)
class FeatureModuleAdmin(admin.ModelAdmin):
    list_display = ("name_de", "enabled", "customer_visible", "sort_order", "updated_at")
    list_editable = ("enabled", "customer_visible", "sort_order")
    search_fields = ("name_de",)
    readonly_fields = ("key", "updated_at")
    fieldsets = ((None, {"fields": ("name_de", "enabled", "customer_visible", "sort_order")}),)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "marketing_consent", "health_data_consent", "created_at")
    list_filter = ("role", "marketing_consent", "health_data_consent")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "entity_type", "entity_id", "ip_address")
    readonly_fields = ("actor", "action", "entity_type", "entity_id", "metadata", "ip_address", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "action", "entity_type", "entity_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MembershipTier)
class MembershipTierAdmin(admin.ModelAdmin):
    list_display = ("name", "monthly_fee_cents", "coin_multiplier", "priority", "active")
    list_editable = ("active", "priority")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(MemberAccount)
class MemberAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "member_number", "tier", "status", "valid_until", "joined_at")
    list_filter = ("status", "tier")
    search_fields = ("user__username", "user__email", "member_number")


@admin.register(WalletAccount)
class WalletAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "balance_cents", "coin_balance", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "direction", "amount_cents", "coin_amount", "description")
    list_filter = ("kind", "direction", "created_at")
    search_fields = ("user__username", "description", "reference")


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("name", "coin_cost", "active", "inventory")
    list_editable = ("active", "inventory")


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ("code", "recipient_email", "initial_cents", "balance_cents", "status", "expires_at")
    list_filter = ("status",)


@admin.register(PackageDefinition)
class PackageDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "sessions", "validity_days", "active")
    list_editable = ("active",)
    exclude = ("medical_service", "issuer")


@admin.register(MemberPackage)
class MemberPackageAdmin(admin.ModelAdmin):
    list_display = ("user", "definition", "remaining_sessions", "expires_at", "status")
    list_filter = ("status", "definition")


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("code", "referrer", "invited_email", "status", "reward_coins", "created_at")
    list_filter = ("status",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "audience", "starts_at", "ends_at", "active")
    list_filter = ("audience", "active")
    exclude = ("issuer",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "duration_minutes", "price_label", "active", "bookable_in_app")
    list_filter = ("category", "active", "bookable_in_app")
    prepopulated_fields = {"slug": ("name",)}
    exclude = ("doctor_revenue_tracked",)


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "role", "active")
    filter_horizontal = ("services",)


@admin.register(WorkingHour)
class WorkingHourAdmin(admin.ModelAdmin):
    list_display = ("staff", "weekday", "start_time", "end_time", "active")
    list_filter = ("weekday", "active")


@admin.register(BlockedPeriod)
class BlockedPeriodAdmin(admin.ModelAdmin):
    list_display = ("staff", "starts_at", "ends_at", "reason")
    list_filter = ("staff",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("starts_at", "user", "service", "staff", "status", "source")
    list_filter = ("status", "source", "service", "staff")
    search_fields = ("user__username", "user__email", "external_id")
    date_hierarchy = "starts_at"


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "service", "preferred_from", "preferred_until", "status", "created_at")
    list_filter = ("status", "service")


@admin.register(BeautyPassportEntry)
class BeautyPassportEntryAdmin(admin.ModelAdmin):
    list_display = ("occurred_on", "user", "entry_type", "title", "provider_name", "visible_to_customer")
    list_filter = ("entry_type", "visible_to_customer")
    search_fields = ("user__username", "title", "provider_name")


@admin.register(ConsentTemplate)
class ConsentTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "health_data", "marketing", "active")
    list_filter = ("health_data", "marketing", "active")
    readonly_fields = ("key",)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("accepted_at", "user", "template", "accepted", "withdrawn_at", "ip_address")
    list_filter = ("accepted", "template")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("scheduled_for", "user", "title", "channel", "status")
    list_filter = ("channel", "status")
    search_fields = ("user__username", "title")


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("due_at", "user", "title", "status", "requires_review")
    list_filter = ("status", "requires_review")


@admin.register(SecureDocument)
class SecureDocumentAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "title", "category", "uploaded_by")
    list_filter = ("category",)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "user", "subject", "status")
    list_filter = ("status",)
    inlines = (MessageInline,)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "thread", "sender", "is_internal")
    list_filter = ("is_internal",)


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "enabled", "sync_enabled", "last_sync_at")
    list_editable = ("enabled", "sync_enabled")
    fields = ("provider", "enabled", "sync_enabled", "last_sync_at")
    readonly_fields = ("provider", "last_sync_at")


@admin.register(SyncEvent)
class SyncEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "integration", "direction", "entity_type", "status")
    list_filter = ("integration", "direction", "status")
    readonly_fields = ("created_at",)
