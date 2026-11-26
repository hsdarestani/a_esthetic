import json
from unittest.mock import patch
from uuid import uuid4

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
    def test_draft_retry_returns_existing_invoice_and_refuses_changed_request(self, verified):
        payload = {
            "billing_method": "goae", "customer_id": self.customer.pk,
            "service_date": "2026-10-20", "goae_number": "1",
            "goae_description": "Ärztliche Beratung", "goae_base_eur": "10,00",
            "goae_factor": "2,30", "goae_vat_rate": "0",
        }
        def post_draft(data):
            return self.client.post(self.base + "draft/", data, content_type="application/json")

        self.assertEqual(post_draft(payload).status_code, 400)
        quote = self.client.post(self.base + 'quote/', payload, content_type='application/json')
        self.assertEqual(quote.status_code, 200, quote.content)
        cents = quote.json()['total_cents']
        self.assertEqual(cents, 2300)
        self.assertFalse(Invoice.objects.exists())
        request_id = str(uuid4())
        payload.update(draft_request_id=request_id, target_total_cents=cents)
        first = post_draft(payload)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(post_draft(dict(reversed(list(payload.items())))).json(), first.json())
        self.assertEqual(post_draft({**payload, "service_date": "2026-10-21"}).status_code, 400)
        self.assertEqual(post_draft({**payload, "draft_request_id": "invalid"}).status_code, 400)
        invoice = Invoice.objects.get(draft_request_id=request_id)
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(invoice.total_cents, cents)
        with patch('reportlab.rl_config.pageCompression', 0):
            pdf = self.client.get(self.base + f'pdf/{invoice.pk}/')
        self.assertEqual(pdf.status_code, 200)
        self.assertIn(b'(23.00 EUR)', pdf.content)
        self.assertIn(b'ENTWURF', pdf.content)

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_patient_search_queries_the_full_active_customer_catalog(self, verified):
        filler = User.objects.bulk_create([User(username=f'patient-test-{i}', last_name='A') for i in range(1001)])
        UserProfile.objects.bulk_create([UserProfile(user=user, role='customer') for user in filler])
        self.customer.first_name = 'Synthetic'
        self.customer.last_name = 'Ziel'
        self.customer.save(update_fields=['first_name', 'last_name'])
        other = User.objects.create_user('synthetic-admin-name', first_name='Synthetic', last_name='Ziel', is_staff=True)
        UserProfile.objects.create(user=other, role='admin')
        reply = self.client.post(self.base + 'patient-search/', {'query': 'Synthetic Ziel'}, content_type='application/json')
        self.assertEqual(reply.status_code, 200)
        row = reply.json()['patients'][0]
        self.assertEqual([row['id'], row['name'], row['email']],
                         [self.customer.pk, 'Synthetic Ziel', self.customer.email])
        self.assertEqual(len(reply.json()['patients']), 1)
        UserProfile.objects.filter(user=self.customer).update(phone='+49 (170) 123-456', street='Testweg 4', postal_code='12345', city='Testort')
        by_phone = self.client.post(self.base + 'patient-search/', {'query': '170123456'}, content_type='application/json')
        self.assertEqual(by_phone.json()['patients'][0]['id'], self.customer.pk)
        self.assertEqual(by_phone.json()['patients'][0]['street'], 'Testweg 4')
        self.assertIn('no-store', reply['Cache-Control'])

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_bridge_does_not_proxy_arbitrary_admin_paths(self, verified):
        response = self.client.get(self.base + "users/")
        self.assertEqual(response.status_code, 404)
