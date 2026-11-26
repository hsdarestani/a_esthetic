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
        self.assertIn(b'(23,00 EUR)', pdf.content)
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

    @patch('p0_app.book_billing_bridge._internal_authorized', return_value=True)
    def test_pdf_export_standalone_matching_document_and_pagination(self, verified):
        import os
        import re
        from pathlib import Path
        from platform_app.models import InvoiceSettings
        from platform_app.goae_billing import goae_draft_pdf_bytes

        InvoiceSettings.objects.create(pk=1, company_name='Synthetische Privatpraxis', street='Teststraße 42', tax_number='TEST-123')
        line = {'goae_number': '1', 'goae_description': 'Ärztliche Beratung', 'goae_base_eur': '10,00',
                'goae_factor': '2,30', 'goae_vat_rate': '19', 'clinical_confirmed': True}
        payload = {'billing_method': 'goae', 'customer_id': self.customer.pk, 'service_date': '2026-11-26',
                   'lines': [line], 'target_total_cents': 2737,
                   'book_preview': {'invoice_date': '2026-11-26', 'due_date': '2026-12-10', 'diagnosis': 'Synthetischer Anlass'}}
        with patch('reportlab.rl_config.pageCompression', 0):
            preview = self.client.post(self.base + 'pdf-preview/', payload, content_type='application/json')
            self.assertEqual(preview.status_code, 200, preview.content[:200])
            self.assertEqual(preview['Content-Type'], 'application/pdf')
            self.assertIn('attachment', preview['Content-Disposition'])
            self.assertFalse(Invoice.objects.exists())
            self.assertEqual(len(re.findall(rb'/Type /Page\b', preview.content)), 1)
            self.assertIn(b'ENTWURF', preview.content)
            self.assertIn(b'27,37 EUR', preview.content)
            self.assertEqual(self.client.post(self.base + 'pdf-preview/', {**payload, 'target_total_cents': 1}, content_type='application/json').status_code, 400)
            saved = self.client.post(self.base + 'draft/', {**payload, 'draft_request_id': str(uuid4())}, content_type='application/json')
            self.assertEqual(saved.status_code, 201, saved.content)
            invoice = Invoice.objects.get()
            self.assertEqual(invoice.total_cents, 2737)
            self.assertEqual(invoice.native_draft_data['book_preview'], payload['book_preview'])
            stored = self.client.get(self.base + f'pdf/{invoice.pk}/')
            self.assertEqual(stored.status_code, 200)
            self.assertIn(b'27,37 EUR', stored.content)
            long_pdf = self.client.post(self.base + 'pdf-preview/', {**payload, 'lines': [line] * 35, 'target_total_cents': 2737 * 35}, content_type='application/json')
            self.assertEqual(long_pdf.status_code, 200, long_pdf.content[:200])
            self.assertGreater(len(re.findall(rb'/Type /Page\b', long_pdf.content)), 1)
            self.assertIn(b'957,95 EUR', long_pdf.content)
            invoice.status = 'issued'
            invoice.number = 'TEST-001'
            issued = goae_draft_pdf_bytes(invoice, InvoiceSettings.objects.get(pk=1))
            self.assertNotIn(b'ENTWURF', issued)
            self.assertIn(b'TEST-001', issued)
        output = os.environ.get('GOAE_PDF_QA_DIR')
        if output:
            folder = Path(output)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'preview.pdf').write_bytes(preview.content)
            (folder / 'saved.pdf').write_bytes(stored.content)
            (folder / 'long.pdf').write_bytes(long_pdf.content)

    @patch("p0_app.book_billing_bridge._internal_authorized", return_value=True)
    def test_quick_template_calculates_and_saves_only_a_draft(self, verified):
        template = {'consult': {'label': 'Testberatung', 'version': '1', 'approved_by': 'Fixture',
                                'lines': [{'number': '1', 'quantity': 1, 'per_unit': True,
                                           'factor': '2.30', 'vat_rate': '19'},
                                          {'kind': 'material', 'description': 'Testmaterial', 'quantity': 1,
                                           'unit_cost_eur': '5.00', 'vat_rate': '19'}]}}
        payload = {'customer_id': self.customer.pk, 'service_date': '2026-10-20',
                   'book_preview': {'invoice_date': '2026-10-21'},
                   'quick_invoice': {'treatment': 'consult', 'version': '1', 'quantity': 2, 'desired_cents': 50000}}
        def post(operation, data):
            return self.client.post(self.base + operation + '/', data, content_type='application/json')
        with self.settings(GOAE_QUICK_TEMPLATES=template):
            self.assertIn('consult', self.client.get(self.base + 'goae/').json()['quick_templates'])
            quote = post('quick-quote', payload)
            self.assertEqual(quote.status_code, 200, quote.content)
            self.assertNotEqual(quote.json()['total_cents'], 50000)
            self.assertEqual(len(quote.json()['items']), 2)
            self.assertFalse(Invoice.objects.exists())
            payload['draft_request_id'] = str(uuid4())
            saved = post('quick-draft', payload)
            self.assertEqual(saved.status_code, 200, saved.content)
            self.assertEqual(post('quick-draft', payload).json(), saved.json())
            invoice = Invoice.objects.get()
            self.assertEqual(invoice.status, 'draft')
            self.assertEqual(invoice.total_cents, quote.json()['total_cents'])
            self.assertEqual(invoice.native_draft_data['quick_invoice']['desired_cents'], 50000)
            self.assertEqual(str(invoice.items.get(goae_number='1').goae_factor), '2.3000')
            with patch('reportlab.rl_config.pageCompression', 0):
                pdf = self.client.get(self.base + f'pdf/{invoice.pk}/')
            self.assertEqual(pdf.status_code, 200)
            self.assertIn(b'ENTWURF', pdf.content)
            self.assertEqual(post(f'finalize/{invoice.pk}', {}).status_code, 409)

        self.assertEqual(post('quick-quote', payload).status_code, 400)
