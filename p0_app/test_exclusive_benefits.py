from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from platform_app.mobile_api import _token_for
from platform_app.models import Campaign, MemberAccount, MembershipTier, UserProfile


class ExclusiveBenefitsVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="exclusive-test@example.de",
            email="exclusive-test@example.de",
            password="test-only",
        )
        UserProfile.objects.create(user=self.user)
        self.basic = MembershipTier.objects.create(name="A+ Member", slug="member")
        self.vip = MembershipTier.objects.create(name="Signature", slug="signature")
        self.membership = MemberAccount.objects.create(
            user=self.user, tier=self.basic, status="active",
            valid_until=timezone.localdate() + timedelta(days=30),
        )
        now = timezone.now()
        self.vip_campaign = Campaign.objects.create(
            name="Signature Preview", audience="vip",
            message="Nur fuer berechtigte Mitglieder",
            starts_at=now-timedelta(days=1), ends_at=now+timedelta(days=7), active=True,
        )
        Campaign.objects.create(
            name="Public Campaign", audience="all", message="Alle Mitglieder",
            starts_at=now-timedelta(days=1), ends_at=now+timedelta(days=7), active=True,
        )
        self.auth = {"HTTP_AUTHORIZATION": "Bearer " + _token_for(self.user)}

    def read_benefits(self):
        response = self.client.get("/api/mobile/club/", **self.auth)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_regular_member_sees_no_exclusive_offers(self):
        data = self.read_benefits()
        self.assertIs(data["exclusive_access"]["eligible"], False)
        self.assertEqual(data["exclusive_benefits"], [])

    def test_active_signature_member_sees_only_vip_campaign(self):
        self.membership.tier = self.vip
        self.membership.save(update_fields=["tier"])
        data = self.read_benefits()
        self.assertIs(data["exclusive_access"]["eligible"], True)
        self.assertEqual([c["id"] for c in data["exclusive_benefits"]], [self.vip_campaign.pk])

    def test_expired_membership_does_not_unlock_vip_offer(self):
        self.membership.tier = self.vip
        self.membership.valid_until = timezone.localdate() - timedelta(days=1)
        self.membership.save(update_fields=["tier", "valid_until"])
        data = self.read_benefits()
        self.assertIs(data["exclusive_access"]["eligible"], False)
        self.assertEqual(data["exclusive_benefits"], [])

    def test_paused_membership_does_not_unlock_vip_offer(self):
        self.membership.tier = self.vip
        self.membership.status = "paused"
        self.membership.save(update_fields=["tier", "status"])
        data = self.read_benefits()
        self.assertIs(data["exclusive_access"]["eligible"], False)
        self.assertEqual(data["exclusive_benefits"], [])

    def test_inactive_or_expired_campaign_does_not_appear(self):
        self.membership.tier = self.vip
        self.membership.save(update_fields=["tier"])
        self.vip_campaign.active = False
        self.vip_campaign.save(update_fields=["active"])
        data = self.read_benefits()
        self.assertIs(data["exclusive_access"]["eligible"], True)
        self.assertEqual(data["exclusive_benefits"], [])
