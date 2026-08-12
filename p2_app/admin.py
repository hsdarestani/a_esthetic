from django.contrib import admin

from .models import (
    CabinetProduct,
    MemberPass,
    RoutineStep,
    ShopCategory,
    ShopOrder,
    ShopOrderEvent,
    ShopOrderItem,
    ShopProduct,
)
from .services import record_status_event, release_reserved_stock


@admin.register(MemberPass)
class MemberPassAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "status", "last_synced_at", "updated_at")
    list_filter = ("provider", "status")
    search_fields = ("user__email", "user__username", "external_object_id")
    readonly_fields = ("serial_number", "external_object_id", "last_error", "last_synced_at", "created_at", "updated_at")


@admin.register(ShopCategory)
class ShopCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active", "sort_order")
    list_editable = ("active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ShopProduct)
class ShopProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price_cents", "stock_quantity", "active", "allow_collect", "allow_shipping")
    list_filter = ("active", "allow_collect", "allow_shipping", "category")
    search_fields = ("name", "slug", "sku")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("is_prescription_product", "created_at", "updated_at")


class RoutineStepInline(admin.TabularInline):
    model = RoutineStep
    extra = 0
    fields = ("period", "weekdays", "note", "sort_order", "active")


@admin.register(CabinetProduct)
class CabinetProductAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "brand", "category", "expires_on", "source", "archived")
    list_filter = ("source", "archived", "category")
    search_fields = ("name", "brand", "barcode", "user__email", "user__username")
    readonly_fields = ("created_at", "updated_at")
    inlines = [RoutineStepInline]


class ShopOrderItemInline(admin.TabularInline):
    model = ShopOrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "quantity", "unit_price_cents", "line_total_cents", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


class ShopOrderEventInline(admin.TabularInline):
    model = ShopOrderEvent
    extra = 0
    can_delete = False
    readonly_fields = ("status", "note", "visible_to_customer", "created_at", "updated_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ShopOrder)
class ShopOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "delivery_method", "total_cents", "created_at")
    list_filter = ("status", "delivery_method", "created_at")
    search_fields = ("order_number", "user__email", "user__username", "shipping_name")
    readonly_fields = (
        "order_number",
        "user",
        "delivery_method",
        "shipping_name",
        "shipping_address",
        "customer_note",
        "total_cents",
        "stock_released_at",
        "created_at",
        "updated_at",
    )
    inlines = [ShopOrderItemInline, ShopOrderEventInline]

    def save_model(self, request, obj, form, change):
        previous_status = None
        if obj.pk:
            previous_status = ShopOrder.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
        super().save_model(request, obj, form, change)
        if previous_status and previous_status != obj.status:
            if obj.status == "cancelled":
                release_reserved_stock(obj)
            record_status_event(obj, note=f"Status durch A+ Team auf „{obj.get_status_display()}“ gesetzt.")


@admin.register(RoutineStep)
class RoutineStepAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "period", "sort_order", "active")
    list_filter = ("period", "active")
    search_fields = ("product__name", "user__email", "user__username")


@admin.register(ShopOrderEvent)
class ShopOrderEventAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "visible_to_customer", "created_at")
    list_filter = ("status", "visible_to_customer")
    search_fields = ("order__order_number", "note")
    readonly_fields = ("order", "status", "note", "visible_to_customer", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
