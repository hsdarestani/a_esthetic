import json
from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from .notification_views import internal_booking_notification
from platform_app.models import UserProfile


class BotoxbogenAdminPushTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin-form-push", is_active=True)
        UserProfile.objects.create(user=self.admin, role="admin")
        self.factory = RequestFactory()

    @patch("p0_app.notification_views.create_notification")
    @patch("p0_app.notification_views._internal_authorized", return_value=True)
    @patch("p0_app.notification_views._internal_sync_token", return_value="configured")
    def test_form_notification_routes_only_admin_to_exact_patient(self, _token, _auth, create):
        create.return_value = SimpleNamespace(push_result={"devices":[{"ok":True}]})
        request = self.factory.post("/api/mobile/internal/booking-notifications/",
            data=json.dumps({
                "target":"admin", "event":"botoxbogen_submitted",
                "title":"Neuer Patientenbogen eingegangen",
                "body":"Patientenakte öffnen.",
                "patient_customer_id":"42",
                "patient_record_id":"5b49f29d-1111-4444-8888-000000000001",
            }), content_type="application/json")
        response = internal_booking_notification(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(json.loads(response.content)["notifications"], 1)
        self.assertTrue(any(call.args[0].pk == self.admin.pk for call in create.call_args_list))
        for call in create.call_args_list:
            self.assertEqual(call.kwargs["deeplink"], "admin_patient")
            self.assertEqual(call.kwargs["data"]["patient_customer_id"], "42")
            self.assertNotIn("medical", json.dumps(call.kwargs["data"]).lower())

    @patch("p0_app.notification_views._internal_authorized", return_value=True)
    @patch("p0_app.notification_views._internal_sync_token", return_value="configured")
    def test_form_push_must_be_targeted_to_admin(self, _token, _auth):
        request = self.factory.post("/api/mobile/internal/booking-notifications/",
            data=json.dumps({
                "target":"customer", "event":"botoxbogen_submitted",
                "title":"Neuer Bogen","body":"Geöffnet",
                "patient_customer_id":"42","patient_record_id":"record",
            }), content_type="application/json")
        response = internal_booking_notification(request)
        self.assertEqual(response.status_code, 400)
