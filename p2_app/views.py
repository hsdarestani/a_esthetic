import json
from datetime import date
from io import BytesIO

import qrcode
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from platform_app import mobile_api as legacy_mobile_api
from platform_app.models import AuditLog, MemberAccount, WalletAccount

from .models import (
    CabinetProduct,
    MemberPass,
    RoutineStep,
    ShopCategory,
    ShopOrder,
    ShopProduct,
)
from .passes import build_apple_pass, google_save_url, wallet_provider_status
from .services import create_shop_order, record_status_event, release_reserved_stock


def _auth(request):
    return legacy_mobile_api._auth(request)


def _json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _audit(request, user, action, entity, metadata=None):
    AuditLog.objects.create(
        actor=user,
        action=action,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        metadata=metadata or {},
        ip_address=request.META.get("REMOTE_ADDR"),
    )


def _parse_date(value, error_code):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError(error_code)


def _cabinet_payload(product):
    return {
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
        "routines": [
            {
                "id": step.pk,
                "period": step.period,
                "period_label": step.get_period_display(),
                "weekdays": step.weekdays,
                "note": step.note,
                "sort_order": step.sort_order,
                "active": step.active,
            }
            for step in product.routine_steps.all()
        ],
    }


def _order_payload(order):
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "status": order.status,
        "status_label": order.get_status_display(),
        "delivery_method": order.delivery_method,
        "delivery_label": order.get_delivery_method_display(),
        "shipping_name": order.shipping_name,
        "shipping_address": order.shipping_address,
        "customer_note": order.customer_note,
        "total_cents": order.total_cents,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "can_cancel": order.status == "pending" and order.stock_released_at is None,
        "items": [
            {
                "id": item.pk,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price_cents": item.unit_price_cents,
                "line_total_cents": item.line_total_cents,
            }
            for item in order.items.all()
        ],
        "events": [
            {
                "id": event.pk,
                "status": event.status,
                "status_label": event.get_status_display(),
                "note": event.note,
                "created_at": event.created_at.isoformat(),
            }
            for event in order.events.filter(visible_to_customer=True)
        ],
    }


@csrf_exempt
@require_http_methods(["GET"])
def mobile_wallet_pass(request):
    user, error = _auth(request)
    if error:
        return error

    member, _ = MemberAccount.objects.get_or_create(user=user)
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    providers = wallet_provider_status()
    passes = {item.provider: item for item in MemberPass.objects.filter(user=user)}
    tier = member.tier.name if member.tier else "A+ Member"

    return JsonResponse({
        "ok": True,
        "card": {
            "name": user.get_full_name() or user.email or user.username,
            "member_number": member.member_number,
            "tier": tier,
            "status": member.status,
            "status_label": member.get_status_display(),
            "valid_until": member.valid_until.isoformat() if member.valid_until else None,
            "coin_balance": wallet.coin_balance,
            "credit_cents": wallet.balance_cents,
            "qr_url": "/wallet-pass/qr/",
        },
        "providers": {
            provider: {
                "configured": configured,
                "status": passes[provider].status if provider in passes else "pending",
                "last_synced_at": passes[provider].last_synced_at.isoformat() if provider in passes and passes[provider].last_synced_at else None,
            }
            for provider, configured in providers.items()
        },
        "note": "Die A+ Mitgliedskarte ist keine Zahlungskarte und enthält keine medizinische Empfehlung.",
    })


@csrf_exempt
@require_http_methods(["GET"])
def mobile_wallet_qr(request):
    user, error = _auth(request)
    if error:
        return error
    member, _ = MemberAccount.objects.get_or_create(user=user)
    image = qrcode.make(member.qr_token)
    output = BytesIO()
    image.save(output, format="PNG")
    response = HttpResponse(output.getvalue(), content_type="image/png")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@csrf_exempt
@require_http_methods(["GET"])
def mobile_wallet_apple(request):
    user, error = _auth(request)
    if error:
        return error
    if not wallet_provider_status()["apple"]:
        MemberPass.objects.get_or_create(user=user, provider="apple")
        return JsonResponse({"ok": False, "error": "wallet_provider_not_configured", "provider": "apple"}, status=503)
    try:
        output = build_apple_pass(user)
    except ImproperlyConfigured:
        return JsonResponse({"ok": False, "error": "wallet_provider_not_configured", "provider": "apple"}, status=503)
    except Exception:
        return JsonResponse({"ok": False, "error": "wallet_generation_failed", "provider": "apple"}, status=500)

    record = MemberPass.objects.get(user=user, provider="apple")
    _audit(request, user, "Apple Wallet Mitgliedskarte erzeugt", record)
    response = HttpResponse(output.getvalue(), content_type="application/vnd.apple.pkpass")
    response["Content-Disposition"] = 'attachment; filename="A-Plus-Esthetic.pkpass"'
    response["Cache-Control"] = "private, no-store, max-age=0"
    return response


