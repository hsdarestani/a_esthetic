import json
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from platform_app.mobile_api import _token_for
from platform_app.models import (
    MemberAccount,
    MembershipTier,
    Service,
    StaffMember,
    UserProfile,
    WalletAccount,
)
from p0_app.ops_models import AppNotification


class FullCustomerAppRegressionTests(TestCase):
    """Functional smoke coverage for the customer-facing mobile API and packaged shell."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='client-regression@example.de',
            email='client-regression@example.de',
            password='Client-Regression-123!',
            first_name='Client',
            last_name='Regression',
        )
        UserProfile.objects.create(user=self.user, marketing_consent=True, phone='+491701234567')
        tier = MembershipTier.objects.create(name='A+ Member', slug='client-regression-member')
        MemberAccount.objects.create(user=self.user, tier=tier)
        WalletAccount.objects.create(user=self.user, coin_balance=1200, balance_cents=5500)
        service = Service.objects.create(
            name='Regression Beratung',
            slug='client-regression-beratung',
            category='consultation',
            duration_minutes=30,
            buffer_minutes=10,
            active=True,
            bookable_in_app=True,
        )
        staff = StaffMember.objects.create(display_name='Regression Team', role='reception', active=True)
        staff.services.add(service)
        self.token = _token_for(self.user)
        self.auth = {
            'HTTP_AUTHORIZATION': f'Bearer {self.token}',
            'HTTP_USER_AGENT': 'A+ Functional Regression Android',
        }

    def test_core_customer_read_surfaces_return_valid_payloads(self):
        expectations = (
            ('/api/mobile/me/', None),
            ('/api/mobile/dashboard/', 'book'),
            ('/api/mobile/wallet/', None),
            ('/api/mobile/club/', None),
            ('/api/mobile/reviews/', None),
            ('/api/mobile/notifications/', None),
            ('/api/mobile/export/', None),
        )
        for path, appointments_source in expectations:
            with self.subTest(path=path):
                response = self.client.get(path, **self.auth)
                self.assertEqual(response.status_code, 200, response.content[:500])
                payload = response.json()
                self.assertTrue(payload.get('ok'), payload)
                if appointments_source:
                    self.assertEqual(payload.get('appointments_source'), appointments_source)

    def test_review_open_and_submit_flow_is_functional(self):
        opened = self.client.post(
            '/api/mobile/reviews/',
            data=json.dumps({'action': 'opened'}),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(opened.status_code, 200, opened.content)
        self.assertEqual(opened.json()['activities'][0]['status'], 'opened')

        submitted = self.client.post(
            '/api/mobile/reviews/',
            data=json.dumps({'action': 'submitted', 'rating': 5, 'review_text': 'Regression review'}),
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(submitted.status_code, 200, submitted.content)
        activity = submitted.json()['activities'][0]
        self.assertEqual(activity['status'], 'submitted')
        self.assertEqual(activity['rating'], 5)

    def test_notification_read_flow_is_scoped_and_functional(self):
        notification = AppNotification.objects.create(
            user=self.user,
            title='Regression',
            body='Functional notification',
            category='system',
        )
        listing = self.client.get('/api/mobile/notifications/', **self.auth)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['unread_count'], 1)

        read = self.client.post(
            f'/api/mobile/notifications/{notification.pk}/read/',
            data='{}',
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(read.status_code, 200)
        self.assertTrue(read.json()['notification']['read'])

        read_all = self.client.post(
            '/api/mobile/notifications/read-all/',
            data='{}',
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(read_all.status_code, 200)
        self.assertEqual(read_all.json()['unread_count'], 0)

    @patch('platform_app.patient_documents._book_json')
    def test_patient_record_surface_bridges_to_book_without_ui_contract_breakage(self, book_json):
        book_json.return_value = ({
            'ok': True,
            'records': [{
                'id': '0d214dd3-6ebf-42b4-8ff4-c3e07966ae31',
                'kind': 'document',
                'title': 'Regression Dokument',
                'note': '',
                'source': 'book_staff',
                'captured_at': '2026-09-07T12:00:00+00:00',
            }],
        }, None, 200)
        response = self.client.get('/api/mobile/patient-records/', **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertEqual(payload['records'][0]['title'], 'Regression Dokument')
        self.assertTrue(book_json.called)

    def test_old_local_booking_write_endpoint_stays_retired(self):
        response = self.client.post(
            '/api/mobile/booking/',
            data='{}',
            content_type='application/json',
            **self.auth,
        )
        self.assertEqual(response.status_code, 410)
        payload = response.json()
        self.assertEqual(payload['error'], 'booking_moved_to_canonical_service')
        self.assertEqual(payload['canonical_api'], 'https://book.a-esthetic.de/api/mobile/booking/')

    def test_packaged_customer_shell_keeps_only_the_supported_runtime_stack(self):
        root = Path(settings.BASE_DIR) / 'www'
        index = (root / 'index.html').read_text(encoding='utf-8')
        required = (
            'booking-direct-api.js',
            'admin-mode.js',
            'core-app.js',
            'booking-consent-bridge.js',
            'booking-book-flow.js',
            'focused-upgrade.js',
            'native-push.js',
            'native-interactions.js',
            'mobile-polish.js',
            'customer-luxury.js',
            'mobile-polish.css',
            'customer-luxury.css',
        )
        for asset in required:
            with self.subTest(asset=asset):
                self.assertIn(asset, index)
                self.assertTrue((root / asset).is_file(), asset)

        # Old parallel app runtimes may remain in the repository for migration
        # compatibility, but they must not be executable script tags in production.
        for legacy in ('p0.js', 'p1.js', 'p2.js', 'p3.js', 'ops.js', 'reference-ui.js'):
            self.assertNotIn(f'<script src="./{legacy}', index)
