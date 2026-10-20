import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from platform_app.models import Invoice, UserProfile


class BookingBillingBridgeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="billing-bridge-admin", is_active=True)
        UserProfile.objects.create(user=self.admin, role="admin")
        self.customer = User.objects.create_user(
            username="billing-bridge-patient", email="patient@example.test",
            first_name="Anna", last_name="Muster", is_active=True)
        UserProfile.objects.create(user=self.customer, role="customer",
                                   street="Testweg 12", postal_code="60313", city="Frankfurt")
        self.base = "/api/mobile/internal/book-billing/"

    def test_refuses_any_unauthenticated_browser_or_cross_site_request(self):
        response = self.client.get(self.base + "overview/")
        self.assertEqual(response.status_code, 401)
        response = self.client.post(self.base + "invoices/",
                                    data=json.dumps({"billing_method": "goae"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Invoice.objects.count(), 0)

    @patch("p0_app.billing_admin_views.sync_service_catalog_from_book")
    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_verified_booking_admin_reads_app_invoice_database(self, verified, sync):
        response = self.client.get(self.base + "overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        self.assertIn("invoices", response.json())
        self.assertIn("customers", response.json())

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_verified_booking_server_creates_only_nonfinal_goae_draft(self, verified):
        payload = {
            "billing_method": "goae", "customer_id": self.customer.pk,
            "service_date": "20.10.2026", "goae_number": "1",
            "goae_description": "Ärztliche Beratung", "goae_base_eur": "10,00",
            "goae_factor": "2,30", "goae_vat_rate": "0",
        }
        response = self.client.post(self.base + "invoices/", data=json.dumps(payload),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        invoice = Invoice.objects.get(user=self.customer)
        self.assertEqual(invoice.billing_method, "goae")
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.total_cents, 2300)
        pdf = self.client.get(self.base + f"pdf/{invoice.pk}/")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn("no-store", pdf["Cache-Control"])
        final = self.client.post(self.base + f"finalize/{invoice.pk}/",
                                 data=json.dumps({}), content_type="application/json")
        self.assertEqual(final.status_code, 409)

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_bridge_does_not_proxy_arbitrary_admin_paths(self, verified):
        response = self.client.get(self.base + "users/")
        self.assertEqual(response.status_code, 404)
