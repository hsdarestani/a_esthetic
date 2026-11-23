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

    def test_material_expense_requires_eligibility_and_receipt_and_no_markup(self):
        item = {"kind":"material", "goae_description":"Synthetisches Material",
                "goae_base_eur":"12.50", "goae_vat_rate":"19", "quantity":"2",
                "material_receipt_reference":"TEST-RECEIPT", "material_eligible": True,
                "goae_factor":"3.5"}
        results = calculate_goae_lines({"lines":[item]})
        self.assertEqual(results[0]['net_cents'], 2500)
        self.assertEqual(results[0]['gross_cents'], 2975)
        self.assertIsNone(results[0]['goae_factor'])
        for update in ({"material_eligible":False}, {"material_receipt_reference":""}):
            with self.assertRaises(ValueError):
                calculate_goae_lines({"lines":[item | update]})

    def test_official_catalog_fixes_points_and_special_blood_collection_limits(self):
        line = {"tariff_source":"official_catalog","clinical_confirmed":True,
                "goae_number":"250","goae_factor":"2.3","goae_vat_rate":"0",
                "goae_category":"general","goae_points":"999","goae_base_eur":"999"}
        # No. 250 appears in section A: 1.8 threshold, 2.5 ordinary ceiling.
        with self.assertRaises(ValueError):
            calculate_goae_lines(line)
        approved = line | {"goae_justification":"Synthetischer Prüfgrund"}
        result = calculate_goae_lines(approved)[0]
        self.assertEqual(result["goae_base_cents"],233)
        self.assertEqual(result["net_cents"],536)
        with self.assertRaises(ValueError):
            calculate_goae_lines(approved | {"goae_factor":"2.51"})
        with self.assertRaises(ValueError):
            calculate_goae_lines(approved | {"clinical_confirmed":False})

    def test_reference_reconciliation_is_not_an_invoice_calculation(self):
        from .goae_tariff import reference_case
        result = reference_case()
        self.assertEqual(result["reference_total_cents"], 23600)
        self.assertEqual(result["medical_cents"], 10280)
        self.assertEqual(result["residual_cents"], 8136)
        self.assertEqual(result["derived_factor"], "3.4896")
        self.assertTrue(result["approval_required"])
        line = {"tariff_source":"official_catalog","clinical_confirmed":True,
                "goae_number":"252","quantity":"10","goae_factor":"3.49",
                "goae_justification":"Synthetischer Prüfgrund","goae_vat_rate":"19"}
        self.assertEqual(calculate_goae_lines(line)[0]["net_cents"],8140)
        self.assertNotEqual(calculate_goae_lines(line)[0]["net_cents"],result["residual_cents"])

    def test_analogous_service_requires_independent_confirmation(self):
        data = {"tariff_source":"official_catalog","clinical_confirmed":True,
                "goae_number":"268","goae_description":"Synthetische Analogleistung",
                "goae_factor":"1","goae_vat_rate":"0","analog":True}
        with self.assertRaises(ValueError):
            calculate_goae_lines(data)
        item = calculate_goae_lines(data | {"analog_confirmed":True})[0]
        self.assertEqual(item["goae_number"], "268 A")
        self.assertEqual(item["net_cents"],758)
        self.assertIn("entsprechend",item["description"])
