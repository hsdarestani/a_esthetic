from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html

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


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    extra = 0
    can_delete = False
    fk_name = "user"
    fields = (
        "role",
        "phone",
        "salutation",
        "preferred_language",
        "marketing_consent",
        "health_data_consent",
        "onboarding_required",
        "auth_provider",
        "email_verified_at",
        "phone_verified_at",
        "profile_completed_at",
        "referral_code_used",
        "created_at",
    )
    readonly_fields = (
        "email_verified_at",
        "phone_verified_at",
        "profile_completed_at",
        "created_at",
    )


class MemberAccountInline(admin.StackedInline):
    model = MemberAccount
    extra = 0
    can_delete = False
    fields = ("member_number", "tier", "status", "valid_until", "joined_at")
    readonly_fields = ("member_number", "joined_at")


class WalletAccountInline(admin.StackedInline):
    model = WalletAccount
    extra = 0
    can_delete = False
    fields = ("balance_cents", "coin_balance", "updated_at")
    readonly_fields = ("balance_cents", "coin_balance", "updated_at")


class AestheticUserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "full_name",
        "customer_phone",
        "customer_role",
        "membership_status",
        "email_verified",
        "is_active",
        "last_login",
        "password_action",
        "customer_links",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "profile__role",
        "member_account__status",
        "date_joined",
        "last_login",
    )
    search_fields = (
        "email",
        "username",
        "first_name",
        "last_name",
        "profile__phone",
        "member_account__member_number",
    )
    ordering = ("-date_joined",)
    list_select_related = ("profile", "member_account", "wallet")
    inlines = (UserProfileInline, MemberAccountInline, WalletAccountInline)
    actions = ("activate_customer_accounts", "deactivate_customer_accounts")
    save_on_top = True

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.get_full_name() or obj.username

    @admin.display(description="Telefon")
    def customer_phone(self, obj):
        try:
            return obj.profile.phone or "—"
        except UserProfile.DoesNotExist:
            return "—"

    @admin.display(description="Rolle")
    def customer_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return "—"

    @admin.display(description="Mitgliedschaft")
    def membership_status(self, obj):
        try:
            account = obj.member_account
        except MemberAccount.DoesNotExist:
            return "—"
        return f"{account.member_number} · {account.get_status_display()}"

    @admin.display(description="E-Mail bestätigt", boolean=True)
    def email_verified(self, obj):
        try:
            return bool(obj.profile.email_verified_at)
        except UserProfile.DoesNotExist:
            return False

    @admin.display(description="Passwort")
    def password_action(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:auth_user_password_change", args=[obj.pk])
        return format_html('<a class="button" href="{}">Passwort ändern</a>', url)

    @admin.display(description="Kundendaten")
    def customer_links(self, obj):
        if not obj.pk:
            return "—"
        links = [
            (
                reverse("admin:platform_app_appointment_changelist")
                + f"?user__id__exact={obj.pk}",
                "Termine",
            ),
            (
                reverse("admin:platform_app_wallettransaction_changelist")
                + f"?user__id__exact={obj.pk}",
                "Wallet",
            ),
            (
                reverse("admin:platform_app_memberpackage_changelist")
                + f"?user__id__exact={obj.pk}",
                "Pakete",
            ),
            (
                reverse("admin:p0_app_devicesession_changelist")
                + f"?user__id__exact={obj.pk}",
                "Geräte",
            ),
        ]
        return format_html(
            " · ".join('<a href="{}">{}</a>' for _ in links),
            *[value for pair in links for value in pair],
        )

    @admin.action(description="Ausgewählte Kundenkonten aktivieren")
    def activate_customer_accounts(self, request, queryset):
        eligible = queryset.filter(is_staff=False, is_superuser=False)
        updated = eligible.update(is_active=True)
        self.message_user(
            request,
            f"{updated} Kundenkonto/Kundenkonten aktiviert.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Ausgewählte Kundenkonten deaktivieren")
    def deactivate_customer_accounts(self, request, queryset):
        eligible = queryset.filter(is_staff=False, is_superuser=False)
        updated = eligible.update(is_active=False)
        self.message_user(
            request,
            f"{updated} Kundenkonto/Kundenkonten deaktiviert.",
            level=messages.SUCCESS,
        )


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, AestheticUserAdmin)


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
