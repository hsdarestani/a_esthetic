import os
from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from platform_app.models import (
    Campaign,
    FeatureModule,
    GiftCard,
    IntegrationConfig,
    MemberAccount,
    MemberPackage,
    MembershipTier,
    Message,
    PackageDefinition,
    Referral,
    Reminder,
    Reward,
    Service,
    StaffMember,
    Thread,
    UserProfile,
    WalletAccount,
    WalletTransaction,
    WorkingHour,
)


class Command(BaseCommand):
    help = 'Initialisiert A+ Esthetic als Customer Club mit sicheren Demo-Daten.'

    def handle(self, *args, **opts):
        modules = [
            ('membership', 'Mitgliedskarte & Membership', 'Digitale Mitgliedskarte, Stufen und QR Check-in', 10),
            ('booking', 'Termine', 'Organisatorische Terminanfragen und Warteliste', 20),
            ('wallet', 'A+ Wallet & Coins', 'A+ Credit, Coins, Rewards und Transaktionshistorie', 30),
            ('packages', 'Pakete', 'Paketstände und Ablaufdaten', 40),
            ('reminders', 'Erinnerungen', 'Club- und Termin-Erinnerungen', 50),
            ('chat', 'Nachrichten', 'Organisatorische Kommunikation mit A+ Esthetic', 60),
            ('giftcards', 'Gift Cards', 'Von A+ Esthetic ausgegebene Geschenkguthaben', 70),
            ('referrals', 'Freunde empfehlen', 'Empfehlungscodes mit Club-Belohnung nach verifiziertem Besuch', 80),
            ('campaigns', 'Angebote & Kampagnen', 'A+ Customer-Club Kampagnen', 90),
            ('integrations', 'Login-Integrationen', 'Apple und Google Login, falls später aktiviert', 100),
        ]
        active_keys = {item[0] for item in modules}
        for key, name, desc, order in modules:
            FeatureModule.objects.update_or_create(
                key=key,
                defaults={
                    'name_de': name,
                    'description_de': desc,
                    'sort_order': order,
                    'enabled': True,
                    'customer_visible': key not in {'campaigns', 'integrations'},
                },
            )

        # Legacy product ideas remain disabled if they already exist in an older database.
        for legacy_key in ['passport', 'before_after', 'followup', 'ai']:
            FeatureModule.objects.filter(key=legacy_key).update(enabled=False, customer_visible=False)

        tiers = []
        for name, slug, fee, mult, prio in [
            ('A+ Member', 'member', 0, 1, 10),
            ('A+ Glow', 'glow', 1900, 1.2, 20),
            ('A+ Signature', 'signature', 4900, 1.5, 30),
            ('A+ Black', 'black', 9900, 2, 40),
        ]:
            tier, _ = MembershipTier.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'monthly_fee_cents': fee,
                    'coin_multiplier': mult,
                    'priority': prio,
                    'active': True,
                },
            )
            tiers.append(tier)

        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        admin, _ = User.objects.get_or_create(
            username=admin_username,
            defaults={'email': 'admin@a-esthetic.de', 'is_staff': True, 'is_superuser': True},
        )
        admin.is_staff = True
        admin.is_superuser = True
        if admin_password:
            admin.set_password(admin_password)
        admin.save()
        UserProfile.objects.update_or_create(
            user=admin,
            defaults={'role': 'admin', 'health_data_consent': False},
        )

        demo_email = 'demo@a-esthetic.de'
        demo_password = os.environ.get('DEMO_PASSWORD', 'Aplus-Demo-2026!')
        demo, _ = User.objects.get_or_create(
            username=demo_email,
            defaults={'email': demo_email, 'first_name': 'Sophie', 'last_name': 'Muster'},
        )
        demo.email = demo_email
        demo.set_password(demo_password)
        demo.save()
        UserProfile.objects.update_or_create(
            user=demo,
            defaults={
                'role': 'customer',
                'phone': '+49 170 0000000',
                'marketing_consent': True,
                'health_data_consent': False,
            },
        )

        MemberAccount.objects.update_or_create(
            user=demo,
            defaults={'tier': tiers[1], 'valid_until': timezone.localdate() + timedelta(days=365)},
        )
        wallet, _ = WalletAccount.objects.get_or_create(user=demo)
        if wallet.coin_balance == 0 and wallet.balance_cents == 0:
            wallet.coin_balance = 1840
            wallet.balance_cents = 6500
            wallet.save(update_fields=['coin_balance', 'balance_cents', 'updated_at'])

        if not WalletTransaction.objects.filter(user=demo).exists():
            WalletTransaction.objects.create(user=demo, kind='credit', direction='in', amount_cents=6500, description='A+ Startguthaben')
            WalletTransaction.objects.create(user=demo, kind='coin', direction='in', coin_amount=1840, description='A+ Customer Club Aktivitäten')

        rewards = [
            ('A+ Welcome Drink', 'Ein Getränk bei Ihrem nächsten Besuch.', 300, 30),
            ('Beauty Sample Set', 'Ausgewähltes A+ Sample Set.', 500, 20),
            ('Priority Booking Pass', 'Bevorzugte Bearbeitung einer Terminanfrage.', 1800, 10),
            ('A+ Event Einladung', 'Einladung zu einer ausgewählten A+ Veranstaltung.', 2500, 10),
        ]
        for name, description, cost, inventory in rewards:
            Reward.objects.update_or_create(
                name=name,
                defaults={
                    'description': description,
                    'coin_cost': cost,
                    'inventory': inventory,
                    'active': True,
                    'is_medical_service': False,
                },
            )

        package, _ = PackageDefinition.objects.update_or_create(
            name='A+ Club Paket',
            defaults={
                'description': 'Customer-Club Paket',
                'sessions': 6,
                'validity_days': 365,
                'active': True,
                'medical_service': False,
            },
        )
        MemberPackage.objects.update_or_create(
            user=demo,
            definition=package,
            defaults={'remaining_sessions': 4, 'expires_at': timezone.localdate() + timedelta(days=210), 'status': 'active'},
        )

        # Customer-facing booking catalog mirrors the real treatment areas offered by A+ Esthetic.
        # Medical entries are booking requests/consultations and stay pending until A+ Esthetic confirms them.
        service_definitions = [
            ('Ästhetische Erstberatung', 'aesthetische-erstberatung', 'consultation', 30, 10, 'Individuelle Beratung', True),
            ('Botox Beratung', 'botox-beratung', 'medical', 30, 10, 'ab 119 €', True),
            ('Hyaluron Beratung', 'hyaluron-beratung', 'medical', 30, 10, 'ab 200 €', True),
            ('Laser-Haarentfernung', 'laser-haarentfernung', 'nonmedical', 45, 10, 'je nach Areal', False),
            ('RF-Microneedling', 'rf-microneedling', 'nonmedical', 60, 15, 'Preis nach Region', False),
            ('PRP Beratung', 'prp-beratung', 'medical', 30, 10, 'Preis nach Beratung', True),
            ('Skinbooster Beratung', 'skinbooster-beratung', 'medical', 30, 10, 'Preis nach Beratung', True),
            ('Infusionstherapie', 'infusionstherapie', 'medical', 60, 10, 'ab 119 €', True),
            ('Injektionslipolyse Beratung', 'injektionslipolyse-beratung', 'medical', 30, 10, 'ab 149 €', True),
        ]
        services = []
        for name, slug, category, duration, buffer, price, medical in service_definitions:
            service, _ = Service.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'description': 'Terminanfrage über den A+ Customer Club. Die persönliche Beratung, Aufklärung und Bestätigung erfolgt durch A+ Esthetic.',
                    'category': category,
                    'duration_minutes': duration,
                    'buffer_minutes': buffer,
                    'price_label': price,
                    'active': True,
                    'bookable_in_app': True,
                    'requires_medical_confirmation': medical,
                },
            )
            services.append(service)

        # Retire generic/demo and legacy services without deleting historical appointments.
        Service.objects.exclude(pk__in=[item.pk for item in services]).update(bookable_in_app=False)

        staff, _ = StaffMember.objects.get_or_create(
            display_name='A+ Esthetic Team',
            defaults={'role': 'specialist', 'active': True},
        )
        staff.role = 'specialist'
        staff.active = True
        staff.save(update_fields=['role', 'active'])
        staff.services.set(services)
        for day in range(5):
            WorkingHour.objects.update_or_create(
                staff=staff,
                weekday=day,
                start_time=time(10, 0),
                defaults={'end_time': time(18, 0), 'active': True},
            )

        Reminder.objects.update_or_create(
            user=demo,
            title='A+ Termin-Erinnerung',
            defaults={
                'body': 'Ihr nächster A+ Termin steht an.',
                'scheduled_for': timezone.now() + timedelta(days=7),
                'channel': 'inapp',
                'status': 'scheduled',
            },
        )

        thread, _ = Thread.objects.get_or_create(user=demo, subject='Willkommen bei A+ Esthetic')
        Message.objects.get_or_create(
            thread=thread,
            sender=admin,
            body='Willkommen im A+ Customer Club. Hier helfen wir bei Membership, Terminen, Rewards und organisatorischen Fragen.',
        )

        for provider in ['google', 'apple']:
            IntegrationConfig.objects.update_or_create(
                provider=provider,
                defaults={
                    'enabled': False,
                    'sync_enabled': False,
                    'status': 'Nicht konfiguriert',
                    'credential_reference': f'{provider.upper()}_CREDENTIALS',
                },
            )
        IntegrationConfig.objects.filter(provider__in=['doctolib', 'simplybook']).update(enabled=False, sync_enabled=False, status='Nicht Teil der Customer-Club-App')

        Referral.objects.get_or_create(
            referrer=demo,
            code='APLUS-SOPHIE',
            defaults={'status': 'invited', 'reward_coins': 300},
        )
        Campaign.objects.get_or_create(
            name='A+ Customer Club Willkommen',
            defaults={
                'audience': 'all',
                'message': 'Willkommen im A+ Customer Club.',
                'starts_at': timezone.now() - timedelta(days=1),
                'ends_at': timezone.now() + timedelta(days=90),
                'active': True,
            },
        )
        GiftCard.objects.get_or_create(
            code='APLUS-DEMO-100',
            defaults={
                'purchaser': demo,
                'recipient_email': demo.email,
                'initial_cents': 10000,
                'balance_cents': 10000,
                'status': 'active',
                'expires_at': timezone.localdate() + timedelta(days=365),
            },
        )

        self.stdout.write(self.style.SUCCESS('A+ Esthetic Customer Club initialisiert.'))
