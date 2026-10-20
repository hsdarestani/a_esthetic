import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from platform_app.models import UserProfile, WalletAccount, WalletTransaction


class BookWalletBridgeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="wallet-bridge-admin", is_active=True)
        UserProfile.objects.create(user=self.admin, role="admin")
        self.patient = User.objects.create_user(
            username="wallet-bridge-customer", email="wallet@example.test", is_active=True,
            first_name="Anna", last_name="Muster",
        )
        UserProfile.objects.create(user=self.patient, role="customer")
        WalletAccount.objects.create(user=self.patient, coin_balance=150)
        self.root = "/api/mobile/internal/book-wallet/"

    def test_browser_without_sync_token_cannot_view_wallet(self):
        response = self.client.get(self.root + "customers/")
        self.assertEqual(response.status_code, 401)
        response = self.client.post(self.root + f"adjust/{self.patient.pk}/",
            json.dumps({"coin_delta": 100}), content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(WalletTransaction.objects.count(), 0)

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_authorized_server_can_list_customers(self, auth):
        response = self.client.get(self.root + "customers/?q=wallet")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(len(response.json()["customers"]), 1)

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_only_coin_delta_adjustments_are_allowed(self, auth):
        response = self.client.post(self.root + f"adjust/{self.patient.pk}/",
            json.dumps({"coin_delta": 75, "credit_delta_cents": 1000}),
            content_type="application/json")
        self.assertEqual(response.status_code, 400)
        wallet = WalletAccount.objects.get(user=self.patient)
        self.assertEqual(wallet.coin_balance, 150)

        valid = self.client.post(self.root + f"adjust/{self.patient.pk}/",
            json.dumps({"coin_delta": 50}), content_type="application/json")
        self.assertEqual(valid.status_code, 200, valid.content)
        wallet.refresh_from_db()
        self.assertEqual(wallet.coin_balance, 200)
        self.assertEqual(WalletTransaction.objects.filter(user=self.patient, kind="coin").count(), 1)

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_wallet_history_access_and_nonexistent_endpoint(self, auth):
        response = self.client.get(self.root + f"history/{self.patient.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(self.client.get(self.root + "delete/").status_code, 404)
