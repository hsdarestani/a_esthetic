from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from platform_app.models import (
    Appointment,
    FeatureModule,
    MemberAccount,
    MembershipTier,
    Reward,
    Service,
    StaffMember,
    WalletAccount,
    WorkingHour,
)

from .models import CoinRule, ProgressAlbum, RewardRedemption
from .services import available_slots, redeem_reward, safe_assistant_answer


@override_settings(PRIVATE_FILE_ENCRYPTION_KEYS="kYUv5GqvPiIu5W5jS7yP4-6pE7_QfrwcDlqlopgCVcY=")
class CompleteFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("kunde@example.de", "kunde@example.de", "Test-Password-123!")
        self.staff_user = User.objects.create_user("staff", "staff@example.de", "Test-Password-123!", is_staff=True)
        tier = MembershipTier.objects.create(name="A+ Member", slug="member", priority=10)
        MemberAccount.objects.create(user=self.user, tier=tier)
        WalletAccount.objects.create(user=self.user, balance_cents=10000, coin_balance=2000)
        self.service = Service.objects.create(name="Beratung", slug="beratung", category="consultation", duration_minutes=30, buffer_minutes=10, active=True, bookable_in_app=True)
        self.staff = StaffMember.objects.create(user=self.staff_user, display_name="A+ Team", role="specialist", active=True)
        self.staff.services.add(self.service)
        WorkingHour.objects.create(staff=self.staff, weekday=(timezone.localdate() + timedelta(days=1)).weekday(), start_time=time(9, 0), end_time=time(12, 0), active=True)
        for key in ["membership", "wallet", "giftcards", "booking", "checkin", "before_after", "followup", "beauty_plan", "ai", "cabinet", "shop", "gamification", "communication", "offers", "events", "content", "feedback", "concierge", "privacy"]:
            FeatureModule.objects.create(key=key, name_de=key, enabled=True, customer_visible=True)

    def test_slots_respect_conflicts(self):
        day = timezone.localdate() + timedelta(days=1)
        slots = available_slots(self.service, self.staff, day)
        self.assertTrue(slots)
        first = slots[0]
        Appointment.objects.create(user=self.user, service=self.service, staff=self.staff, starts_at=first, ends_at=first + timedelta(minutes=40), status="confirmed", source="app")
        updated = available_slots(self.service, self.staff, day)
        self.assertNotIn(first, updated)

    def test_medical_reward_is_rejected(self):
        reward = Reward(name="Medizinische Leistung", coin_cost=100, is_medical_service=True)
        with self.assertRaises(ValidationError):
            reward.full_clean()

    def test_reward_redemption_is_atomic_and_a_plus_issued(self):
        reward = Reward.objects.create(name="A+ Sample", coin_cost=500, active=True, inventory=2, is_medical_service=False)
        redemption = redeem_reward(self.user, reward)
        wallet = WalletAccount.objects.get(user=self.user)
        self.assertEqual(wallet.coin_balance, 1500)
        self.assertEqual(redemption.issuer, "A+ Esthetic")
        self.assertTrue(RewardRedemption.objects.filter(user=self.user, reward=reward).exists())

    def test_ai_blocks_diagnosis_and_dosage(self):
        answer, conversation = safe_assistant_answer(self.user, "Welche Botox Dosis brauche ich?")
        self.assertTrue(conversation.blocked_medical_request)
        self.assertIn("keine Diagnose", answer)

    def test_disabled_module_returns_404(self):
        self.client.login(username="kunde@example.de", password="Test-Password-123!")
        module = FeatureModule.objects.get(key="cabinet")
        module.enabled = False
        module.save()
        response = self.client.get(reverse("experience:cabinet"))
        self.assertEqual(response.status_code, 404)

    def test_checkin_requires_staff(self):
        member = MemberAccount.objects.get(user=self.user)
        response = self.client.get(reverse("experience:checkin_token", args=[member.qr_token]))
        self.assertEqual(response.status_code, 302)
        self.client.login(username="staff", password="Test-Password-123!")
        response = self.client.get(reverse("experience:checkin_token", args=[member.qr_token]))
        self.assertEqual(response.status_code, 200)

    def test_private_photo_page_requires_owner(self):
        album = ProgressAlbum.objects.create(user=self.user, title="OWNER-ONLY-ALBUM-7F3A9C", private=True)
        other = User.objects.create_user("other", password="Test-Password-123!")
        self.client.login(username="other", password="Test-Password-123!")
        response = self.client.get(reverse("experience:photo_center"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, album.title)

    def test_api_returns_only_current_user_data(self):
        other = User.objects.create_user("other2", password="Test-Password-123!")
        Appointment.objects.create(user=other, service=self.service, staff=self.staff, starts_at=timezone.now() + timedelta(days=2), ends_at=timezone.now() + timedelta(days=2, minutes=40), status="confirmed", source="admin")
        self.client.login(username="kunde@example.de", password="Test-Password-123!")
        response = self.client.get(reverse("experience:api_dashboard"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["next_appointment"])
