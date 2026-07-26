from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from platform_app.models import (
    FeatureModule,
    MembershipTier,
    Service,
    StaffMember,
    WorkingHour,
)

from experience_app.models import (
    AftercareTask,
    AftercareTemplate,
    Badge,
    BeautyEvent,
    Challenge,
    CoinRule,
    ContentArticle,
    FAQ,
    KnowledgeArticle,
    MembershipBenefit,
    Offer,
    Quiz,
    QuizQuestion,
    ShopCategory,
    ShopProduct,
)


MODULES = [
    ("membership", "Mitgliedskarte & Membership", "Digitale Karte, Status, Vorteile und Wallet-Pässe", 10),
    ("wallet", "A+ Wallet", "Coins, Credit, Rewards und Transaktionen", 20),
    ("giftcards", "Gift Cards", "Digitale A+ Geschenkkarten", 30),
    ("packages", "Pakete", "Sitzungen, Gültigkeit und Nutzung", 40),
    ("booking", "Terminbuchung", "Slots, Warteliste, Änderungen und Kalender", 50),
    ("checkin", "QR Check-in", "Ankunft und Status", 60),
    ("passport", "Beauty Passport", "Freigegebener Verlauf und Dokumente", 70),
    ("before_after", "Vorher-Nachher", "Private Fotoalben und Verlauf", 80),
    ("reminders", "Erinnerungen", "Termin-, Pflege- und Produkterinnerungen", 90),
    ("followup", "Nachsorge & Follow-up", "Checklisten und sichere Rückmeldung", 100),
    ("beauty_plan", "Beauty Plan", "Ziele, Budget und Journeys", 110),
    ("ai", "Beauty Wissensassistent", "Freigegebene Informationen ohne medizinische Beratung", 120),
    ("cabinet", "Beauty Cabinet", "Produkte, Ablaufdaten und Routinen", 130),
    ("shop", "A+ Shop", "Produkte, Click & Collect und Versand", 140),
    ("gamification", "Gamification", "Challenges, Badges und Quiz", 150),
    ("referrals", "Freunde werben", "Verifizierte Empfehlungen", 160),
    ("communication", "Kommunikation", "Chat, Rückruf und FAQ", 170),
    ("offers", "Angebote", "Transparente A+ Kampagnen", 180),
    ("events", "Events", "Workshops und Member Events", 190),
    ("content", "Inhalte", "Artikel, Videos und Lerninhalte", 200),
    ("feedback", "Feedback & Umfragen", "Bewertungen, Surveys und Beschwerden", 210),
    ("concierge", "Premium Support", "Organisatorische Concierge-Anfragen", 220),
    ("privacy", "Datenschutz-Center", "Einwilligungen, Export, Löschung und Geräte", 230),
    ("management", "Management", "Module, Integrationen und Reports", 240),
]


