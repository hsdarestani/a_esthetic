from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from platform_app.mobile_api import _token_for
from platform_app.models import MemberPackage, PackageDefinition, UserProfile, WalletTransaction

from .models import PackageBookingRedemption


class MobileStaffWorkspaceTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user('customer',email='customer@example.test',password='AnExamplePassword-123')
        self.doctor = User.objects.create_user('doctor',first_name='Qamar',last_name='Hameed',is_staff=True)
        UserProfile.objects.update_or_create(user=self.doctor,defaults={'role':'specialist'})
        self.doctor.groups.add(Group.objects.create(name='aesthetic_qamar_doctor'))

    def auth(self, user):
        return {'HTTP_AUTHORIZATION':'Bearer '+_token_for(user)}

    def test_session_reasserts_role_and_returns_no_cache(self):
        response = self.client.get('/api/mobile/staff/session/', **self.auth(self.doctor))
        self.assertEqual(response.json()['role'],'doctor')
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.doctor.groups.clear()
        self.assertEqual(self.client.get('/api/mobile/staff/session/', **self.auth(self.doctor)).json()['role'],'customer')
        self.assertEqual(self.client.get('/api/mobile/staff/session/').status_code,401)

    def test_privileges_and_relay_methods(self):
        with patch('p0_app.mobile_staff_views.build_opener') as relay:
            self.assertEqual(self.client.get('/api/mobile/staff/book/patients/', **self.auth(self.customer)).status_code,403)
            self.assertEqual(self.client.post('/api/mobile/staff/book/service/',{}, **self.auth(self.doctor)).status_code,403)
            self.assertEqual(self.client.get('/api/mobile/staff/book/admin/overview/', **self.auth(self.doctor)).status_code,404)
            relay.assert_not_called()

    def test_patient_contact_relay_is_scoped_and_write_is_admin_only(self):
        endpoint = '/api/mobile/staff/book/patient/23/contact/'
        admin = User.objects.create_superuser('contact-admin', email='contact-admin@example.test')
        body = {'revision':'a'*64, 'phone':'+493023125000'}
        with patch('p0_app.mobile_staff_views.build_opener') as opener:
            for user, expected in [(self.customer,403), (self.doctor,403), (None,401)]:
                result = self.client.post(endpoint, body, content_type='application/json',
                                          **(self.auth(user) if user else {}))
                self.assertEqual(result.status_code, expected)
            opener.assert_not_called()
            upstream = opener.return_value.open.return_value
            upstream.code = 200
            upstream.headers.get_content_type.return_value = 'application/json'
            upstream.read.return_value = b'{"ok":true}'
            headers = self.auth(admin)
            response = self.client.post(endpoint, body, content_type='application/json', **headers)
            remote = opener.return_value.open.call_args.args[0]
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertTrue(remote.full_url.endswith('/api/mobile/staff/patient/23/contact/'))
            self.assertEqual(remote.get_method(), 'POST')
            self.assertEqual(remote.get_header('Authorization'), headers['HTTP_AUTHORIZATION'])
            self.assertEqual(self.client.get(endpoint, **self.auth(self.doctor)).status_code, 200)
            self.assertEqual(opener.return_value.open.call_args.args[0].get_method(), 'GET')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reset_uses_allauth_token_and_generic_success(self):
        for address in (self.customer.email, 'missing@example.test'):
            response = self.client.post('/api/mobile/password-recovery/', {'email':address}, content_type='application/json')
            self.assertEqual(response.json(), {'ok':True})
        self.assertIn('/accounts/password/reset/key/',mail.outbox[0].body)
        self.assertNotIn('/accounts/password/reset/key/',mail.outbox[1].body)

    @patch('p0_app.package_bridge_views._internal_authorized', return_value=True)
    def test_staff_cancellation_prevents_late_reservations_and_releases_once(self, _authorized):
        definition = PackageDefinition.objects.create(name='Laser Paket',sessions=3)
        package = MemberPackage.objects.create(user=self.customer,definition=definition,remaining_sessions=3,
                                               expires_at=timezone.localdate()+timedelta(days=10))

        def cancel(booking_id):
            return self.client.post('/api/mobile/internal/staff-cancel-package/', {'booking_public_id':booking_id},
                                    content_type='application/json').json()

        def reserve(booking_id):
            return self.client.post('/api/mobile/package-booking/', {'booking_public_id':booking_id,'service_slug':'laser'},
                                    content_type='application/json', **self.auth(self.customer)).json()

        first = str(uuid4())
        self.assertTrue(cancel(first)['ok'])
        self.assertFalse(reserve(first)['package_used'])
        self.assertFalse(PackageBookingRedemption.objects.filter(booking_public_id=first).exists())
        second = str(uuid4())
        self.assertTrue(reserve(second)['package_used'])
        self.assertTrue(cancel(second)['package_released'])
        self.assertTrue(cancel(second)['package_released'])
        package.refresh_from_db()
        self.assertEqual(package.remaining_sessions,3)


    def test_adjustment_is_admin_only_idempotent_and_audited(self):
        UserProfile.objects.update_or_create(user=self.customer,defaults={'role':'customer'})
        admin = User.objects.create_superuser('admin',email='admin@example.test',password='ExamplePwd!234')
        endpoint = '/api/mobile/staff/points/'+str(self.customer.pk)+'/'
        body = {'key':str(uuid4()),'coin_delta':50}
        self.assertEqual(self.client.post(endpoint,body,content_type='application/json',**self.auth(self.doctor)).status_code,403)
        for _ in range(2):
            response = self.client.post(endpoint,body,content_type='application/json',**self.auth(admin))
            self.assertEqual(response.json()['coins'],50)
        self.assertEqual(WalletTransaction.objects.filter(user=self.customer,kind='coin').count(),1)
        self.assertEqual(self.client.post(endpoint,{**body,'coin_delta':51},content_type='application/json',
                                          **self.auth(admin)).status_code,409)