@csrf_exempt
@require_http_methods(["GET"])
def mobile_wallet_google(request):
    user, error = _auth(request)
    if error:
        return error
    if not wallet_provider_status()["google"]:
        MemberPass.objects.get_or_create(user=user, provider="google")
        return JsonResponse({"ok": False, "error": "wallet_provider_not_configured", "provider": "google"}, status=503)
    try:
        save_url = google_save_url(user)
    except ImproperlyConfigured:
        return JsonResponse({"ok": False, "error": "wallet_provider_not_configured", "provider": "google"}, status=503)
    except Exception:
        return JsonResponse({"ok": False, "error": "wallet_generation_failed", "provider": "google"}, status=500)

    record = MemberPass.objects.get(user=user, provider="google")
    _audit(request, user, "Google Wallet Mitgliedskarte erzeugt", record)
    return JsonResponse({"ok": True, "save_url": save_url})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_cabinet(request):
    user, error = _auth(request)
    if error:
        return error

    if request.method == "POST":
        data = _json(request)
        shop_product = None
        if data.get("shop_product_id"):
            try:
                shop_product_id = int(data["shop_product_id"])
            except (TypeError, ValueError):
                return JsonResponse({"ok": False, "error": "invalid_shop_product"}, status=400)
            shop_product = ShopProduct.objects.filter(pk=shop_product_id, active=True).select_related("category").first()
            if not shop_product:
                return JsonResponse({"ok": False, "error": "invalid_shop_product"}, status=400)

        name = str(data.get("name") or (shop_product.name if shop_product else "")).strip()[:180]
        if not name:
            return JsonResponse({"ok": False, "error": "name_required"}, status=400)
        try:
            opened_on = _parse_date(data.get("opened_on"), "invalid_opened_date")
            expires_on = _parse_date(data.get("expires_on"), "invalid_expiry_date")
        except ValidationError as exc:
            return JsonResponse({"ok": False, "error": exc.messages[0]}, status=400)
        if opened_on and expires_on and expires_on < opened_on:
            return JsonResponse({"ok": False, "error": "expiry_before_opened"}, status=400)

        product = CabinetProduct.objects.create(
            user=user,
            name=name,
            brand=str(data.get("brand") or "").strip()[:120],
            barcode=str(data.get("barcode") or "").strip()[:64],
            category=str(data.get("category") or (shop_product.category.name if shop_product and shop_product.category else "")).strip()[:80],
            opened_on=opened_on,
            expires_on=expires_on,
            notes=str(data.get("notes") or "").strip()[:3000],
            source="shop" if shop_product else "manual",
            shop_product=shop_product,
        )
        _audit(request, user, "Produkt zum Beauty Cabinet hinzugefügt", product, {"source": product.source})
        return JsonResponse({"ok": True, "product": _cabinet_payload(product)}, status=201)

    products = CabinetProduct.objects.filter(user=user).select_related("shop_product").prefetch_related("routine_steps")
    return JsonResponse({
        "ok": True,
        "safety_note": "Das Beauty Cabinet organisiert Ihre eigenen Produkte und Routinen. Es erstellt keine medizinischen Empfehlungen.",
        "periods": [{"value": value, "label": label} for value, label in RoutineStep.PERIOD],
        "products": [_cabinet_payload(product) for product in products],
    })


@csrf_exempt
@require_http_methods(["POST"])
def mobile_cabinet_archive(request, product_id):
    user, error = _auth(request)
    if error:
        return error
    product = CabinetProduct.objects.filter(pk=product_id, user=user).first()
    if not product:
        return JsonResponse({"ok": False, "error": "cabinet_product_not_found"}, status=404)
    data = _json(request)
    product.archived = bool(data.get("archived", not product.archived))
    product.save(update_fields=["archived", "updated_at"])
    _audit(request, user, "Beauty Cabinet Produkt archiviert" if product.archived else "Beauty Cabinet Produkt reaktiviert", product)
    return JsonResponse({"ok": True, "archived": product.archived})


