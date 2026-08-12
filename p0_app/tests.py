import json
from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from platform_app.mobile_api import _token_for
from platform_app.models import (
    Appointment,
    MemberAccount,
    MembershipTier,
    Reward,
    Service,
    StaffMember,
    UserProfile,
    WalletAccount,
    WorkingHour,
)

from .models import AccountDeletionRequest, DeviceSession


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

        day = timezone.localdate() + timedelta(days=1)
        while day.weekday() > 4:
            day += timedelta(days=1)
        self.day = day
        WorkingHour.objects.create(
            staff=self.staff,
            weekday=day.weekday(),
            start_time=time(10, 0),
            end_time=time(18, 0),
            active=True,
        )

        self.token = _token_for(self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}", "HTTP_USER_AGENT": "A+ Test iPhone"}

    def _aware(self, day, clock):
        return timezone.make_aware(datetime.combine(day, clock), timezone.get_current_timezone())

    def _slot_iso(self):
        return self._aware(self.day, time(10, 0)).isoformat()

    def _change_day(self):
        return self.day + timedelta(days=7)

    def _create_changeable_appointment(self, clock=time(11, 0)):
        start = self._aware(self._change_day(), clock)
        return Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff=self.staff,
            starts_at=start,
            ends_at=start + timedelta(minutes=40),
            status="confirmed",
            source="app",
        )

    def test_booking_accepts_real_available_slot(self):
        response = self.client.post(
            "/api/mobile/booking/",
            data=json.dumps({
                "service_id": self.service.pk,
                "staff_id": self.staff.pk,
                "starts_at": self._slot_iso(),
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 201, response.content)
        appointment = Appointment.objects.get(user=self.user)
        self.assertEqual(appointment.staff, self.staff)
        self.assertEqual(appointment.status, "confirmed")

    def test_booking_rejects_time_outside_working_hours(self):
        start = self._aware(self.day, time(8, 0))
        response = self.client.post(
            "/api/mobile/booking/",
            data=json.dumps({
                "service_id": self.service.pk,
                "staff_id": self.staff.pk,
                "starts_at": start.isoformat(),
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "time_not_available")

    def test_changeable_appointment_can_be_cancelled(self):
        appointment = self._create_changeable_appointment()
        response = self.client.post(
            f"/api/mobile/booking/{appointment.pk}/change/",
            data=json.dumps({"action": "cancel"}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")

    def test_changeable_appointment_can_be_rescheduled_to_real_slot(self):
        appointment = self._create_changeable_appointment(time(11, 0))
        new_start = self._aware(self._change_day(), time(12, 0))
        response = self.client.post(
            f"/api/mobile/booking/{appointment.pk}/change/",
            data=json.dumps({
                "action": "reschedule",
                "staff_id": self.staff.pk,
                "starts_at": new_start.isoformat(),
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        appointment.refresh_from_db()
        self.assertEqual(appointment.starts_at, new_start)
        self.assertEqual(appointment.status, "confirmed")

    def test_change_deadline_blocks_last_minute_cancellation(self):
        start = timezone.now() + timedelta(hours=12)
        appointment = Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff=self.staff,
            starts_at=start,
            ends_at=start + timedelta(minutes=40),
            status="confirmed",
            source="app",
        )
        response = self.client.post(
            f"/api/mobile/booking/{appointment.pk}/change/",
            data=json.dumps({"action": "cancel"}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "change_deadline_passed")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "confirmed")

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
