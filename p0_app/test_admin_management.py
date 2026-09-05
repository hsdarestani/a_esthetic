import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from platform_app.mobile_api import _token_for
from platform_app.models import MemberPackage, PackageDefinition, Referral, UserProfile, WalletAccount
from p0_app.ops_models import PushDevice


class UnifiedAdminManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin-api', password='secret', is_staff=True)
        admin_profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        admin_profile.role = 'admin'
        admin_profile.save(update_fields=['role'])
        self.customer = User.objects.create_user('member-api', email='member@example.test', first_name='Mina')
        customer_profile, _ = UserProfile.objects.get_or_create(user=self.customer)
        customer_profile.role = 'customer'
        customer_profile.save(update_fields=['role'])
        self.auth = f'Bearer {_token_for(self.admin)}'

    def get(self, path):
        return self.client.get(path, HTTP_AUTHORIZATION=self.auth)

    def post(self, path, payload):
        return self.client.post(path, data=json.dumps(payload), content_type='application/json', HTTP_AUTHORIZATION=self.auth)

    def test_customer_management_excludes_admin_identity(self):
        response = self.get('/api/mobile/admin/customers/')
        self.assertEqual(response.status_code, 200)
        rows = response.json()['customers']
        self.assertEqual([row['id'] for row in rows], [self.customer.pk])

    def test_customer_wallet_and_member_status_can_be_adjusted(self):
        response = self.post(f'/api/mobile/admin/customers/{self.customer.pk}/', {
            'member_status': 'paused',
            'coin_delta': 125,
            'credit_delta_cents': 750,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()['customer']
        self.assertEqual(payload['member_status'], 'paused')
        self.assertEqual(payload['coins'], 125)
        self.assertEqual(payload['credit_cents'], 750)

    def test_packages_referrals_and_devices_are_available(self):
        definition = PackageDefinition.objects.create(name='Test Paket', sessions=3, validity_days=90)
        MemberPackage.objects.create(
            user=self.customer,
            definition=definition,
            remaining_sessions=2,
            expires_at=timezone.localdate() + timedelta(days=60),
        )
        Referral.objects.create(
            referrer=self.customer,
            code='APLUS-TEST-REF',
            invited_email='friend@example.test',
            reward_coins=300,
        )
        PushDevice.objects.create(
            user=self.customer,
            token='test-device-token',
            platform='android',
            app_version='1.0.9',
        )
        self.assertEqual(len(self.get('/api/mobile/admin/packages/').json()['packages']), 1)
        self.assertEqual(len(self.get('/api/mobile/admin/referrals/').json()['referrals']), 1)
        self.assertEqual(len(self.get('/api/mobile/admin/devices/').json()['devices']), 1)

    def test_device_can_be_disabled(self):
        device = PushDevice.objects.create(
            user=self.customer,
            token='toggle-device-token',
            platform='ios',
            app_version='1.0.9',
        )
        response = self.post('/api/mobile/admin/devices/', {'device_id': device.pk, 'enabled': False})
        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertFalse(device.enabled)