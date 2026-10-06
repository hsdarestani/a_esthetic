import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from allauth.account.models import EmailAddress

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

    def test_office_staff_login_bypasses_customer_email_verification(self):
        EmailAddress.objects.create(
            user=self.staff,
            email=self.staff.email,
            primary=True,
            verified=False,
        )
        response = self.client.get(reverse("office_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/office/admin/login/", response.url)

        response = self.client.post(
            reverse("office_staff_login"),
            {
                "email": self.staff.email,
                "password": "StrongTestPassword123!",
                "next": reverse("office_dashboard"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("office_dashboard"))
        response = self.client.get(reverse("office_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A+ ESTHETIC OFFICE")

    def test_customer_cannot_use_office_staff_login(self):
        customer = User.objects.create_user(
            username="ordinary-customer",
            email="ordinary@example.com",
            password="StrongCustomerPassword123!",
        )
        UserProfile.objects.create(user=customer, role="customer")
        response = self.client.post(
            reverse("office_staff_login"),
            {
                "email": customer.email,
                "password": "StrongCustomerPassword123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "keinen Zugriff")

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

    def test_admin_can_save_billing_settings_and_service_tax(self):
        service = Service.objects.create(
            name="Hydra Test",
            slug="hydra-test",
            category="medical",
            price_label="",
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("office_settings"),
            {
                "action": "invoice_settings",
                "company_name": "A+ Esthetic GmbH",
                "street": "Stiftstraße 14",
                "postal_code": "60313",
                "city": "Frankfurt am Main",
                "email": "info@a-esthetic.de",
                "phone": "069 71417012",
                "tax_number": "TEST-99",
                "vat_id": "",
                "bank_name": "Testbank",
                "iban": "DE001234",
                "bic": "TESTDEFF",
                "invoice_prefix": "RE",
                "next_sequence": "42",
            },
        )
        self.assertEqual(response.status_code, 200)
        settings = InvoiceSettings.objects.get(pk=1)
        self.assertEqual(settings.tax_number, "TEST-99")
        self.assertEqual(settings.next_sequence, 42)

        response = self.client.post(
            reverse("office_settings"),
            {
                "action": "service_prices",
                f"service_{service.pk}_price": "119,00",
                f"service_{service.pk}_vat": "19",
            },
        )
        self.assertEqual(response.status_code, 200)
        service.refresh_from_db()
        self.assertEqual(service.price_cents, 11900)
        self.assertEqual(str(service.vat_rate), "19.00")
        self.assertEqual(service.price_label, "119,00 €")

    def test_invoice_accepts_german_service_date(self):
        customer = User.objects.create_user(
            username="german-date-customer",
            email="date@example.com",
            first_name="Datum",
            last_name="Test",
        )
        UserProfile.objects.create(
            user=customer,
            role="customer",
            street="Testweg 1",
            postal_code="60313",
            city="Frankfurt am Main",
        )
        service = Service.objects.create(
            name="Datum Behandlung",
            slug="datum-behandlung",
            category="medical",
            price_label="119,00 €",
            price_cents=11900,
            vat_rate="19.00",
        )
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("office_dashboard"),
            {
                "action": "new_invoice",
                "customer_id": customer.pk,
                "service_id": service.pk,
                "service_date": "06.10.2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get(user=customer)
        self.assertEqual(invoice.service_date.isoformat(), "2026-10-06")

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
