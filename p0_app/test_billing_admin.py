from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from platform_app.mobile_api import _token_for
from platform_app.models import Invoice, InvoiceSettings, Service, UserProfile


class AdminBillingApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="billing-admin",
            email="billing-admin@example.com",
            password="StrongAdminPassword123!",
            is_staff=True,
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        self.token = _token_for(self.admin)
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        self.customer = User.objects.create_user(
            username="billing-customer",
            email="billing-customer@example.com",
            first_name="Max",
            last_name="Muster",
        )
        UserProfile.objects.create(
            user=self.customer,
            role="customer",
            phone="+49 170 0000000",
            street="Testweg 1",
            postal_code="60313",
            city="Frankfurt am Main",
        )
        self.service = Service.objects.create(
            name="Billing Test",
            slug="billing-test",
            category="medical",
            active=True,
        )

    def test_admin_app_can_configure_service_and_create_invoice(self):
        response = self.client.post(
            reverse("p0_mobile_admin_billing_service", args=[self.service.pk]),
            data='{"price":"119,00","vat_rate":"19"}',
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.service.refresh_from_db()
        self.assertEqual(self.service.price_cents, 11900)
        self.assertEqual(str(self.service.vat_rate), "19.00")

        response = self.client.post(
            reverse("p0_mobile_admin_billing_invoices"),
            data=(
                '{"customer_id":%d,"service_id":%d,"service_date":"06.10.2026"}'
                % (self.customer.pk, self.service.pk)
            ),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 201)
        invoice = Invoice.objects.get(user=self.customer)
        self.assertEqual(invoice.total_cents, 11900)
        self.assertEqual(invoice.service_date.isoformat(), "2026-10-06")

    def test_admin_app_can_save_invoice_settings(self):
        response = self.client.post(
            reverse("p0_mobile_admin_billing_settings"),
            data='{"tax_number":"TEST-123","invoice_prefix":"RE","next_sequence":25}',
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        settings = InvoiceSettings.objects.get(pk=1)
        self.assertEqual(settings.tax_number, "TEST-123")
        self.assertEqual(settings.next_sequence, 25)
