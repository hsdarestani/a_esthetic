import django.db.models.deletion
import p2_app.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("platform_app", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberPass",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(choices=[("apple", "Apple Wallet"), ("google", "Google Wallet")], max_length=10)),
                ("serial_number", models.CharField(default=p2_app.models.generate_pass_serial, editable=False, max_length=80, unique=True)),
                ("external_object_id", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(choices=[("pending", "Konfiguration erforderlich"), ("active", "Aktiv"), ("revoked", "Widerrufen"), ("failed", "Fehlgeschlagen")], default="pending", max_length=15)),
                ("last_error", models.TextField(blank=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p2_wallet_passes", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["provider"]},
        ),
        migrations.CreateModel(
            name="ShopCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(unique=True)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
            ],
            options={"verbose_name": "Shop-Kategorie", "verbose_name_plural": "Shop-Kategorien", "ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="ShopProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(unique=True)),
                ("description", models.TextField(blank=True)),
                ("ingredients", models.TextField(blank=True)),
                ("price_cents", models.PositiveIntegerField(default=0)),
                ("stock_quantity", models.PositiveIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("allow_collect", models.BooleanField(default=True)),
                ("allow_shipping", models.BooleanField(default=False)),
                ("image_url", models.URLField(blank=True)),
                ("sku", models.CharField(blank=True, db_index=True, max_length=80)),
                ("is_prescription_product", models.BooleanField(default=False, editable=False)),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="p2_app.shopcategory")),
            ],
            options={"verbose_name": "Shop-Produkt", "verbose_name_plural": "Shop-Produkte", "ordering": ["category_id", "name"]},
        ),
        migrations.CreateModel(
            name="CabinetProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=180)),
                ("brand", models.CharField(blank=True, max_length=120)),
                ("barcode", models.CharField(blank=True, max_length=64)),
                ("category", models.CharField(blank=True, max_length=80)),
                ("opened_on", models.DateField(blank=True, null=True)),
                ("expires_on", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("source", models.CharField(choices=[("manual", "Manuell"), ("shop", "A+ Shop")], default="manual", max_length=12)),
                ("archived", models.BooleanField(default=False)),
                ("shop_product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cabinet_entries", to="p2_app.shopproduct")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p2_cabinet_products", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Beauty-Cabinet Produkt", "verbose_name_plural": "Beauty-Cabinet Produkte", "ordering": ["archived", "expires_on", "name"]},
        ),
        migrations.CreateModel(
            name="RoutineStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period", models.CharField(choices=[("morning", "Morgen"), ("evening", "Abend"), ("weekly", "Wöchentlich")], max_length=12)),
                ("weekdays", models.JSONField(blank=True, default=list)),
                ("note", models.CharField(blank=True, max_length=300)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("active", models.BooleanField(default=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="routine_steps", to="p2_app.cabinetproduct")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p2_routine_steps", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Beauty-Routine Schritt", "verbose_name_plural": "Beauty-Routine Schritte", "ordering": ["period", "sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="ShopOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order_number", models.CharField(default=p2_app.models.generate_order_number, editable=False, max_length=32, unique=True)),
                ("status", models.CharField(choices=[("pending", "Bestellung eingegangen"), ("paid", "Bezahlt"), ("ready", "Abholbereit"), ("shipped", "Versendet"), ("completed", "Abgeschlossen"), ("cancelled", "Storniert")], default="pending", max_length=15)),
                ("delivery_method", models.CharField(choices=[("collect", "Click & Collect"), ("shipping", "Versand")], default="collect", max_length=12)),
                ("shipping_name", models.CharField(blank=True, max_length=160)),
                ("shipping_address", models.TextField(blank=True)),
                ("customer_note", models.TextField(blank=True)),
                ("total_cents", models.PositiveIntegerField(default=0, editable=False)),
                ("payment_reference", models.CharField(blank=True, max_length=160)),
                ("stock_released_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="p2_shop_orders", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Shop-Bestellung", "verbose_name_plural": "Shop-Bestellungen", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ShopOrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product_name", models.CharField(max_length=180)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("unit_price_cents", models.PositiveIntegerField()),
                ("line_total_cents", models.PositiveIntegerField()),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="p2_app.shoporder")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="p2_app.shopproduct")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="ShopOrderEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("pending", "Bestellung eingegangen"), ("paid", "Bezahlt"), ("ready", "Abholbereit"), ("shipped", "Versendet"), ("completed", "Abgeschlossen"), ("cancelled", "Storniert")], max_length=15)),
                ("note", models.CharField(blank=True, max_length=300)),
                ("visible_to_customer", models.BooleanField(default=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="p2_app.shoporder")),
            ],
            options={"verbose_name": "Bestellstatus", "verbose_name_plural": "Bestellstatus", "ordering": ["created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="memberpass",
            constraint=models.UniqueConstraint(fields=("user", "provider"), name="p2_unique_wallet_provider_per_user"),
        ),
        migrations.AddConstraint(
            model_name="shoporderitem",
            constraint=models.UniqueConstraint(fields=("order", "product"), name="p2_unique_product_per_order"),
        ),
    ]
