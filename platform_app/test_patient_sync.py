import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import ConsentRecord, ConsentTemplate, UserProfile
from .patient_sync import sync_consent_record


class PatientRecordSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='anna',
            email='anna@example.com',
            first_name='Anna',
            last_name='Muster',
            password='long-test-password',
        )
        UserProfile.objects.create(user=self.user, phone='+49 151 2345678')
        self.template = ConsentTemplate.objects.create(
            key='botox-consent',
            title='Botox Aufklärung und Einwilligung',
            text='Testfassung der Einwilligung.',
            version='2.0',
            health_data=True,
            active=True,
        )
        self.record = ConsentRecord.objects.create(
            user=self.user,
            template=self.template,
            accepted=True,
            evidence={'source': 'test'},
        )

    @patch('platform_app.patient_sync._token', return_value='sync-secret')
    @patch('platform_app.patient_sync.urlopen')
    def test_acceptance_is_sent_as_form_snapshot(self, urlopen_mock, token_mock):
        response = MagicMock()
        response.status = 201
        response.read.return_value = b'{"ok":true,"created":true}'
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        urlopen_mock.return_value = response

        self.assertTrue(sync_consent_record(self.record))
        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(payload['source'], 'a_esthetic_app')
        self.assertEqual(payload['external_id'], f'consent:{self.record.pk}:acceptance')
        self.assertEqual(payload['kind'], 'form')
        self.assertEqual(payload['email'], 'anna@example.com')
        self.assertEqual(payload['phone'], '+49 151 2345678')
        self.assertEqual(payload['metadata']['template_version'], '2.0')
        self.assertIn('Testfassung der Einwilligung.', payload['note'])

    @patch('platform_app.patient_sync._token', return_value='sync-secret')
    @patch('platform_app.patient_sync.urlopen')
    def test_withdrawal_creates_second_audit_event(self, urlopen_mock, token_mock):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"ok":true,"created":false}'
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        urlopen_mock.return_value = response
        self.record.withdrawn_at = timezone.now()
        self.record.save(update_fields=['withdrawn_at'])

        self.assertTrue(sync_consent_record(self.record))
        self.assertEqual(urlopen_mock.call_count, 2)
        second_request = urlopen_mock.call_args_list[-1].args[0]
        payload = json.loads(second_request.data.decode('utf-8'))
        self.assertEqual(payload['external_id'], f'consent:{self.record.pk}:withdrawal')
        self.assertEqual(payload['metadata']['document_type'], 'consent_withdrawal')
