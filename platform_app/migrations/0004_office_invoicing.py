# Generated for A+ Esthetic Office invoicing
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_app", "0003_account_onboarding"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="street",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="postal_code",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="city",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="country",
            field=models.CharField(default="DE", max_length=2),
        ),
        migrations.AddField(
            model_name="service",
            name="price_cents",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="service",
            name="vat_rate",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.CreateModel(
            name="InvoiceSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(default="A+ Esthetic GmbH", max_length=180)),
                ("street", models.CharField(default="Stiftstraße 14", max_length=180)),
                ("postal_code", models.CharField(default="60313", max_length=20)),
                ("city", models.CharField(default="Frankfurt am Main", max_length=120)),
                ("country", models.CharField(default="DE", max_length=2)),
                ("email", models.EmailField(default="info@a-esthetic.de", max_length=254)),
                ("phone", models.CharField(default="069 71417012", max_length=40)),
                ("tax_number", models.CharField(blank=True, max_length=80)),
                ("vat_id", models.CharField(blank=True, max_length=80)),
                ("iban", models.CharField(blank=True, max_length=64)),
                ("bic", models.CharField(blank=True, max_length=32)),
                ("bank_name", models.CharField(blank=True, max_length=120)),
                ("invoice_prefix", models.CharField(default="RE", max_length=20)),
                ("next_sequence", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Rechnungseinstellungen",
                "verbose_name_plural": "Rechnungseinstellungen",
            },
        ),
        migrations.CreateModel(
            name="CheckInSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_checkins", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="checkin_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=40, null=True, unique=True)),
                ("status", models.CharField(choices=[("draft", "Entwurf"), ("issued", "Ausgestellt"), ("cancelled", "Storniert")], default="draft", max_length=20)),
                ("service_date", models.DateField()),
                ("issued_on", models.DateField(blank=True, null=True)),
                ("customer_name", models.CharField(max_length=180)),
                ("customer_email", models.EmailField(blank=True, max_length=254)),
                ("customer_street", models.CharField(blank=True, max_length=180)),
                ("customer_postal_code", models.CharField(blank=True, max_length=20)),
                ("customer_city", models.CharField(blank=True, max_length=120)),
                ("subtotal_cents", models.PositiveIntegerField(default=0)),
                ("tax_cents", models.PositiveIntegerField(default=0)),
                ("total_cents", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("appointment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invoices", to="platform_app.appointment")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_invoices", to=settings.AUTH_USER_MODEL)),
                ("document", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invoice_record", to="platform_app.securedocument")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="InvoiceItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(max_length=220)),
                ("quantity", models.DecimalField(decimal_places=2, default=1, max_digits=8)),
                ("unit_gross_cents", models.PositiveIntegerField()),
                ("vat_rate", models.DecimalField(decimal_places=2, max_digits=5)),
                ("net_cents", models.PositiveIntegerField()),
                ("tax_cents", models.PositiveIntegerField()),
                ("gross_cents", models.PositiveIntegerField()),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="platform_app.invoice")),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="platform_app.service")),
            ],
        ),
    ]
