from django.contrib import admin

from .models import *


class ReadOnlyIssuerAdmin(admin.ModelAdmin):
    readonly_fields = ("issuer",)


@admin.register(MembershipBenefit)
class MembershipBenefitAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "tier", "benefit_type", "active", "issuer")
    list_filter = ("tier", "benefit_type", "active")
    list_editable = ("active",)


@admin.register(MembershipSubscription)
class MembershipSubscriptionAdmin(ReadOnlyIssuerAdmin):
    list_display = ("user", "tier", "interval", "status", "renews_on", "auto_renew", "issuer")
    list_filter = ("tier", "interval", "status", "auto_renew")


@admin.register(MemberPass)
class MemberPassAdmin(ReadOnlyIssuerAdmin):
    list_display = ("user", "provider", "status", "external_object_id", "last_synced_at")
    list_filter = ("provider", "status")
    readonly_fields = ("issuer", "serial_number", "last_error", "last_synced_at")


@admin.register(CoinRule)
class CoinRuleAdmin(ReadOnlyIssuerAdmin):
    list_display = ("event", "coins", "daily_limit", "active", "issuer")
    list_editable = ("coins", "daily_limit", "active")


@admin.register(RewardRedemption)
class RewardRedemptionAdmin(ReadOnlyIssuerAdmin):
    list_display = ("created_at", "code", "user", "reward", "coins_spent", "status", "issuer")
    list_filter = ("status", "reward")
    readonly_fields = ("issuer", "code", "created_at", "updated_at")


@admin.register(GiftCardDelivery)
class GiftCardDeliveryAdmin(ReadOnlyIssuerAdmin):
    list_display = ("gift_card", "recipient_name", "scheduled_for", "delivered_at", "opened_at", "issuer")


@admin.register(PackageUsage)
class PackageUsageAdmin(ReadOnlyIssuerAdmin):
    list_display = ("created_at", "member_package", "appointment", "sessions_used", "recorded_by", "issuer")
    list_filter = ("member_package__definition",)


@admin.register(BookingPolicy)
class BookingPolicyAdmin(ReadOnlyIssuerAdmin):
    list_display = ("service", "minimum_notice_hours", "maximum_days_ahead", "cancellation_hours", "deposit_cents", "issuer")


@admin.register(AppointmentChangeRequest)
class AppointmentChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "appointment", "request_type", "status", "delay_minutes", "handled_by")
    list_filter = ("request_type", "status")


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("checked_in_at", "appointment", "method", "status", "staff_notified_at")
    list_filter = ("method", "status")


@admin.register(WaitlistOffer)
class WaitlistOfferAdmin(admin.ModelAdmin):
    list_display = ("waitlist_entry", "offered_start", "expires_at", "status")
    list_filter = ("status",)
    readonly_fields = ("token",)


class ProgressPhotoInline(admin.TabularInline):
    model = ProgressPhoto
    extra = 0
    readonly_fields = ("sha256", "created_at", "updated_at")


@admin.register(ProgressAlbum)
class ProgressAlbumAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "private", "marketing_use_allowed", "created_at")
    list_filter = ("private", "marketing_use_allowed")
    inlines = (ProgressPhotoInline,)


@admin.register(ProgressPhoto)
class ProgressPhotoAdmin(admin.ModelAdmin):
    list_display = ("album", "kind", "taken_at", "uploaded_by", "visible_to_customer", "sha256")
    list_filter = ("kind", "visible_to_customer")
    readonly_fields = ("sha256",)


class AftercareTaskInline(admin.TabularInline):
    model = AftercareTask
    extra = 0


@admin.register(AftercareTemplate)
class AftercareTemplateAdmin(ReadOnlyIssuerAdmin):
    list_display = ("service", "title", "version", "approved_by", "active", "issuer")
    list_filter = ("service", "active")
    inlines = (AftercareTaskInline,)


@admin.register(AftercareTask)
class AftercareTaskAdmin(ReadOnlyIssuerAdmin):
    list_display = ("template", "title", "task_type", "offset_hours", "warning_sign", "sort_order")
    list_filter = ("task_type", "warning_sign")


@admin.register(AssignedAftercare)
class AssignedAftercareAdmin(admin.ModelAdmin):
    list_display = ("user", "appointment", "template", "starts_at", "completed_at")


@admin.register(AftercareTaskStatus)
class AftercareTaskStatusAdmin(admin.ModelAdmin):
    list_display = ("assigned", "task", "completed", "completed_at")
    list_filter = ("completed",)


class BeautyPlanStepInline(admin.TabularInline):
    model = BeautyPlanStep
    extra = 0


@admin.register(BeautyPlan)
class BeautyPlanAdmin(ReadOnlyIssuerAdmin):
    list_display = ("user", "title", "journey_type", "target_date", "status", "approved_by_staff", "issuer")
    list_filter = ("journey_type", "status")
    inlines = (BeautyPlanStepInline,)


@admin.register(BeautyPlanStep)
class BeautyPlanStepAdmin(ReadOnlyIssuerAdmin):
    list_display = ("plan", "title", "step_type", "due_on", "estimated_cost_cents", "completed")
    list_filter = ("step_type", "completed")


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "category", "language", "approved", "active", "approved_by", "issuer")
    list_filter = ("category", "language", "approved", "active")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(AssistantConversation)
class AssistantConversationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "provider", "blocked_medical_request", "handed_to_staff")
    list_filter = ("provider", "blocked_medical_request", "handed_to_staff")
    readonly_fields = ("user", "question", "answer", "language", "blocked_medical_request", "handed_to_staff", "provider", "safety_metadata", "created_at", "updated_at")