@csrf_exempt
@require_http_methods(["DELETE"])
def mobile_cabinet_delete(request, product_id):
    user, error = _auth(request)
    if error:
        return error
    product = CabinetProduct.objects.filter(pk=product_id, user=user).first()
    if not product:
        return JsonResponse({"ok": False, "error": "cabinet_product_not_found"}, status=404)
    _audit(request, user, "Beauty Cabinet Produkt gelöscht", product)
    product.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_cabinet_routine(request, product_id):
    user, error = _auth(request)
    if error:
        return error
    product = CabinetProduct.objects.filter(pk=product_id, user=user, archived=False).first()
    if not product:
        return JsonResponse({"ok": False, "error": "cabinet_product_not_found"}, status=404)
    data = _json(request)
    period = str(data.get("period") or "morning")
    if period not in {value for value, _ in RoutineStep.PERIOD}:
        return JsonResponse({"ok": False, "error": "invalid_routine_period"}, status=400)
    weekdays = data.get("weekdays") or []
    if not isinstance(weekdays, list):
        return JsonResponse({"ok": False, "error": "invalid_weekdays"}, status=400)
    try:
        weekdays = sorted(set(int(day) for day in weekdays))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_weekdays"}, status=400)
    if any(day < 0 or day > 6 for day in weekdays):
        return JsonResponse({"ok": False, "error": "invalid_weekdays"}, status=400)
    try:
        sort_order = max(0, min(int(data.get("sort_order") or 100), 10_000))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_sort_order"}, status=400)

    step = RoutineStep(
        user=user,
        product=product,
        period=period,
        weekdays=weekdays,
        note=str(data.get("note") or "").strip()[:300],
        sort_order=sort_order,
        active=True,
    )
    try:
        step.full_clean()
    except ValidationError:
        return JsonResponse({"ok": False, "error": "invalid_routine"}, status=400)
    step.save()
    _audit(request, user, "Beauty Routine Schritt erstellt", step, {"period": period})
    return JsonResponse({"ok": True, "routine_id": step.pk}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def mobile_routine_toggle(request, routine_id):
    user, error = _auth(request)
    if error:
        return error
    step = RoutineStep.objects.filter(pk=routine_id, user=user, product__user=user).first()
    if not step:
        return JsonResponse({"ok": False, "error": "routine_not_found"}, status=404)
    step.active = not step.active
    step.save(update_fields=["active", "updated_at"])
    _audit(request, user, "Beauty Routine Schritt aktualisiert", step, {"active": step.active})
    return JsonResponse({"ok": True, "active": step.active})


@csrf_exempt
@require_http_methods(["DELETE"])
def mobile_routine_delete(request, routine_id):
    user, error = _auth(request)
    if error:
        return error
    step = RoutineStep.objects.filter(pk=routine_id, user=user, product__user=user).first()
    if not step:
        return JsonResponse({"ok": False, "error": "routine_not_found"}, status=404)
    _audit(request, user, "Beauty Routine Schritt gelöscht", step)
    step.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET"])
def mobile_shop(request):
    user, error = _auth(request)
    if error:
        return error
    categories = ShopCategory.objects.filter(active=True).prefetch_related("products")
    products = ShopProduct.objects.filter(active=True).select_related("category")
    orders = ShopOrder.objects.filter(user=user).prefetch_related("items", "events")[:20]
    return JsonResponse({
        "ok": True,
        "payment_note": "Bestellungen werden in der App erfasst. Zahlungsstatus und Versand/Abholung werden anschließend durch A+ bestätigt.",
        "categories": [{"id": category.pk, "name": category.name, "slug": category.slug} for category in categories],
        "products": [
            {
                "id": product.pk,
                "name": product.name,
                "slug": product.slug,
                "category": product.category.name if product.category else "",
                "description": product.description,
                "ingredients": product.ingredients,
                "price_cents": product.price_cents,
                "stock_quantity": product.stock_quantity,
                "in_stock": product.in_stock,
                "allow_collect": product.allow_collect,
                "allow_shipping": product.allow_shipping,
                "image_url": product.image_url,
            }
            for product in products
        ],
        "orders": [_order_payload(order) for order in orders],
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mobile_shop_orders(request):
    user, error = _auth(request)
    if error:
        return error

    if request.method == "POST":
        data = _json(request)
        try:
            order = create_shop_order(
                user=user,
                raw_items=data.get("items"),
                delivery_method=str(data.get("delivery_method") or "collect"),
                shipping_name=data.get("shipping_name") or "",
                shipping_address=data.get("shipping_address") or "",
                customer_note=data.get("customer_note") or "",
            )
        except ValidationError as exc:
            return JsonResponse({"ok": False, "error": exc.messages[0]}, status=400)
        order = ShopOrder.objects.prefetch_related("items", "events").get(pk=order.pk)
        _audit(request, user, "Shop-Bestellung erstellt", order, {"order_number": order.order_number, "total_cents": order.total_cents})
        return JsonResponse({"ok": True, "order": _order_payload(order)}, status=201)

    orders = ShopOrder.objects.filter(user=user).prefetch_related("items", "events")
    return JsonResponse({"ok": True, "orders": [_order_payload(order) for order in orders]})


@csrf_exempt
@require_http_methods(["GET"])
def mobile_shop_order_detail(request, order_id):
    user, error = _auth(request)
    if error:
        return error
    order = ShopOrder.objects.filter(pk=order_id, user=user).prefetch_related("items", "events").first()
    if not order:
        return JsonResponse({"ok": False, "error": "order_not_found"}, status=404)
    return JsonResponse({"ok": True, "order": _order_payload(order)})


@csrf_exempt
@require_http_methods(["POST"])
def mobile_shop_order_cancel(request, order_id):
    user, error = _auth(request)
    if error:
        return error

    with transaction.atomic():
        order = ShopOrder.objects.select_for_update().filter(pk=order_id, user=user).first()
        if not order:
            return JsonResponse({"ok": False, "error": "order_not_found"}, status=404)
        if order.status != "pending":
            return JsonResponse({"ok": False, "error": "order_cannot_be_cancelled"}, status=409)
        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])
        release_reserved_stock(order)
        record_status_event(order, note="Vom Kunden in der A+ App storniert.")
        _audit(request, user, "Shop-Bestellung storniert", order, {"order_number": order.order_number})

    order = ShopOrder.objects.prefetch_related("items", "events").get(pk=order.pk)
    return JsonResponse({"ok": True, "order": _order_payload(order)})
