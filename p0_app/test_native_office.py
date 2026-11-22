from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from platform_app.models import AuditLog, Invoice, OfficePatientLink, OfficeIntakeReview, UserProfile


@override_settings(STORAGES={
    'default': {'BACKEND':'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class NativeOfficeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='office-native-admin', is_staff=True, is_superuser=True)
        self.patient = User.objects.create_user(username='office-native-patient', first_name='Anna',
            last_name='Muster', email='anna@example.test')
        UserProfile.objects.create(user=self.patient, role='customer', phone='01721234567')
        self.other = User.objects.create_user(username='native-other')
        UserProfile.objects.create(user=self.other, role='customer')
        self.visit = uuid4()
        self.path = '/api/mobile/staff/office/'
        self.remote = {'ok': True, 'patient': {'id': 54, 'first_name': 'Anna', 'last_name': 'Muster',
                       'email': 'anna@example.test', 'phone': '+49 172 1234567'}}

    def admin_call(self, operation, payload, remote):
        with patch('p0_app.native_office._auth', return_value=(self.admin, None)), \
             patch('p0_app.native_office._is_admin', return_value=True), \
             patch('p0_app.native_office.read_book', return_value=remote):
            return self.client.post(self.path + operation + '/', payload, content_type='application/json')

    def test_identity_requires_confirmed_match_and_never_relinks(self):
        values = {'customer_id': self.patient.pk, 'book_customer_id': 54}
        response = self.admin_call('link', values, self.remote)
        self.assertEqual(response.status_code, 409)
        values['confirmed_same_patient'] = True
        response = self.admin_call('link', values, self.remote)
        self.assertEqual(response.status_code, 200, response.content)
        link = OfficePatientLink.objects.get()
        self.assertEqual(link.verified_by, self.admin)
        self.assertEqual(link.book_customer_id, 54)
        response = self.admin_call('link', values | {'book_customer_id': 55}, {'ok': True, 'patient': self.remote['patient'] | {'id': 55}})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(OfficePatientLink.objects.count(), 1)

    def test_completed_visit_draft_address_and_replay(self):
        OfficePatientLink.objects.create(user=self.patient, book_customer_id=54, verified_by=self.admin)
        day = timezone.localdate().isoformat()
        payload = {'customer_id': self.patient.pk, 'request_id': str(uuid4()), 'visit_id': str(self.visit),
            'address': {'street': 'Testweg 1', 'postal_code': '60313', 'city': 'Frankfurt'},
            'save_missing_address': True,
            'lines': [{'goae_number': '1', 'goae_description': 'Beratung', 'goae_base_eur': '10',
                       'goae_factor': '2.30', 'goae_vat_rate': '19'}]}
        pending = {'ok': True, 'visit': {'date': day, 'status': 'confirmed', 'customer_id': 54, 'public_id': str(self.visit)}}
        self.assertEqual(self.admin_call('draft', payload, pending).status_code, 409)
        complete = {'ok': True, 'visit': {'date': day, 'status': 'completed', 'customer_id': 54, 'public_id': str(self.visit)}}
        response = self.admin_call('draft', payload, complete)
        self.assertEqual(response.status_code, 201, response.content)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.book_appointment_public_id, self.visit)
        self.assertEqual(invoice.status, 'draft')
        self.assertEqual(invoice.total_cents, 2737)
        self.patient.profile.refresh_from_db()
        self.assertEqual(self.patient.profile.street, 'Testweg 1')
        self.assertTrue(self.admin_call('draft', payload, complete).json()['replayed'])
        self.assertEqual(self.admin_call('draft', payload | {'save_missing_address': False}, complete).status_code, 409)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_customer_only_saves_own_intake_and_cannot_open_invoices(self):
        with patch('p0_app.native_office._auth', return_value=(self.patient, None)), \
             patch('p0_app.native_office._is_admin', return_value=False):
            response = self.client.post(self.path + 'intake/', {
                'customer_id': self.other.pk, 'date_of_birth': '1990-05-19',
                'street': 'Testweg 1', 'postal_code': '60313', 'city': 'Frankfurt',
            }, content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(self.client.get(self.path + 'customers/?q=Anna').status_code, 403)
        self.patient.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(self.patient.profile.date_of_birth, date(1990, 5, 19))
        self.assertIsNone(self.other.profile.date_of_birth)
        self.assertTrue(AuditLog.objects.filter(actor=self.patient).exists())

    def test_public_intake_candidate_does_not_change_existing_account_and_can_be_reviewed(self):
        self.patient.profile.date_of_birth = date(1990, 5, 19)
        self.patient.profile.street = 'Originalweg 7'
        self.patient.profile.save()
        submission = {'first_name':'Anna', 'last_name':'Muster', 'email':'changed@example.test',
                      'phone':'+49 171 9999999', 'date_of_birth':'1990-05-19',
                      'street':'Changedweg 8', 'postal_code':'60313', 'city':'Frankfurt'}
        response = self.client.post('/office/', submission)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OfficeIntakeReview.objects.count(), 1)
        self.assertFalse(User.objects.filter(email='changed@example.test').exists())
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.email, 'anna@example.test')
        row = OfficeIntakeReview.objects.get()
        with patch('p0_app.native_office._auth', return_value=(self.admin, None)), \
             patch('p0_app.native_office._is_admin', return_value=True):
            endpoint = self.path + f'intake-review/{row.pk}/'
            self.assertEqual(self.client.post(endpoint, {'decision':'approve','customer_id':self.patient.pk},
                content_type='application/json').status_code, 409)
            accepted = self.client.post(endpoint, {'decision':'approve','customer_id':self.patient.pk,
                'confirmed_same_patient':True}, content_type='application/json')
            self.assertEqual(accepted.status_code, 200, accepted.content)
        self.patient.profile.refresh_from_db()
        self.assertEqual(self.patient.profile.street, 'Originalweg 7')
        self.assertEqual(self.patient.profile.city, 'Frankfurt')
        row.refresh_from_db()
        self.assertEqual(row.status, 'approved')
        self.assertEqual(row.reviewed_by, self.admin)

    def test_quote_uses_same_calculator_without_creating_invoice(self):
        payload = {'lines':[{'goae_number':'1','goae_description':'Beratung',
                  'goae_base_eur':'10','goae_factor':'2.30','quantity':'2','goae_vat_rate':'19'}]}
        response = self.admin_call('quote', payload, None)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['total_cents'], 5474)
        self.assertEqual(Invoice.objects.count(), 0)
