import json
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from platform_app.mobile_api import _token_for
from platform_app.models import MemberAccount, WalletAccount

from .models import CabinetProduct, RoutineStep, ShopCategory, ShopOrder, ShopProduct


class P2ExperienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="p2@example.de",
            email="p2@example.de",
            password="Test-Password-123!",
            first_name="Paula",
            last_name="Plus",
        )
        self.other = User.objects.create_user(
            username="other-p2@example.de",
            email="other-p2@example.de",
            password="Other-Password-123!",
        )
        self.token = _token_for(self.user)
        self.other_token = _token_for(self.other)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.other_auth = {"HTTP_AUTHORIZATION": f"Bearer {self.other_token}"}

        self.category = ShopCategory.objects.create(name="Pflege", slug="pflege", active=True, sort_order=10)
        self.product = ShopProduct.objects.create(
            category=self.category,
            name="A+ Daily Care",
            slug="a-plus-daily-care",
            description="Kosmetisches Pflegeprodukt",
            price_cents=2500,
            stock_quantity=5,
            active=True,
            allow_collect=True,
            allow_shipping=True,
        )

    def test_p2_requires_mobile_authentication(self):
        self.assertEqual(self.client.get("/api/mobile/wallet-pass/").status_code, 401)
        self.assertEqual(self.client.get("/api/mobile/cabinet/").status_code, 401)
        self.assertEqual(self.client.get("/api/mobile/shop/").status_code, 401)

    def test_wallet_card_works_without_provider_credentials_and_hides_qr_secret(self):
        with mock.patch("p2_app.views.wallet_provider_status", return_value={"apple": False, "google": False}):
            response = self.client.get("/api/mobile/wallet-pass/", **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["card"]["name"], "Paula Plus")
        self.assertTrue(payload["card"]["member_number"].startswith("AP-"))
        self.assertNotIn("qr_token", payload["card"])
        self.assertFalse(payload["providers"]["apple"]["configured"])
        self.assertFalse(payload["providers"]["google"]["configured"])
        self.assertTrue(MemberAccount.objects.filter(user=self.user).exists())
        self.assertTrue(WalletAccount.objects.filter(user=self.user).exists())

        qr = self.client.get("/api/mobile/wallet-pass/qr/", **self.auth)
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr["Content-Type"], "image/png")
        self.assertEqual(qr["Cache-Control"], "private, no-store, max-age=0")

    def test_wallet_provider_missing_is_graceful(self):
        with mock.patch("p2_app.views.wallet_provider_status", return_value={"apple": False, "google": False}):
            apple = self.client.get("/api/mobile/wallet-pass/apple/", **self.auth)
            google = self.client.get("/api/mobile/wallet-pass/google/", **self.auth)
        self.assertEqual(apple.status_code, 503)
        self.assertEqual(apple.json()["error"], "wallet_provider_not_configured")
        self.assertEqual(google.status_code, 503)
        self.assertEqual(google.json()["error"], "wallet_provider_not_configured")

    def test_cabinet_and_routine_are_owner_scoped(self):
        created = self.client.post(
            "/api/mobile/cabinet/",
            data=json.dumps({
                "name": "Mein Serum",
                "brand": "A+",
                "category": "Serum",
                "opened_on": "2026-08-01",
                "expires_on": "2027-08-01",
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(created.status_code, 201, created.content)
        cabinet = CabinetProduct.objects.get(pk=created.json()["product"]["id"])

        routine = self.client.post(
            f"/api/mobile/cabinet/{cabinet.pk}/routine/",
            data=json.dumps({"period": "evening", "weekdays": [0, 2, 4], "note": "Eigene Routine"}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(routine.status_code, 201, routine.content)
        step = RoutineStep.objects.get(pk=routine.json()["routine_id"])

        forbidden_toggle = self.client.post(
            f"/api/mobile/cabinet/routine/{step.pk}/toggle/",
            data="{}",
            content_type="application/json",
            **self.other_auth,
        )
        self.assertEqual(forbidden_toggle.status_code, 404)

        listing = self.client.get("/api/mobile/cabinet/", **self.auth)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["name"] for item in listing.json()["products"]], ["Mein Serum"])
        self.assertEqual(listing.json()["products"][0]["routines"][0]["period"], "evening")

    def test_shop_uses_server_price_reserves_stock_and_cancel_restores_once(self):
        created = self.client.post(
            "/api/mobile/shop/orders/",
            data=json.dumps({
                "items": [{"product_id": self.product.pk, "quantity": 2, "price_cents": 1}],
                "delivery_method": "collect",
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(created.status_code, 201, created.content)
        order = ShopOrder.objects.get(pk=created.json()["order"]["id"])
        self.assertEqual(order.total_cents, 5000)
        self.assertEqual(order.items.get().unit_price_cents, 2500)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)

        forbidden = self.client.get(f"/api/mobile/shop/orders/{order.pk}/", **self.other_auth)
        self.assertEqual(forbidden.status_code, 404)

        cancelled = self.client.post(
            f"/api/mobile/shop/orders/{order.pk}/cancel/",
            data="{}",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        self.product.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(order.status, "cancelled")
        self.assertIsNotNone(order.stock_released_at)

        second = self.client.post(
            f"/api/mobile/shop/orders/{order.pk}/cancel/",
            data="{}",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(second.status_code, 409)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_shop_validates_shipping_and_stock(self):
        missing_address = self.client.post(
            "/api/mobile/shop/orders/",
            data=json.dumps({
                "items": [{"product_id": self.product.pk, "quantity": 1}],
                "delivery_method": "shipping",
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(missing_address.status_code, 400)
        self.assertEqual(missing_address.json()["error"], "shipping_address_required")

        insufficient = self.client.post(
            "/api/mobile/shop/orders/",
            data=json.dumps({
                "items": [{"product_id": self.product.pk, "quantity": 6}],
                "delivery_method": "collect",
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(insufficient.status_code, 400)
        self.assertEqual(insufficient.json()["error"], "insufficient_stock")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_prescription_product_is_blocked_by_model_validation(self):
        product = ShopProduct(
            name="Restricted",
            slug="restricted",
            price_cents=100,
            stock_quantity=1,
            is_prescription_product=True,
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_full_export_preserves_p1_and_isolates_p2_user_data(self):
        CabinetProduct.objects.create(user=self.user, name="Mein Produkt")
        CabinetProduct.objects.create(user=self.other, name="Fremdes Produkt")

        order_response = self.client.post(
            "/api/mobile/shop/orders/",
            data=json.dumps({"items": [{"product_id": self.product.pk, "quantity": 1}], "delivery_method": "collect"}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(order_response.status_code, 201)

        response = self.client.get("/api/mobile/export/", **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertIn("progress_albums", data)
        self.assertIn("beauty_plans", data)
        self.assertEqual([item["name"] for item in data["beauty_cabinet"]], ["Mein Produkt"])
        self.assertEqual(len(data["shop_orders"]), 1)
        self.assertIn("wallet_passes", data)
