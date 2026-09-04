import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from platform_app.mobile_api import _token_for
from platform_app.models import (
    Appointment,
    MemberAccount,
    MemberPackage,
    MembershipTier,
    PackageDefinition,
    Reward,
    Service,
    StaffMember,
    UserProfile,
    WalletAccount,
)

from .models import AccountDeletionRequest, DeviceSession, PackageBookingRedemption, PackageBookingService


class P0MobileSafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="kunde@example.de",
            email="kunde@example.de",
            password="Test-Password-123!",
            first_name="Test",
        )
        UserProfile.objects.create(user=self.user, marketing_consent=True)
        tier = MembershipTier.objects.create(name="A+ Member", slug="member")
        MemberAccount.objects.create(user=self.user, tier=tier)
        WalletAccount.objects.create(user=self.user, coin_balance=2000, balance_cents=5000)

        self.service = Service.objects.create(
            name="A+ Beratung",
            slug="a-plus-beratung",
            category="consultation",
            duration_minutes=30,
            buffer_minutes=10,
            active=True,
            bookable_in_app=True,
        )
        self.staff = StaffMember.objects.create(display_name="A+ Team", role="reception", active=True)
        self.staff.services.add(self.service)

        self.token = _token_for(self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}", "HTTP_USER_AGENT": "A+ Test iPhone"}

    def test_package_booking_reserve_is_idempotent_and_release_restores_session(self):
        definition = PackageDefinition.objects.create(
            name="A+ Beratung Paket",
            sessions=2,
            validity_days=365,
            active=True,
        )
        package = MemberPackage.objects.create(
            user=self.user,
            definition=definition,
            remaining_sessions=2,
            expires_at=timezone.localdate() + timedelta(days=90),
            status="active",
        )
        booking_id = "82f4b778-d1b9-49cf-c1bb-f45042bf9d51"
        payload = {
            "action": "reserve",
            "booking_public_id": booking_id,
            "service_slug": "a-plus-beratung",
            "service_name": "A+ Beratung",
        }

        first = self.client.post(
            "/api/mobile/package-booking/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertTrue(first.json()["package_used"])
        package.refresh_from_db()
        self.assertEqual(package.remaining_sessions, 1)
        self.assertTrue(PackageBookingService.objects.filter(package_definition=definition, service_slug="a-plus-beratung").exists())

        second = self.client.post(
            "/api/mobile/package-booking/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(second.status_code, 200, second.content)
        package.refresh_from_db()
        self.assertEqual(package.remaining_sessions, 1)
        self.assertEqual(PackageBookingRedemption.objects.filter(booking_public_id=booking_id).count(), 1)

        release = self.client.post(
            "/api/mobile/package-booking/",
            data=json.dumps({"action": "release", "booking_public_id": booking_id}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(release.status_code, 200, release.content)
        self.assertTrue(release.json()["package_released"])
        package.refresh_from_db()
        self.assertEqual(package.remaining_sessions, 2)
        self.assertEqual(PackageBookingRedemption.objects.get(booking_public_id=booking_id).status, "released")

    def test_package_booking_does_not_consume_unrelated_package(self):
        definition = PackageDefinition.objects.create(name="Laser Paket", sessions=3, active=True)
        package = MemberPackage.objects.create(
            user=self.user,
            definition=definition,
            remaining_sessions=3,
            expires_at=timezone.localdate() + timedelta(days=90),
            status="active",
        )
        response = self.client.post(
            "/api/mobile/package-booking/",
            data=json.dumps({
                "action": "reserve",
                "booking_public_id": "unrelated-booking",
                "service_slug": "botox",
                "service_name": "Botox",
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["package_used"])
        package.refresh_from_db()
        self.assertEqual(package.remaining_sessions, 3)

    def test_account_deletion_creates_trackable_request(self):
        response = self.client.post(
            "/api/mobile/account-deletion/",
            data=json.dumps({"reason": "Bitte löschen"}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        item = AccountDeletionRequest.objects.get(user=self.user)
        self.assertEqual(item.status, "identity_check")
        self.assertFalse(UserProfile.objects.get(user=self.user).marketing_consent)

    def test_revoked_device_token_is_blocked_on_next_request(self):
        first = self.client.get("/api/mobile/me/", **self.auth)
        self.assertEqual(first.status_code, 200)
        device = DeviceSession.objects.get(user=self.user)

        revoke = self.client.post(
            f"/api/mobile/devices/{device.pk}/revoke/",
            data="{}",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(revoke.status_code, 200)

        blocked = self.client.get("/api/mobile/me/", **self.auth)
        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(blocked.json()["error"], "session_revoked")

    def test_medical_reward_never_appears_or_redeems(self):
        safe = Reward.objects.create(name="Sample", coin_cost=100, active=True, is_medical_service=False)
        unsafe = Reward.objects.create(name="Medical", coin_cost=100, active=True, is_medical_service=True)

        wallet = self.client.get("/api/mobile/wallet/", **self.auth)
        self.assertEqual(wallet.status_code, 200)
        ids = {item["id"] for item in wallet.json()["rewards"]}
        self.assertIn(safe.pk, ids)
        self.assertNotIn(unsafe.pk, ids)

        redeem = self.client.post(
            f"/api/mobile/wallet/reward/{unsafe.pk}/",
            data="{}",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(redeem.status_code, 404)

    def test_export_is_scoped_to_authenticated_user(self):
        other = User.objects.create_user("other@example.de", password="Other-Password-123!")
        Appointment.objects.create(
            user=other,
            service=self.service,
            staff=self.staff,
            starts_at=timezone.now() + timedelta(days=7),
            ends_at=timezone.now() + timedelta(days=7, minutes=40),
            status="confirmed",
            source="admin",
        )

        response = self.client.get("/api/mobile/export/", **self.auth)
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["account"]["email"], self.user.email)
        self.assertEqual(payload["appointments"], [])
