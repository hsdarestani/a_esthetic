from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .account_onboarding import (
    _attach_referral,
    _maybe_complete,
    award_referrer_first_booking,
)
from .models import Referral, UserProfile, WalletAccount


class AccountOnboardingTests(TestCase):
    def test_referral_rewards_new_user_then_referrer_on_first_booking(self):
        referrer = User.objects.create_user(
            "referrer",
            "referrer@example.com",
            "StrongPass-123!",
        )
        UserProfile.objects.create(user=referrer, role="customer")
        referral = Referral.objects.create(
            referrer=referrer,
            code="APLUS-ABCDEF1234",
            invited_email="",
            reward_coins=300,
        )
        newcomer = User.objects.create_user(
            "newcomer",
            "new@example.com",
            "StrongPass-123!",
            first_name="New",
            last_name="User",
        )
        UserProfile.objects.create(
            user=newcomer,
            role="customer",
            phone="+491701234567",
            salutation="divers",
            onboarding_required=True,
            email_verified_at=timezone.now(),
            phone_verified_at=timezone.now(),
        )
        _attach_referral(newcomer, referral.code)
        state = _maybe_complete(newcomer)
        self.assertTrue(state["profile_complete"])
        self.assertEqual(
            WalletAccount.objects.get(user=newcomer).coin_balance,
            300,
        )

        first = award_referrer_first_booking(newcomer.email, "booking-1")
        self.assertTrue(first["awarded"])
        self.assertEqual(
            WalletAccount.objects.get(user=referrer).coin_balance,
            300,
        )

        second = award_referrer_first_booking(newcomer.email, "booking-2")
        self.assertFalse(second["awarded"])
