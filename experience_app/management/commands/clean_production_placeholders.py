from django.core.management.base import BaseCommand

from platform_app.models import (
    Campaign,
    FeatureModule,
    GiftCard,
    IntegrationConfig,
    PackageDefinition,
    Referral,
    Reward,
)
from experience_app.models import (
    Badge,
    BeautyEvent,
    Challenge,
    ContentArticle,
    FAQ,
    KnowledgeArticle,
    MembershipBenefit,
    Offer,
    Quiz,
    ShopCategory,
    ShopProduct,
)


class Command(BaseCommand):
    help = "Entfernt ausschließlich bekannte Seed- und Platzhalterinhalte."

    def handle(self, *args, **options):
        # Keep the integration objects, but remove technical placeholder copy from the UI/admin.
        IntegrationConfig.objects.update(
            status="",
            credential_reference="",
            settings={},
        )

        # Remove generic copy that was only added to make an early prototype look populated.
        MembershipBenefit.objects.filter(
            description="Von A+ Esthetic bereitgestellter Vorteil."
        ).update(description="")

        ShopProduct.objects.filter(
            slug__in=["a-plus-pflege-set", "a-plus-sample-box"]
        ).delete()
        ShopCategory.objects.filter(slug="pflege", products__isnull=True).delete()

        KnowledgeArticle.objects.filter(
            slug__in=["membership", "process", "safety"]
        ).delete()
        Challenge.objects.filter(
            title__in=["7 Tage Pflegeroutine", "A+ Wissen entdecken"]
        ).delete()
        Badge.objects.filter(slug="beauty-starter").delete()
        Quiz.objects.filter(title="A+ Datenschutz Quiz").delete()
        FAQ.objects.filter(
            question__in=[
                "Ersetzt die App eine ärztliche Beratung?",
                "Sind A+ Coins mit einer Arztvergütung verbunden?",
            ]
        ).delete()
        Offer.objects.filter(title="Double Coin – Lerninhalte").delete()
        BeautyEvent.objects.filter(title="A+ Member Information Night").delete()
        ContentArticle.objects.filter(slug="a-plus-app-datenschutz").delete()

        Reward.objects.filter(
            name__in=[
                "Skin-Care Sample Set",
                "A+ Skin Analysis",
                "Priority Booking Pass",
                "A+ Event Einladung",
            ]
        ).delete()
        PackageDefinition.objects.filter(name="Laser Pflegepaket").delete()
        Campaign.objects.filter(name="A+ Beauty Club Willkommen").delete()
        GiftCard.objects.filter(code="APLUS-DEMO-100").delete()
        Referral.objects.filter(code="APLUS-SOPHIE").delete()

        # Module descriptions are real product labels, not demo content. Keep them available
        # for API clients, but the polished management views no longer display them.
        count = FeatureModule.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Platzhalter bereinigt; {count} Module bleiben erhalten."
            )
        )
