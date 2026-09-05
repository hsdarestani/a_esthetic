import json

from django.contrib.auth.models import User
from django.test import TestCase

from .models import MemberAccount, UserProfile, WalletAccount


class AdminAwareMobileLoginTests(TestCase):
    def test_admin_login_does_not_create_customer_membership(self):
        admin = User.objects.create_user(
            username='clinic-admin',
            email='clinic-admin@example.test',
            password='test-pass-123',
            is_staff=True,
        )
        UserProfile.objects.update_or_create(user=admin, defaults={'role': 'admin'})

        response = self.client.post(
            '/api/mobile/login/',
            data=json.dumps({'username': 'clinic-admin', 'password': 'test-pass-123'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['admin'])
        self.assertEqual(payload['account_type'], 'admin')
        self.assertNotIn('member', payload)
        self.assertFalse(MemberAccount.objects.filter(user=admin).exists())
        self.assertFalse(WalletAccount.objects.filter(user=admin).exists())

    def test_customer_login_keeps_customer_club_payload(self):
        customer = User.objects.create_user(
            username='customer',
            email='customer@example.test',
            password='test-pass-123',
        )
        UserProfile.objects.update_or_create(user=customer, defaults={'role': 'customer'})

        response = self.client.post(
            '/api/mobile/login/',
            data=json.dumps({'username': 'customer', 'password': 'test-pass-123'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload['admin'])
        self.assertEqual(payload['account_type'], 'customer')
        self.assertIn('member', payload)
        self.assertTrue(MemberAccount.objects.filter(user=customer).exists())
        self.assertTrue(WalletAccount.objects.filter(user=customer).exists())
