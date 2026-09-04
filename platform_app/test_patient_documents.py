import json
import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from platform_app.mobile_api import _token_for
from platform_app.models import UserProfile


class CustomerPatientDocumentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="patient@example.de",
            email="patient@example.de",
            password="Password-123!",
            first_name="Paula",
            last_name="Patient",
        )
        self.profile = UserProfile.objects.create(user=self.user, phone="+49123456789")
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_token_for(self.user)}"}

    def test_patient_record_list_is_scoped_to_authenticated_identity(self):
        book_payload = {
            "ok": True,
            "patient_found": True,
            "customer": {"id": 10, "name": "Paula Patient", "email": self.user.email},
            "records": [{"id": str(uuid.uuid4()), "title": "Geteilt", "customer_uploaded": False}],
        }
        with mock.patch("platform_app.patient_documents._book_json", return_value=(book_payload, None, 200)) as gateway:
            response = self.client.get("/api/mobile/patient-records/", **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["records"][0]["title"], "Geteilt")
        sent_identity = gateway.call_args.args[1]
        self.assertEqual(sent_identity["email"], self.user.email)
        self.assertEqual(sent_identity["phone"], "+49123456789")

    def test_upload_requires_explicit_health_data_consent_first_time(self):
        response = self.client.post(
            "/api/mobile/patient-records/upload/",
            data={"kind": "note", "title": "Notiz", "note": "Test"},
            **self.auth,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "health_data_consent_required")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.health_data_consent)

    def test_customer_upload_is_sent_to_book_as_shared_patient_record(self):
        upload = SimpleUploadedFile("befund.pdf", b"%PDF test", content_type="application/pdf")
        result = {"ok": True, "created": True, "record_id": str(uuid.uuid4()), "customer_id": 1}
        with mock.patch("platform_app.patient_documents._book_json", return_value=(result, None, 201)) as gateway, mock.patch("platform_app.patient_documents.create_notification"):
            response = self.client.post(
                "/api/mobile/patient-records/upload/",
                data={
                    "kind": "document",
                    "title": "Mein Befund",
                    "health_data_consent": "1",
                    "file": upload,
                },
                **self.auth,
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.health_data_consent)
        payload = gateway.call_args.args[1]
        self.assertEqual(payload["source"], "a_esthetic_app_customer")
        self.assertTrue(payload["metadata"]["shared_with_customer"])
        self.assertTrue(payload["metadata"]["customer_upload"])
        self.assertEqual(payload["original_name"], "befund.pdf")
        self.assertTrue(payload["file_base64"])

    def test_customer_can_archive_through_identity_scoped_gateway(self):
        self.profile.health_data_consent = True
        self.profile.save(update_fields=["health_data_consent"])
        record_id = uuid.uuid4()
        with mock.patch(
            "platform_app.patient_documents._book_json",
            return_value=({"ok": True, "archived": True, "record_id": str(record_id)}, None, 200),
        ) as gateway:
            response = self.client.post(
                f"/api/mobile/patient-records/{record_id}/archive/",
                data="{}",
                content_type="application/json",
                **self.auth,
            )
        self.assertEqual(response.status_code, 200, response.content)
        payload = gateway.call_args.args[1]
        self.assertEqual(payload["email"], self.user.email)
        self.assertEqual(payload["record_id"], str(record_id))

    def test_book_callback_creates_notification_only_after_source_auth(self):
        payload = json.dumps({
            "email": self.user.email,
            "record_id": str(uuid.uuid4()),
            "title": "Behandlungsinformation",
            "shared": True,
        })
        denied = self.client.post(
            "/api/internal/patient-document/shared/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 401)

        fake_notification = mock.Mock(pk=99, push_result={"devices": []})
        with mock.patch("platform_app.patient_documents._book_callback_authorized", return_value=True), mock.patch(
            "platform_app.patient_documents.create_notification", return_value=fake_notification
        ) as notify:
            allowed = self.client.post(
                "/api/internal/patient-document/shared/",
                data=payload,
                content_type="application/json",
            )
        self.assertEqual(allowed.status_code, 200, allowed.content)
        self.assertTrue(allowed.json()["recipient_found"])
        self.assertEqual(notify.call_args.kwargs["deeplink"], "profile")
