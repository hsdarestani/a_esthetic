from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .goae_billing import create_goae_draft, goae_draft_pdf_bytes
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