class Command(BaseCommand):
    help = "Legt den vollständigen A+ Esthetic Funktionskatalog als sichere Demo-Grundlage an."

    def handle(self, *args, **options):
        for key, name, description, order in MODULES:
            FeatureModule.objects.update_or_create(
                key=key,
                defaults={"name_de": name, "description_de": description, "enabled": True, "customer_visible": key != "management", "sort_order": order},
            )

        tiers = {}
        tier_data = [
            ("member", "A+ Member", 0, 1, 10),
            ("glow", "A+ Glow", 1900, 1.15, 20),
            ("signature", "A+ Signature", 4900, 1.35, 30),
            ("black", "A+ Black", 9900, 1.60, 40),
        ]
        for slug, name, fee, multiplier, priority in tier_data:
            tier, _ = MembershipTier.objects.update_or_create(slug=slug, defaults={"name": name, "monthly_fee_cents": fee, "coin_multiplier": multiplier, "priority": priority, "active": True})
            tiers[slug] = tier

        benefits = {
            "member": [("Digitale Mitgliedskarte", "service"), ("A+ Coins sammeln", "service")],
            "glow": [("Bevorzugte Warteliste", "priority"), ("Geburtstagsinformation von A+", "service")],
            "signature": [("Frühere Buchungsfenster", "priority"), ("Zugang zu A+ Member Events", "event"), ("Schnellerer A+ Support", "support")],
            "black": [("Persönliche A+ Ansprechperson", "support"), ("Exklusive A+ Terminfenster", "priority"), ("A+ Premium Eventzugang", "event")],
        }
        for slug, rows in benefits.items():
            for index, (title, benefit_type) in enumerate(rows):
                MembershipBenefit.objects.update_or_create(tier=tiers[slug], title=title, defaults={"benefit_type": benefit_type, "description": "Von A+ Esthetic bereitgestellter Vorteil.", "active": True, "sort_order": index * 10})

        coin_defaults = {
            "purchase_product": 100,
            "booking": 30,
            "punctual": 40,
            "profile": 50,
            "referral": 300,
            "review": 60,
            "quiz": 40,
            "aftercare": 50,
            "challenge": 80,
            "off_peak": 20,
        }
        for event, coins in coin_defaults.items():
            CoinRule.objects.update_or_create(event=event, defaults={"coins": coins, "daily_limit": 1, "active": True})

        service = Service.objects.filter(active=True).first()
        if service:
            template, _ = AftercareTemplate.objects.update_or_create(service=service, version="1.0", defaults={"title": f"Nachsorge – {service.name}", "introduction": "Bitte verwenden Sie ausschließlich die von A+ Esthetic für Ihren Termin freigegebenen Hinweise.", "approved_by": "Fachliche Freigabe erforderlich", "active": True})
            tasks = [
                ("Freigegebene Hinweise lesen", "Bitte lesen Sie die bereitgestellten Informationen vollständig.", "do", 0, False),
                ("Bei unerwarteten Beschwerden A+ kontaktieren", "Nutzen Sie den sicheren Kontaktkanal; die App stellt keine Diagnose.", "contact", 4, True),
                ("Follow-up Rückmeldung", "Teilen Sie A+ Esthetic Ihre organisatorische Rückmeldung mit.", "do", 48, False),
            ]
            for order, (title, description, task_type, offset, warning) in enumerate(tasks):
                AftercareTask.objects.update_or_create(template=template, title=title, defaults={"description": description, "task_type": task_type, "offset_hours": offset, "warning_sign": warning, "sort_order": order * 10})

        articles = [
            ("Mitgliedschaft verstehen", "membership", "A+ Membership", "Coins, Credits und Gift Cards werden ausschließlich von A+ Esthetic ausgegeben und sind von ärztlicher Vergütung getrennt."),
            ("Sichere Nutzung des Beauty Passport", "process", "Beauty Passport", "Im Beauty Passport sehen Sie nur die für Sie freigegebenen Informationen. Interne medizinische Dokumentation bleibt getrennt."),
            ("Was der Wissensassistent darf", "safety", "AI Sicherheit", "Der Assistent erklärt freigegebene allgemeine Informationen. Diagnose, Dosierung, Eignungsprüfung und individuelle Behandlungsempfehlung sind ausgeschlossen."),
        ]
        manager = User.objects.filter(is_superuser=True).first()
        for slug, category, title, body in articles:
            KnowledgeArticle.objects.update_or_create(slug=slug, defaults={"title": title, "category": category, "summary": body, "body": body, "approved": True, "approved_by": manager, "approved_at": timezone.now(), "active": True})

        category, _ = ShopCategory.objects.update_or_create(slug="pflege", defaults={"name": "Pflegeprodukte", "active": True, "sort_order": 10})
        products = [
            ("a-plus-pflege-set", "A+ Pflege-Set", 4900, 20),
            ("a-plus-sample-box", "A+ Sample Box", 1900, 50),
        ]
        for slug, name, price, stock in products:
            ShopProduct.objects.update_or_create(slug=slug, defaults={"category": category, "name": name, "description": "Von A+ Esthetic angebotenes Pflegeprodukt.", "price_cents": price, "stock": stock, "active": True, "click_collect": True, "shipping": True})

        now = timezone.now()
        Challenge.objects.update_or_create(title="7 Tage Pflegeroutine", defaults={"description": "Dokumentieren Sie sieben Tage lang Ihre persönliche Pflegeroutine.", "challenge_type": "care", "target_count": 7, "reward_coins": 100, "starts_at": now - timedelta(days=1), "ends_at": now + timedelta(days=60), "active": True})
        Challenge.objects.update_or_create(title="A+ Wissen entdecken", defaults={"description": "Lesen Sie freigegebene Lerninhalte.", "challenge_type": "learning", "target_count": 3, "reward_coins": 60, "starts_at": now - timedelta(days=1), "ends_at": now + timedelta(days=60), "active": True})

        badge, _ = Badge.objects.update_or_create(slug="beauty-starter", defaults={"name": "Beauty Starter", "description": "Erste Schritte im A+ Beauty Club", "icon": "✦", "active": True})
        quiz, _ = Quiz.objects.update_or_create(title="A+ Datenschutz Quiz", defaults={"description": "Kennen Sie Ihre Datenschutzoptionen?", "reward_coins": 40, "active": True})
        QuizQuestion.objects.update_or_create(quiz=quiz, question="Wer gibt A+ Coins und Gift Cards aus?", defaults={"options": ["Der Arzt", "A+ Esthetic", "Doctolib"], "correct_index": 1, "explanation": "Alle Club-Vorteile werden ausschließlich durch A+ Esthetic ausgegeben.", "sort_order": 10})

        FAQ.objects.update_or_create(question="Ersetzt die App eine ärztliche Beratung?", defaults={"answer": "Nein. Die App organisiert Termine und stellt freigegebene allgemeine Informationen bereit.", "category": "Sicherheit", "active": True, "sort_order": 10})
        FAQ.objects.update_or_create(question="Sind A+ Coins mit einer Arztvergütung verbunden?", defaults={"answer": "Nein. Coins, Credits, Gift Cards und Rewards werden ausschließlich von A+ Esthetic verwaltet.", "category": "Membership", "active": True, "sort_order": 20})

        Offer.objects.update_or_create(title="Double Coin – Lerninhalte", defaults={"description": "Doppelte A+ Coins für ausgewählte Lernaktivitäten.", "audience": "all", "offer_type": "membership", "starts_at": now - timedelta(days=1), "ends_at": now + timedelta(days=30), "coin_bonus_multiplier": 2, "active": True})
        BeautyEvent.objects.update_or_create(title="A+ Member Information Night", defaults={"description": "Ein Informationsabend zu A+ Services, App-Funktionen und Datenschutz.", "starts_at": now + timedelta(days=20), "ends_at": now + timedelta(days=20, hours=2), "capacity": 30, "location": "A+ Esthetic", "active": True})
        ContentArticle.objects.update_or_create(slug="a-plus-app-datenschutz", defaults={"title": "Ihre Daten in der A+ App", "content_type": "article", "summary": "Ein Überblick über Einwilligungen, Export und Löschanfragen.", "body": "Sie können Einwilligungen verwalten, eine Datenkopie erstellen und eine Kontolöschung anfordern. Gesetzliche Aufbewahrungspflichten bleiben unberührt.", "category": "Datenschutz", "approved": True, "published_at": now, "active": True})

        self.stdout.write(self.style.SUCCESS("Vollständiger Funktionskatalog wurde angelegt."))
