import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import CheckInSession, Invoice, InvoiceSettings, Service, UserProfile


TEST_MEDIA = tempfile.mkdtemp(prefix="aesthetic-office-test-")


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class OfficeInvoicingTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)

    def setUp(self):
        self.staff = User.objects.create_user(
            username="office-admin",
            email="office@example.com",
            password="StrongTestPassword123!",
            is_staff=True,
        )
        UserProfile.objects.create(user=self.staff, role="admin")

    def test_ipad_checkin_creates_customer_and_address(self):
        session = CheckInSession.objects.create(
            created_by=self.staff,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        response = self.client.post(
            reverse("office_checkin", args=[session.token]),
            {
                "salutation": "frau",
                "first_name": "Anna",
                "last_name": "Muster",
                "email": "anna@example.com",
                "phone": "+49 170 1234567",
                "street": "Teststraße 12",
                "postal_code": "60313",
                "city": "Frankfurt am Main",
            },
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="anna@example.com")
        self.assertEqual(user.profile.street, "Teststraße 12")
        self.assertTrue(hasattr(user, "member_account"))
        session.refresh_from_db()
        self.assertEqual(session.customer_id, user.pk)
        self.assertIsNotNone(session.completed_at)


    def test_public_ipad_intake_needs_no_login(self):
        response = self.client.get(reverse("office_intake"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ihre Daten")
        self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow, noarchive")

        response = self.client.post(
            reverse("office_intake"),
            {
                "salutation": "herr",
                "first_name": "Ali",
                "last_name": "Beispiel",
                "email": "ali@example.com",
                "phone": "+49 171 1112233",
                "street": "Zeil 10",
                "postal_code": "60313",
                "city": "Frankfurt am Main",
                "website": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vielen Dank")
        user = User.objects.get(email="ali@example.com")
        self.assertEqual(user.profile.street, "Zeil 10")
        self.assertTrue(hasattr(user, "member_account"))

    def test_invoice_can_be_issued_to_pdf(self):
        customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            first_name="Max",
            last_name="Muster",
        )
        UserProfile.objects.create(
            user=customer,
            role="customer",
            phone="+49 170 9876543",
            street="Musterweg 1",
            postal_code="60313",
            city="Frankfurt am Main",
        )
        service = Service.objects.create(
            name="Testbehandlung",
            slug="testbehandlung",
            category="medical",
            price_label="119 EUR",
            price_cents=11900,
            vat_rate="19.00",
        )
        InvoiceSettings.objects.create(pk=1, tax_number="TEST-123")

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("office_dashboard"),
            {
                "action": "new_invoice",
                "customer_id": customer.pk,
                "service_id": service.pk,
                "service_date": "2026-10-06",
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get(user=customer)
        self.assertEqual(invoice.subtotal_cents, 10000)
        self.assertEqual(invoice.tax_cents, 1900)
        self.assertEqual(invoice.total_cents, 11900)

        response = self.client.post(reverse("office_invoice_finalize", args=[invoice.pk]))
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "issued")
        self.assertTrue(invoice.number.startswith("RE"))
        self.assertIsNotNone(invoice.document_id)
        self.assertTrue(invoice.document.file.name.endswith(".pdf"))