@admin.register(CabinetProduct)
class CabinetProductAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "brand", "opened_on", "expires_on", "pao_months", "active")
    list_filter = ("active", "category")
    search_fields = ("user__username", "name", "brand", "barcode")


@admin.register(RoutineStep)
class RoutineStepAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "period", "sort_order", "active")
    list_filter = ("period", "active")


@admin.register(ShopCategory)
class ShopCategoryAdmin(ReadOnlyIssuerAdmin):
    list_display = ("name", "slug", "sort_order", "active", "issuer")
    list_editable = ("sort_order", "active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ShopProduct)
class ShopProductAdmin(ReadOnlyIssuerAdmin):
    list_display = ("name", "category", "price_cents", "stock", "active", "click_collect", "shipping", "issuer")
    list_filter = ("category", "active", "click_collect", "shipping", "subscription_available")
    list_editable = ("price_cents", "stock", "active")
    prepopulated_fields = {"slug": ("name",)}


class ShopOrderItemInline(admin.TabularInline):
    model = ShopOrderItem
    extra = 0
    readonly_fields = ("line_total_cents",)


@admin.register(ShopOrder)
class ShopOrderAdmin(admin.ModelAdmin):
    list_display = ("created_at", "order_number", "user", "status", "delivery_method", "total_cents", "payment_provider")
    list_filter = ("status", "delivery_method", "payment_provider")
    search_fields = ("order_number", "user__username", "user__email")
    inlines = (ShopOrderItemInline,)


@admin.register(Challenge)
class ChallengeAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "challenge_type", "target_count", "reward_coins", "starts_at", "ends_at", "active", "issuer")
    list_filter = ("challenge_type", "active")


@admin.register(ChallengeParticipation)
class ChallengeParticipationAdmin(admin.ModelAdmin):
    list_display = ("user", "challenge", "progress", "completed_at", "reward_granted")
    list_filter = ("completed_at", "reward_granted")


@admin.register(Badge)
class BadgeAdmin(ReadOnlyIssuerAdmin):
    list_display = ("name", "slug", "icon", "active", "issuer")
    list_editable = ("active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "awarded_for", "created_at")


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 0


@admin.register(Quiz)
class QuizAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "reward_coins", "active", "issuer")
    list_editable = ("reward_coins", "active")
    inlines = (QuizQuestionInline,)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "quiz", "score", "completed", "coins_granted")
    list_filter = ("quiz", "completed", "coins_granted")


@admin.register(CallbackRequest)
class CallbackRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "subject", "preferred_time", "phone", "status")
    list_filter = ("status",)


@admin.register(FAQ)
class FAQAdmin(ReadOnlyIssuerAdmin):
    list_display = ("question", "category", "sort_order", "active", "issuer")
    list_editable = ("sort_order", "active")


@admin.register(Offer)
class OfferAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "offer_type", "audience", "starts_at", "ends_at", "active", "issuer")
    list_filter = ("offer_type", "audience", "active")


@admin.register(BeautyEvent)
class BeautyEventAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "starts_at", "ends_at", "capacity", "minimum_tier", "coin_cost", "active", "issuer")
    list_filter = ("active", "minimum_tier")


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "user", "guest_name", "status")
    list_filter = ("event", "status")


@admin.register(ContentArticle)
class ContentArticleAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "content_type", "category", "approved", "membership_only", "published_at", "active", "issuer")
    list_filter = ("content_type", "approved", "membership_only", "active")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(SavedContent)
class SavedContentAdmin(admin.ModelAdmin):
    list_display = ("user", "article", "created_at")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "appointment", "overall_rating", "private_to_management", "verified")
    list_filter = ("overall_rating", "private_to_management", "verified")


@admin.register(Survey)
class SurveyAdmin(ReadOnlyIssuerAdmin):
    list_display = ("title", "starts_at", "ends_at", "reward_coins", "active", "issuer")
    list_filter = ("active",)


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ("created_at", "survey", "user", "completed", "coins_granted")
    list_filter = ("survey", "completed", "coins_granted")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "subject", "priority", "status", "assigned_to", "resolved_at")
    list_filter = ("priority", "status")


@admin.register(ConciergeRequest)
class ConciergeRequestAdmin(ReadOnlyIssuerAdmin):
    list_display = ("created_at", "user", "request_type", "title", "status", "assigned_to", "issuer")
    list_filter = ("request_type", "status")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "push_enabled", "email_enabled", "appointment_reminders", "aftercare_reminders", "marketing_messages", "hide_sensitive_text")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "active", "last_success_at", "created_at", "updated_at")
    readonly_fields = ("endpoint", "p256dh", "auth", "user_agent", "last_error")


@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
    list_display = ("scheduled_for", "user", "channel", "title", "status", "attempts", "sensitive")
    list_filter = ("channel", "status", "sensitive")


@admin.register(DataExportRequest)
class DataExportRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "status", "completed_at", "expires_at")
    list_filter = ("status",)


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "status", "scheduled_for", "completed_at")
    list_filter = ("status",)


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "device_name", "ip_address", "last_seen_at", "revoked_at")
    list_filter = ("revoked_at",)


@admin.register(IntegrationCredentialStatus)
class IntegrationCredentialStatusAdmin(admin.ModelAdmin):
    list_display = ("integration", "ready", "last_checked_at")
    readonly_fields = ("configured_variables", "last_checked_at")


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = ("provider", "user", "email", "email_verified", "created_at")
    list_filter = ("provider", "email_verified")


@admin.register(ExternalAppointmentLink)
class ExternalAppointmentLinkAdmin(admin.ModelAdmin):
    list_display = ("provider", "external_id", "appointment", "last_external_update_at", "conflict_state")
    list_filter = ("provider", "conflict_state")
