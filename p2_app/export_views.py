import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from p0_app import views as p0_views
from p1_app import export_views as p1_export_views

from .models import CabinetProduct, MemberPass, RoutineStep, ShopOrder


@csrf_exempt
@require_http_methods(["GET"])
def mobile_full_export(request):
    base_response = p1_export_views.mobile_full_export(request)
    if base_response.status_code != 200:
        return base_response

    payload = json.loads(base_response.content.decode("utf-8"))
    user, error = p0_views._auth(request)
    if error:
        return error

    payload["data"]["wallet_passes"] = list(
        MemberPass.objects.filter(user=user).values(
            "id",
            "provider",
            "status",
            "external_object_id",
            "last_synced_at",
            "created_at",
            "updated_at",
        )
    )
    payload["data"]["beauty_cabinet"] = [
        {
            "id": product.pk,
            "name": product.name,
            "brand": product.brand,
            "barcode": product.barcode,
            "category": product.category,
            "opened_on": product.opened_on.isoformat() if product.opened_on else None,
            "expires_on": product.expires_on.isoformat() if product.expires_on else None,
            "notes": product.notes,
            "source": product.source,
            "shop_product_id": product.shop_product_id,
            "archived": product.archived,
            "created_at": product.created_at.isoformat(),
            "updated_at": product.updated_at.isoformat(),
            "routines": list(
                RoutineStep.objects.filter(user=user, product=product).values(
                    "id", "period", "weekdays", "note", "sort_order", "active", "created_at", "updated_at"
                )
            ),
        }
        for product in CabinetProduct.objects.filter(user=user)
    ]
    payload["data"]["shop_orders"] = [
        {
            "id": order.pk,
            "order_number": order.order_number,
            "status": order.status,
            "delivery_method": order.delivery_method,
            "shipping_name": order.shipping_name,
            "shipping_address": order.shipping_address,
            "customer_note": order.customer_note,
            "total_cents": order.total_cents,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "items": list(order.items.values(
                "id", "product_id", "product_name", "quantity", "unit_price_cents", "line_total_cents", "created_at"
            )),
            "events": list(order.events.filter(visible_to_customer=True).values(
                "id", "status", "note", "created_at"
            )),
        }
        for order in ShopOrder.objects.filter(user=user).prefetch_related("items", "events")
    ]

    response = JsonResponse(payload)
    response["Content-Disposition"] = base_response.get(
        "Content-Disposition",
        f'attachment; filename="a-plus-esthetic-data-{user.pk}.json"',
    )
    return response
