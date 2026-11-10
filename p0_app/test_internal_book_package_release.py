"""Authenticated inter-service package credit release without app login."""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from p0_app.models import PackageBookingRedemption
from platform_app.models import MemberPackage, PackageDefinition, WalletTransaction


class InternalBookPackageReleaseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='customer-package-release')
        definition = PackageDefinition.objects.create(name='Botox 3er Paket')
        self.package = MemberPackage.objects.create(
            user=self.user, definition=definition, remaining_sessions=1,
            status='active', expires_at=timezone.localdate() + timedelta(days=90),
        )
        self.booking_id = str(uuid.uuid4())
        self.redemption = PackageBookingRedemption.objects.create(
            user=self.user, member_package=self.package,
            booking_public_id=self.booking_id, service_slug='botox',
        )
        self.path = '/api/mobile/internal/book-package-release/'

    def post(self, payload):
        return self.client.post(
            self.path, data=json.dumps(payload),
            content_type='application/json',
        )

    def test_unauthorized_caller_cannot_release_any_package_session(self):
        response = self.post({'booking_public_id': self.booking_id})
        self.assertEqual(response.status_code, 401)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.status, 'reserved')
        self.package.refresh_from_db()
        self.assertEqual(self.package.remaining_sessions, 1)

    @patch('p0_app.package_bridge_views._internal_authorized', return_value=True)
    def test_release_is_idempotent_and_audited_once(self, _auth):
        first = self.post({'booking_public_id': self.booking_id})
        second = self.post({'booking_public_id': self.booking_id})
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertTrue(first.json()['package_released'])
        self.package.refresh_from_db()
        self.assertEqual(self.package.remaining_sessions, 2)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.status, 'released')
        self.assertEqual(WalletTransaction.objects.filter(reference=f'book:{self.booking_id}:release').count(), 1)

    @patch('p0_app.package_bridge_views._internal_authorized', return_value=True)
    def test_missing_booking_is_noop_and_does_not_touch_other_customers(self, _auth):
        response = self.post({'booking_public_id': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['package_released'])
        self.package.refresh_from_db()
        self.assertEqual(self.package.remaining_sessions, 1)

    @patch('p0_app.package_bridge_views._internal_authorized', return_value=True)
    def test_disallows_arbitrary_user_or_package_mutations(self, _auth):
        response = self.post({
            'booking_public_id': self.booking_id,
            'user_id': self.user.pk,
        })
        self.assertEqual(response.status_code, 400)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.status, 'reserved')

    @patch('p0_app.package_bridge_views._internal_authorized', return_value=True)
    def test_rejects_malformed_booking_id(self, _auth):
        response = self.post({'booking_public_id': '../../other-id'})
        self.assertEqual(response.status_code, 400)
