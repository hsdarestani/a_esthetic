from django.core.management.base import BaseCommand

from platform_app.models import FeatureModule

from p2_app.models import MemberPass, ShopCategory, ShopOrder, ShopProduct
from p2_app.passes import wallet_provider_status


class Command(BaseCommand):
    help = "Zeigt den produktionsrelevanten P2 Status ohne Secrets auszugeben."

    def handle(self, *args, **options):
        providers = wallet_provider_status()
        self.stdout.write(f"wallet_apple_configured={str(providers['apple']).lower()}")
        self.stdout.write(f"wallet_google_configured={str(providers['google']).lower()}")
        self.stdout.write(f"wallet_pass_records={MemberPass.objects.count()}")
        self.stdout.write(f"shop_categories={ShopCategory.objects.filter(active=True).count()}")
        self.stdout.write(f"shop_products={ShopProduct.objects.filter(active=True).count()}")
        self.stdout.write(f"shop_orders={ShopOrder.objects.count()}")
        self.stdout.write(
            "p2_modules=" + ",".join(
                FeatureModule.objects.filter(key__in=["wallet-pass", "beauty-cabinet", "shop-orders"], enabled=True)
                .order_by("key")
                .values_list("key", flat=True)
            )
        )
