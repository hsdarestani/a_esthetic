from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .goae_billing import calculate_goae_lines, create_goae_draft, goae_draft_pdf_bytes
from .models import Invoice, InvoiceSettings, UserProfile


class GoaEDraftTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="goae-admin", is_staff=True)
        UserProfile.objects.create(user=self.staff, role="admin")
        self.patient = User.objects.create_user(
            username="goae-patient", email="goae@example.com",
            first_name="Anna", last_name="Muster",
        )
        UserProfile.objects.create(
            user=self.patient, role="customer",
            street="Testweg 1", postal_code="60313", city="Frankfurt am Main",
        )

    def test_goae_draft_amount_and_pdf(self):
        invoice = create_goae_draft(
            user=self.patient, actor=self.staff, service_date=date(2026,10,20),
            data={"goae_number":"1","goae_description":"Beratung",
                  "goae_base_eur":"10,00","goae_factor":"2,30","goae_vat_rate":"0"},
        )
        self.assertEqual(invoice.billing_method, "goae")
        self.assertEqual(invoice.status, "draft")
        self.assertEqual(invoice.total_cents, 2300)
        self.assertEqual(invoice.items.first().goae_factor, Decimal("2.30"))
        pdf = goae_draft_pdf_bytes(invoice, InvoiceSettings())
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.client.force_login(self.staff)
        response = self.client.post(reverse("office_invoice_finalize", args=[invoice.pk]))
        self.assertEqual(response.status_code, 409)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "draft")

    def test_goae_high_factor_without_reason_is_rejected(self):
        with self.assertRaises(ValueError):
            create_goae_draft(
                user=self.patient, actor=self.staff, service_date=date(2026,10,20),
                data={"goae_number":"1","goae_description":"Beratung",
                      "goae_base_eur":"10","goae_factor":"3.50","goae_vat_rate":"0"},
            )
        self.assertEqual(Invoice.objects.count(), 0)

    def test_office_goae_submission_creates_draft(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("office_dashboard"),{
            "action":"new_goae_invoice","customer_id":self.patient.pk,
            "service_date":"20.10.2026","goae_number":"1",
            "goae_description":"Beratung","goae_base_eur":"10",
            "goae_factor":"2,30","goae_vat_rate":"0",
        })
        self.assertEqual(response.status_code,302)
        self.assertEqual(Invoice.objects.count(),1)
        self.assertEqual(Invoice.objects.first().billing_method,"goae")

    def test_multiple_lines_net_fee_vat_quantity_and_point_rounding(self):
        invoice = create_goae_draft(
            user=self.patient, actor=self.staff, service_date=date(2026, 10, 20),
            data={"lines": [
                {"goae_number": "1", "goae_description": "Beratung", "goae_points": "80",
                 "goae_factor": "2.30", "goae_vat_rate": "19", "quantity": "2"},
                {"goae_number": "2", "goae_description": "Folgeleistung", "goae_base_eur": "10",
                 "goae_factor": "1", "goae_vat_rate": "0"},
            ]},
        )
        # 80 × 0.0582873 × 2.3 = 10.7248632 EUR -> 10.72 EUR per service.
        self.assertEqual(invoice.items.count(), 2)
        self.assertEqual(invoice.subtotal_cents, 3144)
        self.assertEqual(invoice.tax_cents, 407)
        self.assertEqual(invoice.total_cents, 3551)

    def test_rejects_nonfinite_and_out_of_category_factors(self):
        entry = {"goae_number": "1", "goae_description": "Testleistung",
                 "goae_base_eur": "10", "goae_factor": "1.9",
                 "goae_vat_rate": "19", "goae_category": "technical"}
        for update in ({}, {"goae_factor": "2.51", "goae_justification": "Individuelle Prüfung"},
                       {"goae_factor": "NaN"}, {"goae_factor": "1.5", "quantity": "1.1"},
                       {"goae_factor": "1.5", "goae_base_eur": "Infinity"}):
            with self.assertRaises(ValueError):
                calculate_goae_lines(entry | update)
