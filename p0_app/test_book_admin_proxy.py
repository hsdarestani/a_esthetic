import json
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from platform_app.models import UserProfile


class _FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._body = json.dumps(payload).encode('utf-8')
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self._body


class BookAdminProxyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin-book-test', password='x', email='admin@example.com', is_staff=True)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = 'admin'
        profile.save(update_fields=['role'])
        self.headers = {'HTTP_AUTHORIZATION': 'Bearer proxy-test-token-abcdefghijklmnopqrstuvwxyz'}

    @patch('p0_app.book_admin_proxy_views._admin_auth')
    @patch('p0_app.book_admin_proxy_views.urlopen')
    def test_overview_is_proxied_with_admin_bearer(self, mocked_urlopen, mocked_auth):
        mocked_auth.return_value = (self.user, None)
        mocked_urlopen.return_value = _FakeResponse({'ok': True, 'stats': {'today': 2}})
        response = self.client.get('/api/mobile/admin/book/overview/', **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.headers.get('Authorization'), self.headers['HTTP_AUTHORIZATION'])
        self.assertIn('/api/mobile/app-admin/overview/', request.full_url)

    @patch('p0_app.book_admin_proxy_views._admin_auth')
    @patch('p0_app.book_admin_proxy_views.urlopen')
    def test_appointment_write_is_forwarded(self, mocked_urlopen, mocked_auth):
        mocked_auth.return_value = (self.user, None)
        mocked_urlopen.return_value = _FakeResponse({'ok': True, 'appointment': {'id': 9, 'status': 'confirmed'}})
        response = self.client.post(
            '/api/mobile/admin/book/appointments/9/',
            data='{"status":"confirmed"}',
            content_type='application/json',
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.method, 'POST')
        self.assertEqual(request.data, b'{"status":"confirmed"}')
