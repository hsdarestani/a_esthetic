import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def generate_pass_serial():
    return secrets.token_urlsafe(24)


def generate_order_number():
    return "APO-" + secrets.token_hex(6).upper()


class MemberPass(TimeStampedModel):
    PROVIDER = [("apple", "Apple Wallet"), ("google", "Google Wallet")]
    STATUS = [
        ("pending", "Konfiguration erforderlich"),
        ("active", "Aktiv"),
        ("revoked", "Widerrufen"),
        ("failed", "Fehlgeschlagen"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p2_wallet_passes")
    provider = models.CharField(max_length=10, choices=PROVIDER)
    serial_number = models.CharField(max_length=80, unique=True, default=generate_pass_serial, editable=False)
    external_object_id = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=15, choices=STATUS, default="pending")
    last_error = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "provider"], name="p2_unique_wallet_provider_per_user")]
        ordering = ["provider"]

    def __str__(self):
        return f"{self.user} – {self.get_provider_display()}"


class ShopCategory(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Shop-Kategorie"
        verbose_name_plural = "Shop-Kategorien"

    def __str__(self):
        return self.name


class ShopProduct(TimeStampedModel):
    category = models.ForeignKey(ShopCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    ingredients = models.TextField(blank=True)
    price_cents = models.PositiveIntegerField(default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    allow_collect = models.BooleanField(default=True)
    allow_shipping = models.BooleanField(default=False)
    image_url = models.URLField(blank=True)
    sku = models.CharField(max_length=80, blank=True, db_index=True)
    is_prescription_product = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["category_id", "name"]
        verbose_name = "Shop-Produkt"
        verbose_name_plural = "Shop-Produkte"

    def clean(self):
        if self.is_prescription_product:
            raise ValidationError("Verschreibungspflichtige Produkte dürfen nicht über den A+ Shop verkauft werden.")

    @property
    def in_stock(self):
        return self.stock_quantity > 0

    def __str__(self):
        return self.name


class CabinetProduct(TimeStampedModel):
    SOURCE = [("manual", "Manuell"), ("shop", "A+ Shop")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p2_cabinet_products")
    name = models.CharField(max_length=180)
    brand = models.CharField(max_length=120, blank=True)
    barcode = models.CharField(max_length=64, blank=True)
    category = models.CharField(max_length=80, blank=True)
    opened_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=12, choices=SOURCE, default="manual")
    shop_product = models.ForeignKey(ShopProduct, null=True, blank=True, on_delete=models.SET_NULL, related_name="cabinet_entries")
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["archived", "expires_on", "name"]
        verbose_name = "Beauty-Cabinet Produkt"
        verbose_name_plural = "Beauty-Cabinet Produkte"

    def __str__(self):
        return f"{self.user} – {self.name}"


class RoutineStep(TimeStampedModel):
    PERIOD = [("morning", "Morgen"), ("evening", "Abend"), ("weekly", "Wöchentlich")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="p2_routine_steps")
    product = models.ForeignKey(CabinetProduct, on_delete=models.CASCADE, related_name="routine_steps")
    period = models.CharField(max_length=12, choices=PERIOD)
    weekdays = models.JSONField(default=list, blank=True)
    note = models.CharField(max_length=300, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["period", "sort_order", "id"]
        verbose_name = "Beauty-Routine Schritt"
        verbose_name_plural = "Beauty-Routine Schritte"

    def clean(self):
        if self.product_id and self.user_id and self.product.user_id != self.user_id:
            raise ValidationError("Routine und Produkt müssen demselben Kundenkonto gehören.")

    def __str__(self):
        return f"{self.get_period_display()} – {self.product.name}"


class ShopOrder(TimeStampedModel):
    STATUS = [
        ("pending", "Bestellung eingegangen"),
        ("paid", "Bezahlt"),
        ("ready", "Abholbereit"),
        ("shipped", "Versendet"),
        ("completed", "Abgeschlossen"),
        ("cancelled", "Storniert"),
    ]
    DELIVERY = [("collect", "Click & Collect"), ("shipping", "Versand")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="p2_shop_orders")
    order_number = models.CharField(max_length=32, unique=True, default=generate_order_number, editable=False)
    status = models.CharField(max_length=15, choices=STATUS, default="pending")
    delivery_method = models.CharField(max_length=12, choices=DELIVERY, default="collect")
    shipping_name = models.CharField(max_length=160, blank=True)
    shipping_address = models.TextField(blank=True)
    customer_note = models.TextField(blank=True)
    total_cents = models.PositiveIntegerField(default=0, editable=False)
    payment_reference = models.CharField(max_length=160, blank=True)
    stock_released_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Shop-Bestellung"
        verbose_name_plural = "Shop-Bestellungen"

    def clean(self):
        if self.delivery_method == "shipping" and not self.shipping_address.strip():
            raise ValidationError("Für Versand ist eine Lieferadresse erforderlich.")
        if self.stock_released_at and self.status != "cancelled":
            raise ValidationError("Eine stornierte Bestellung mit freigegebenem Bestand kann nicht reaktiviert werden.")

    def __str__(self):
        return self.order_number


class ShopOrderItem(TimeStampedModel):
    order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(ShopProduct, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=180)
    quantity = models.PositiveIntegerField(default=1)
    unit_price_cents = models.PositiveIntegerField()
    line_total_cents = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["order", "product"], name="p2_unique_product_per_order")]

    def __str__(self):
        return f"{self.order.order_number} – {self.product_name} × {self.quantity}"


class ShopOrderEvent(TimeStampedModel):
    order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=15, choices=ShopOrder.STATUS)
    note = models.CharField(max_length=300, blank=True)
    visible_to_customer = models.BooleanField(default=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Bestellstatus"
        verbose_name_plural = "Bestellstatus"

    def __str__(self):
        return f"{self.order.order_number} – {self.get_status_display()}"
