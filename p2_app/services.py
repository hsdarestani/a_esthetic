from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import ShopOrder, ShopOrderEvent, ShopOrderItem, ShopProduct


MAX_ORDER_QUANTITY_PER_PRODUCT = 20
MAX_ORDER_TOTAL_CENTS = 2_000_000


def _normalise_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items:
        raise ValidationError("items_required")

    quantities = defaultdict(int)
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValidationError("invalid_order_item")
        try:
            product_id = int(raw.get("product_id"))
            quantity = int(raw.get("quantity") or 1)
        except (TypeError, ValueError):
            raise ValidationError("invalid_order_item")
        if product_id <= 0 or quantity <= 0:
            raise ValidationError("invalid_order_item")
        quantities[product_id] += quantity
        if quantities[product_id] > MAX_ORDER_QUANTITY_PER_PRODUCT:
            raise ValidationError("quantity_too_large")
    return quantities


@transaction.atomic
def create_shop_order(*, user, raw_items, delivery_method, shipping_name="", shipping_address="", customer_note=""):
    quantities = _normalise_items(raw_items)
    if delivery_method not in {value for value, _ in ShopOrder.DELIVERY}:
        raise ValidationError("invalid_delivery_method")
    if delivery_method == "shipping" and not str(shipping_address or "").strip():
        raise ValidationError("shipping_address_required")

    products = {
        product.pk: product
        for product in ShopProduct.objects.select_for_update().filter(pk__in=quantities.keys(), active=True)
    }
    if len(products) != len(quantities):
        raise ValidationError("product_unavailable")

    total_cents = 0
    for product_id, quantity in quantities.items():
        product = products[product_id]
        if delivery_method == "shipping" and not product.allow_shipping:
            raise ValidationError("product_not_shippable")
        if delivery_method == "collect" and not product.allow_collect:
            raise ValidationError("product_not_collectable")
        if product.stock_quantity < quantity:
            raise ValidationError("insufficient_stock")
        total_cents += product.price_cents * quantity

    if total_cents > MAX_ORDER_TOTAL_CENTS:
        raise ValidationError("order_total_too_large")

    order = ShopOrder.objects.create(
        user=user,
        delivery_method=delivery_method,
        shipping_name=str(shipping_name or "").strip()[:160],
        shipping_address=str(shipping_address or "").strip()[:3000],
        customer_note=str(customer_note or "").strip()[:3000],
        total_cents=total_cents,
        status="pending",
    )

    for product_id, quantity in quantities.items():
        product = products[product_id]
        line_total = product.price_cents * quantity
        ShopOrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=quantity,
            unit_price_cents=product.price_cents,
            line_total_cents=line_total,
        )
        product.stock_quantity -= quantity
        product.save(update_fields=["stock_quantity", "updated_at"])

    ShopOrderEvent.objects.create(
        order=order,
        status="pending",
        note="Bestellung über die A+ App eingegangen.",
        visible_to_customer=True,
    )
    return order


@transaction.atomic
def release_reserved_stock(order):
    locked = ShopOrder.objects.select_for_update().get(pk=order.pk)
    if locked.stock_released_at is not None:
        return False

    for item in locked.items.select_related("product").all():
        product = ShopProduct.objects.select_for_update().get(pk=item.product_id)
        product.stock_quantity += item.quantity
        product.save(update_fields=["stock_quantity", "updated_at"])

    locked.stock_released_at = timezone.now()
    locked.save(update_fields=["stock_released_at", "updated_at"])
    return True


def record_status_event(order, *, note=""):
    return ShopOrderEvent.objects.create(
        order=order,
        status=order.status,
        note=str(note or "").strip()[:300],
        visible_to_customer=True,
    )
