from django.contrib import admin

from .models import (
    Badge,
    BeautyEvent,
    Challenge,
    ChallengeParticipation,
    ConciergeRequest,
    EventRegistration,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    UserBadge,
)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "icon", "active", "updated_at")
    list_editable = ("active",)
    prepopulated_fields = {"key": ("name",)}
    exclude = ("is_medical_reward",)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "challenge_type", "target_count", "reward_coins", "starts_at", "ends_at", "active")
    list_filter = ("challenge_type", "active")
    list_editable = ("active",)
    search_fields = ("title", "description")
    exclude = ("medical_treatment_count_based",)


@admin.register(ChallengeParticipation)
class ChallengeParticipationAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "user", "challenge", "progress", "completed_at", "reward_granted")
    list_filter = ("reward_granted", "challenge")
    search_fields = ("user__username", "user__email", "challenge__title")
    readonly_fields = ("last_progress_on", "completed_at", "reward_granted", "created_at", "updated_at")


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "badge", "source_type", "source_id")
    search_fields = ("user__username", "user__email", "badge__name")
    readonly_fields = ("created_at", "updated_at")


class QuizQuestionInline(admin.StackedInline):
    model = QuizQuestion
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "passing_percent", "reward_coins", "approved", "active", "updated_at")
    list_filter = ("approved", "active")
    list_editable = ("approved", "active")
    search_fields = ("title", "description")
    exclude = ("medical_advice",)
    inlines = (QuizQuestionInline,)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "user", "quiz", "percent", "passed", "reward_granted")
    list_filter = ("passed", "reward_granted", "quiz")
    search_fields = ("user__username", "user__email", "quiz__title")
    readonly_fields = ("answers", "score", "total_questions", "percent", "completed", "passed", "reward_granted", "completed_at", "created_at", "updated_at")


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(BeautyEvent)
class BeautyEventAdmin(admin.ModelAdmin):
    list_display = ("starts_at", "title", "location", "capacity", "allow_guest", "active")
    list_filter = ("active", "allow_guest")
    list_editable = ("active",)
    search_fields = ("title", "description", "location")
    exclude = ("medical_service_reward",)
    inlines = (EventRegistrationInline,)


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "user", "seat_count", "status", "guest_name")
    list_filter = ("status", "event")
    search_fields = ("user__username", "user__email", "event__title", "guest_name")


@admin.register(ConciergeRequest)
class ConciergeRequestAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "user", "request_type", "title", "status", "thread")
    list_filter = ("request_type", "status")
    list_editable = ("status",)
    search_fields = ("user__username", "user__email", "title", "details")
    exclude = ("medical_decision_support",)
    readonly_fields = ("user", "thread", "request_type", "title", "details", "created_at", "updated_at")
