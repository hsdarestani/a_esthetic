from django.contrib import admin

from .models import (
    AftercareTask,
    AftercareTaskStatus,
    AftercareTemplate,
    AssignedAftercare,
    BeautyPlan,
    BeautyPlanStep,
    ProgressAlbum,
    ProgressPhoto,
)


class AftercareTaskInline(admin.TabularInline):
    model = AftercareTask
    extra = 0


@admin.register(AftercareTemplate)
class AftercareTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "service", "version", "approved_by", "active")
    list_filter = ("active", "service")
    search_fields = ("title", "service__name", "approved_by")
    inlines = [AftercareTaskInline]


class AftercareTaskStatusInline(admin.TabularInline):
    model = AftercareTaskStatus
    extra = 0
    readonly_fields = ("task", "completed", "completed_at")


@admin.register(AssignedAftercare)
class AssignedAftercareAdmin(admin.ModelAdmin):
    list_display = ("user", "template", "appointment", "starts_at", "completed_at")
    list_filter = ("template", "completed_at")
    search_fields = ("user__email", "user__username", "template__title")
    inlines = [AftercareTaskStatusInline]


class ProgressPhotoInline(admin.TabularInline):
    model = ProgressPhoto
    extra = 0
    readonly_fields = ("sha256", "uploaded_by", "created_at")


@admin.register(ProgressAlbum)
class ProgressAlbumAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "marketing_use_allowed", "created_at")
    search_fields = ("title", "user__email", "user__username")
    readonly_fields = ("marketing_use_allowed",)
    inlines = [ProgressPhotoInline]


class BeautyPlanStepInline(admin.TabularInline):
    model = BeautyPlanStep
    extra = 0


@admin.register(BeautyPlan)
class BeautyPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "journey_type", "status", "target_date", "updated_at")
    list_filter = ("status", "journey_type")
    search_fields = ("title", "user__email", "user__username", "goal")
    readonly_fields = ("medical_decision_support",)
    inlines = [BeautyPlanStepInline]


admin.site.register(ProgressPhoto)
admin.site.register(AftercareTask)
admin.site.register(AftercareTaskStatus)
admin.site.register(BeautyPlanStep)
