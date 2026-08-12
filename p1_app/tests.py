import json
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from platform_app.mobile_api import _token_for
from platform_app.models import (
    Appointment,
    ConsentRecord,
    FollowUp,
    Service,
    StaffMember,
    UserProfile,
)

from .models import (
    AftercareTask,
    AftercareTaskStatus,
    AftercareTemplate,
    BeautyPlan,
    BeautyPlanStep,
    ProgressAlbum,
    ProgressPhoto,
)


class P1ExperienceTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="aesthetic-p1-test-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        self.user = User.objects.create_user(
            username="p1@example.de",
            email="p1@example.de",
            password="Test-Password-123!",
            first_name="Pia",
        )
        self.other = User.objects.create_user(
            username="other-p1@example.de",
            email="other-p1@example.de",
            password="Other-Password-123!",
        )
        UserProfile.objects.create(user=self.user, health_data_consent=False)
        UserProfile.objects.create(user=self.other, health_data_consent=False)

        self.token = _token_for(self.user)
        self.other_token = _token_for(self.other)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.other_auth = {"HTTP_AUTHORIZATION": f"Bearer {self.other_token}"}

        self.service = Service.objects.create(
            name="P1 Beauty Termin",
            slug="p1-beauty-termin",
            category="nonmedical",
            duration_minutes=30,
            buffer_minutes=10,
            active=True,
            bookable_in_app=True,
        )
        self.staff = StaffMember.objects.create(
            display_name="A+ P1 Team",
            role="reception",
            active=True,
        )
        self.staff.services.add(self.service)
        self.appointment = Appointment.objects.create(
            user=self.user,
            service=self.service,
            staff=self.staff,
            starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(days=2) + timedelta(minutes=40),
            status="completed",
            source="app",
        )

    def _consent(self):
        return self.client.post(
            "/api/mobile/progress/consent/",
            data=json.dumps({"accepted": True}),
            content_type="application/json",
            **self.auth,
        )

    def _album(self):
        response = self.client.post(
            "/api/mobile/progress/",
            data=json.dumps({"title": "Mein Verlauf", "description": "Privat"}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 201, response.content)
        return ProgressAlbum.objects.get(pk=response.json()["album_id"])

    def test_p1_requires_mobile_authentication(self):
        response = self.client.get("/api/mobile/progress/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "authentication_required")

    def test_progress_upload_requires_explicit_health_data_consent(self):
        album = self._album()
        upload = SimpleUploadedFile("before.jpg", b"fake-jpeg", content_type="image/jpeg")
        response = self.client.post(
            f"/api/mobile/progress/{album.pk}/upload/",
            {"kind": "before", "photo": upload},
            **self.auth,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "health_data_consent_required")
        self.assertFalse(ProgressPhoto.objects.exists())

    def test_progress_consent_is_versioned_and_withdrawable(self):
        accepted = self._consent()
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["health_data_consent"])
        consent = ConsentRecord.objects.get(user=self.user, template__key="progress-photos")
        self.assertTrue(consent.accepted)
        self.assertIsNone(consent.withdrawn_at)
        self.assertEqual(consent.evidence["source"], "mobile_app")

        withdrawn = self.client.post(
            "/api/mobile/progress/consent/",
            data=json.dumps({"accepted": False}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(withdrawn.status_code, 200)
        self.assertFalse(withdrawn.json()["health_data_consent"])
        consent.refresh_from_db()
        self.assertIsNotNone(consent.withdrawn_at)

    def test_progress_photo_is_owner_scoped_and_deletable(self):
        self._consent()
        album = self._album()
        upload = SimpleUploadedFile("progress.jpg", b"private-photo-bytes", content_type="image/jpeg")
        created = self.client.post(
            f"/api/mobile/progress/{album.pk}/upload/",
            {"kind": "progress", "photo": upload},
            **self.auth,
        )
        self.assertEqual(created.status_code, 201, created.content)
        photo = ProgressPhoto.objects.get(pk=created.json()["photo_id"])
        self.assertEqual(len(photo.sha256), 64)

        owner_get = self.client.get(f"/api/mobile/progress/photo/{photo.pk}/", **self.auth)
        self.assertEqual(owner_get.status_code, 200)
        self.assertEqual(owner_get["Cache-Control"], "private, no-store, max-age=0")

        other_get = self.client.get(f"/api/mobile/progress/photo/{photo.pk}/", **self.other_auth)
        self.assertEqual(other_get.status_code, 404)

        deleted = self.client.delete(f"/api/mobile/progress/photo/{photo.pk}/", **self.auth)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(ProgressPhoto.objects.filter(pk=photo.pk).exists())

    def test_aftercare_only_uses_staff_defined_template_for_completed_appointment(self):
        template = AftercareTemplate.objects.create(
            service=self.service,
            title="Freigegebene Nachsorge",
            approved_by="A+ Team",
            version="1.0",
            active=True,
        )
        task = AftercareTask.objects.create(
            template=template,
            title="A+ Hinweise lesen",
            description="Nur freigegebene Hinweise.",
            task_type="do",
            sort_order=10,
        )

        response = self.client.get("/api/mobile/aftercare/", **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["assigned"]), 1)
        status = AftercareTaskStatus.objects.get(assigned__user=self.user, task=task)

        toggled = self.client.post(
            f"/api/mobile/aftercare/task/{status.pk}/toggle/",
            data="{}",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(toggled.status_code, 200)
        self.assertTrue(toggled.json()["completed"])
        self.assertTrue(toggled.json()["assigned_complete"])

    def test_followup_contact_request_escalates_to_staff_review(self):
        followup = FollowUp.objects.create(
            user=self.user,
            appointment=self.appointment,
            title="Wie geht es Ihnen?",
            questions=["Alles in Ordnung?"],
            due_at=timezone.now(),
            status="pending",
        )
        response = self.client.post(
            f"/api/mobile/aftercare/followup/{followup.pk}/response/",
            data=json.dumps({"response": "Bitte melden.", "request_contact": True}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        followup.refresh_from_db()
        self.assertEqual(followup.status, "review")
        self.assertTrue(followup.requires_review)

        forbidden = self.client.post(
            f"/api/mobile/aftercare/followup/{followup.pk}/response/",
            data=json.dumps({"response": "Andere Person"}),
            content_type="application/json",
            **self.other_auth,
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_beauty_plan_create_step_toggle_and_ownership(self):
        created = self.client.post(
            "/api/mobile/beauty-plans/",
            data=json.dumps({
                "title": "Summer Plan",
                "journey_type": "summer",
                "goal": "Eigene Routine organisieren",
                "monthly_budget_cents": 12000,
            }),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(created.status_code, 201, created.content)
        plan = BeautyPlan.objects.get(pk=created.json()["plan"]["id"])
        self.assertFalse(plan.medical_decision_support)

        step_response = self.client.post(
            f"/api/mobile/beauty-plans/{plan.pk}/steps/",
            data=json.dumps({"title": "Pflege prüfen", "step_type": "care", "estimated_cost_cents": 2500}),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(step_response.status_code, 201, step_response.content)
        step = BeautyPlanStep.objects.get(pk=step_response.json()["step_id"])

        forbidden = self.client.post(
            f"/api/mobile/beauty-plans/steps/{step.pk}/toggle/",
            data="{}",
            content_type="application/json",
            **self.other_auth,
        )
        self.assertEqual(forbidden.status_code, 404)

        toggled = self.client.post(
            f"/api/mobile/beauty-plans/steps/{step.pk}/toggle/",
            data="{}",
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(toggled.status_code, 200)
        self.assertTrue(toggled.json()["completed"])
        self.assertEqual(toggled.json()["plan_status"], "completed")

    def test_full_export_includes_only_current_users_p1_data(self):
        BeautyPlan.objects.create(user=self.user, title="Mein Plan", journey_type="custom", status="active")
        BeautyPlan.objects.create(user=self.other, title="Fremder Plan", journey_type="custom", status="active")
        ProgressAlbum.objects.create(user=self.user, title="Mein Album")
        ProgressAlbum.objects.create(user=self.other, title="Fremdes Album")

        response = self.client.get("/api/mobile/export/", **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["data"]
        self.assertEqual([item["title"] for item in payload["beauty_plans"]], ["Mein Plan"])
        self.assertEqual([item["title"] for item in payload["progress_albums"]], ["Mein Album"])
        self.assertIn("aftercare", payload)
