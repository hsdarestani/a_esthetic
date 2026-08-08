from django.contrib import admin

from .models import (
    Appointment,
    AuditLog,
    BlockedPeriod,
    Campaign,
    FeatureModule,
    GiftCard,
    IntegrationConfig,
    MemberAccount,
    MemberPackage,
    MembershipTier,
    Message,
    PackageDefinition,
    Referral,
    Reminder,
    Reward,
    Service,
    StaffMember,
    Thread,
    UserProfile,
    WaitlistEntry,
    WalletAccount,
    WalletTransaction,
    WorkingHour,
)


@admin.register(FeatureModule)
class FeatureModuleAdmin(admin.ModelAdmin):
    list_display = ('name_de', 'key', 'enabled', 'customer_visible', 'sort_order', 'updated_at')
    list_editable = ('enabled', 'customer_visible', 'sort_order')
    search_fields = ('name_de', 'key')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'marketing_consent', 'created_at')
    list_filter = ('role', 'marketing_consent')
    readonly_fields = ('created_at',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'entity_type', 'entity_id', 'ip_address')
    readonly_fields = ('actor', 'action', 'entity_type', 'entity_id', 'metadata', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('actor__username', 'action', 'entity_type', 'entity_id')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MembershipTier)
class MembershipTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'monthly_fee_cents', 'coin_multiplier', 'priority', 'active')
    list_editable = ('active', 'priority')


@admin.register(MemberAccount)
class MemberAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'member_number', 'tier', 'status', 'valid_until', 'joined_at')
    list_filter = ('status', 'tier')
    search_fields = ('user__username', 'user__email', 'member_number')


@admin.register(WalletAccount)
class WalletAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_cents', 'coin_balance', 'updated_at')
    search_fields = ('user__username', 'user__email')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'kind', 'direction', 'amount_cents', 'coin_amount', 'description', 'issuer')
    list_filter = ('kind', 'direction', 'created_at')
    search_fields = ('user__username', 'description', 'reference')


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ('name', 'coin_cost', 'active', 'inventory', 'issuer')
    list_editable = ('active', 'inventory')
    exclude = ('is_medical_service',)


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ('code', 'recipient_email', 'initial_cents', 'balance_cents', 'status', 'expires_at', 'issuer')
    list_filter = ('status',)


@admin.register(PackageDefinition)
class PackageDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'sessions', 'validity_days', 'active', 'issuer')
    list_editable = ('active',)
    exclude = ('medical_service',)


@admin.register(MemberPackage)
class MemberPackageAdmin(admin.ModelAdmin):
    list_display = ('user', 'definition', 'remaining_sessions', 'expires_at', 'status')
    list_filter = ('status', 'definition')


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('code', 'referrer', 'invited_email', 'status', 'reward_coins', 'created_at')
    list_filter = ('status',)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'audience', 'starts_at', 'ends_at', 'active', 'issuer')
    list_filter = ('audience', 'active')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_minutes', 'price_label', 'active', 'bookable_in_app')
    list_filter = ('active', 'bookable_in_app')
    prepopulated_fields = {'slug': ('name',)}
    exclude = ('category', 'requires_medical_confirmation', 'doctor_revenue_tracked')


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'role', 'active')
    filter_horizontal = ('services',)


@admin.register(WorkingHour)
class WorkingHourAdmin(admin.ModelAdmin):
    list_display = ('staff', 'weekday', 'start_time', 'end_time', 'active')
    list_filter = ('weekday', 'active')


@admin.register(BlockedPeriod)
class BlockedPeriodAdmin(admin.ModelAdmin):
    list_display = ('staff', 'starts_at', 'ends_at', 'reason')
    list_filter = ('staff',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('starts_at', 'user', 'service', 'staff', 'status', 'source')
    list_filter = ('status', 'source', 'service', 'staff')
    search_fields = ('user__username', 'user__email', 'external_id')
    date_hierarchy = 'starts_at'
    exclude = ('notes_customer', 'consent_acknowledged')


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'preferred_from', 'preferred_until', 'status', 'created_at')
    list_filter = ('status', 'service')


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('scheduled_for', 'user', 'title', 'channel', 'status')
    list_filter = ('channel', 'status')
    search_fields = ('user__username', 'title')


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('created_at',)
    exclude = ('attachment',)


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'user', 'subject', 'status')
    list_filter = ('status',)
    inlines = (MessageInline,)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'thread', 'sender', 'is_internal')
    list_filter = ('is_internal',)
    exclude = ('attachment',)


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ('provider', 'enabled', 'sync_enabled', 'status', 'credential_reference', 'last_sync_at')
    list_editable = ('enabled', 'sync_enabled')
