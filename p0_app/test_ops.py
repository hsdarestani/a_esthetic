import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from platform_app.mobile_api import _token_for
from platform_app.models import Reward, UserProfile, WalletAccount

from .ops_models import AppNotification, PushDevice, RewardRedemption


class CustomerOpsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ops@example.de",
            email="ops@example.de",
            password="Password-123!",
            first_name="Ops",
        )
        self.admin = User.objects.create_user(
            username="admin@example.de",
            email="admin@example.de",
            password="Password-123!",
            is_staff=True,
            is_superuser=True,
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        WalletAccount.objects.create(user=self.user, coin_balance=500)
        WalletAccount.objects.create(user=self.admin, coin_balance=0)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_token_for(self.user)}"}
        self.admin_auth = {"HTTP_AUTHORIZATION": f"Bearer {_token_for(self.admin)}"}

    def post_json(self, path, payload=None, auth=None):
        return self.client.post(
            path,
            data=json.dumps(payload or {}),
            content_type="application/json",
            **(auth or self.auth),
        )

    def test_referral_uses_verified_book_email_relay(self):
        with mock.patch(
            "p0_app.referral_views._send_referral_email",
            return_value="https://esthetic.smarbiz.sbs/?ref=APLUS-ABCDEF1234",
        ) as sender:
            response = self.post_json("/api/mobile/club/", {"invited_email": "friend@example.de"})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()["email_sent"])
        sender.assert_called_once()
        referral = sender.call_args.args[0]
        request = sender.call_args.args[1]
        self.assertEqual(referral.invited_email, "friend@example.de")
        self.assertRegex(referral.code, r"^[A-HJ-NP-Z2-9]{6}$")
        self.assertTrue(request.headers.get("Authorization", "").startswith("Bearer "))

    def test_reward_redemption_has_fulfillment_and_admin_can_complete(self):
        reward = Reward.objects.create(name="Test Reward", description="Test", coin_cost=100, inventory=2, active=True)
        redeemed = self.post_json(f"/api/mobile/wallet/reward/{reward.pk}/")
        self.assertEqual(redeemed.status_code, 201, redeemed.content)
        redemption = RewardRedemption.objects.get(pk=redeemed.json()["redemption"]["id"])
        self.assertEqual(redemption.status, "pending")
        self.assertEqual(WalletAccount.objects.get(user=self.user).coin_balance, 400)
        self.assertTrue(AppNotification.objects.filter(user=self.user, category="reward").exists())

        fulfilled = self.post_json(
            f"/api/mobile/admin/rewards/{redemption.pk}/",
            {"action": "fulfill", "note": "Ausgegeben"},
            auth=self.admin_auth,
        )
        self.assertEqual(fulfilled.status_code, 200, fulfilled.content)
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, "fulfilled")
        self.assertEqual(redemption.fulfilled_by, self.admin)

    def test_cancelled_reward_refunds_coins_and_inventory(self):
        reward = Reward.objects.create(name="Refund Reward", coin_cost=120, inventory=1, active=True)
        redeemed = self.post_json(f"/api/mobile/wallet/reward/{reward.pk}/")
        redemption_id = redeemed.json()["redemption"]["id"]
        cancelled = self.post_json(
            f"/api/mobile/admin/rewards/{redemption_id}/",
            {"action": "cancel"},
            auth=self.admin_auth,
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        self.assertEqual(WalletAccount.objects.get(user=self.user).coin_balance, 500)
        reward.refresh_from_db()
        self.assertEqual(reward.inventory, 1)

    def test_notification_center_and_device_registration(self):
        registered = self.post_json(
            "/api/mobile/notifications/devices/",
            {"token": "fake-device-token", "platform": "android", "app_version": "test"},
        )
        self.assertEqual(registered.status_code, 201, registered.content)
        self.assertTrue(PushDevice.objects.filter(user=self.user, enabled=True).exists())
        AppNotification.objects.create(user=self.user, title="Hallo", body="Test")
        listing = self.client.get("/api/mobile/notifications/", **self.auth)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["unread_count"], 1)
        item_id = listing.json()["notifications"][0]["id"]
        read = self.post_json(f"/api/mobile/notifications/{item_id}/read/")
        self.assertEqual(read.status_code, 200)
        self.assertTrue(read.json()["notification"]["read"])

    def test_admin_customer_and_settings_access_is_protected(self):
        denied = self.client.get("/api/mobile/admin/", **self.auth)
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.get("/api/mobile/admin/", **self.admin_auth)
        self.assertEqual(allowed.status_code, 200, allowed.content)
        self.assertEqual(allowed.json()["links"]["book_admin"], "https://book.a-esthetic.de/verwaltung/")

    def test_private_doctor_booking_push_targets_only_own_device_account(self):
        from django.contrib.auth.models import Group
        doctor = User.objects.create_user(
            username="qamar", email="qamar@a-esthetic.de", password="DoctorTest123!",
            first_name="Qamar", last_name="Hameed")
        UserProfile.objects.create(user=doctor, role="specialist")
        doctor.groups.add(Group.objects.get_or_create(name="aesthetic_qamar_doctor")[0])
        unrelated = User.objects.create_user(
            username="different-doctor", first_name="Andere", last_name="Ärztin",
            password="DoctorTest123!")
        UserProfile.objects.create(user=unrelated, role="specialist")

        payload = {"target": "doctor", "event": "booking_created",
                   "staff_name": "Qamar Hameed", "title": "Neuer Termin",
                   "body": "Meine Patientin"}
        with mock.patch("p0_app.notification_views._internal_sync_token", return_value="relay-secret"):
            with mock.patch("p0_app.notification_views.create_notification") as created:
                created.return_value.push_result = {"devices": []}
                response = self.client.post(
                    "/api/mobile/internal/booking-notifications/",
                    data=json.dumps(payload), content_type="application/json",
                    HTTP_X_AESTHETIC_PATIENT_SYNC="relay-secret")
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["recipients"], 1)
                self.assertEqual(created.call_args.args[0].pk, doctor.pk)
                self.assertEqual(created.call_args.kwargs["deeplink"], "doctor_calendar")
                created.reset_mock()
                payload["staff_name"] = "Andere Ärztin"
                response = self.client.post(
                    "/api/mobile/internal/booking-notifications/",
                    data=json.dumps(payload), content_type="application/json",
                    HTTP_X_AESTHETIC_PATIENT_SYNC="relay-secret")
                self.assertEqual(response.json()["recipients"], 0)
                created.assert_not_called()
                payload["staff_name"] = "Qamar Hameed"
                denied = self.client.post(
                    "/api/mobile/internal/booking-notifications/",
                    data=json.dumps(payload), content_type="application/json",
                    HTTP_X_AESTHETIC_PATIENT_SYNC="wrong")
                self.assertEqual(denied.status_code, 403)
                self.assertFalse(AppNotification.objects.filter(user=unrelated).exists())

    def test_shop_is_hard_disabled(self):
        response = self.client.get("/api/mobile/shop/", **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["enabled"])
        order = self.post_json("/api/mobile/shop/orders/", {"items": [{"id": 1, "quantity": 1}]})
        self.assertEqual(order.status_code, 409)
        self.assertEqual(order.json()["error"], "shop_disabled")
