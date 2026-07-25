import secrets
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class FeatureModule(models.Model):
    key=models.SlugField(unique=True,max_length=60); name_de=models.CharField(max_length=120); description_de=models.TextField(blank=True); enabled=models.BooleanField(default=True); customer_visible=models.BooleanField(default=True); sort_order=models.PositiveIntegerField(default=100); updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['sort_order','name_de']; verbose_name='Modul'; verbose_name_plural='Module'
    def __str__(self): return self.name_de
class UserProfile(models.Model):
    ROLE_CHOICES=[('customer','Kundin/Kunde'),('reception','Empfang'),('specialist','Behandler/in'),('manager','Management'),('admin','Administrator/in')]
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile'); role=models.CharField(max_length=20,choices=ROLE_CHOICES,default='customer'); phone=models.CharField(max_length=40,blank=True); preferred_language=models.CharField(max_length=10,default='de'); marketing_consent=models.BooleanField(default=False); health_data_consent=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user.username} – {self.get_role_display()}'
class AuditLog(models.Model):
    actor=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL); action=models.CharField(max_length=120); entity_type=models.CharField(max_length=100,blank=True); entity_id=models.CharField(max_length=100,blank=True); metadata=models.JSONField(default=dict,blank=True); ip_address=models.GenericIPAddressField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']; verbose_name='Audit-Eintrag'; verbose_name_plural='Audit-Protokoll'
    def __str__(self): return f'{self.created_at:%d.%m.%Y %H:%M} – {self.action}'
class MembershipTier(models.Model):
    name=models.CharField(max_length=80); slug=models.SlugField(unique=True); description=models.TextField(blank=True); monthly_fee_cents=models.PositiveIntegerField(default=0); coin_multiplier=models.DecimalField(max_digits=4,decimal_places=2,default=1); priority=models.PositiveIntegerField(default=10); active=models.BooleanField(default=True)
    class Meta: ordering=['priority']; verbose_name='Mitgliedsstufe'; verbose_name_plural='Mitgliedsstufen'
    def __str__(self): return self.name
class MemberAccount(models.Model):
    STATUS=[('active','Aktiv'),('paused','Pausiert'),('expired','Abgelaufen')]
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='member_account'); member_number=models.CharField(max_length=24,unique=True,editable=False); tier=models.ForeignKey(MembershipTier,null=True,on_delete=models.SET_NULL); status=models.CharField(max_length=20,choices=STATUS,default='active'); valid_until=models.DateField(null=True,blank=True); qr_token=models.CharField(max_length=64,unique=True,editable=False); joined_at=models.DateTimeField(auto_now_add=True)
    def save(self,*args,**kwargs):
        if not self.member_number: self.member_number='AP-'+secrets.token_hex(5).upper()
        if not self.qr_token: self.qr_token=secrets.token_urlsafe(32)
        super().save(*args,**kwargs)
    def __str__(self): return self.member_number
class WalletAccount(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='wallet'); balance_cents=models.IntegerField(default=0); coin_balance=models.IntegerField(default=0); updated_at=models.DateTimeField(auto_now=True)
    def __str__(self): return f'{self.user.username}: {self.balance_cents/100:.2f} € / {self.coin_balance} Coins'
class WalletTransaction(models.Model):
    KIND=[('credit','A+ Credit'),('coin','A+ Coins'),('gift','Geschenkguthaben'),('package','Paket')]; DIRECTION=[('in','Gutschrift'),('out','Einlösung')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='wallet_transactions'); kind=models.CharField(max_length=20,choices=KIND); direction=models.CharField(max_length=10,choices=DIRECTION); amount_cents=models.IntegerField(default=0); coin_amount=models.IntegerField(default=0); description=models.CharField(max_length=200); reference=models.CharField(max_length=80,blank=True); issuer=models.CharField(max_length=80,default='A+ Esthetic',editable=False); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']; verbose_name='Wallet-Transaktion'; verbose_name_plural='Wallet-Transaktionen'
class Reward(models.Model):
    name=models.CharField(max_length=140); description=models.TextField(blank=True); coin_cost=models.PositiveIntegerField(); active=models.BooleanField(default=True); inventory=models.PositiveIntegerField(null=True,blank=True); issuer=models.CharField(max_length=80,default='A+ Esthetic',editable=False); is_medical_service=models.BooleanField(default=False,help_text='Muss aus rechtlichen Gründen deaktiviert bleiben.')
    def clean(self):
        if self.is_medical_service: raise ValidationError('Medizinische Leistungen dürfen nicht als A+ Reward ausgegeben werden.')
    def __str__(self): return self.name
class GiftCard(models.Model):
    STATUS=[('active','Aktiv'),('redeemed','Eingelöst'),('expired','Abgelaufen'),('blocked','Gesperrt')]
    code=models.CharField(max_length=32,unique=True); purchaser=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='purchased_giftcards'); recipient_email=models.EmailField(blank=True); initial_cents=models.PositiveIntegerField(); balance_cents=models.PositiveIntegerField(); status=models.CharField(max_length=20,choices=STATUS,default='active'); expires_at=models.DateField(null=True,blank=True); issuer=models.CharField(max_length=80,default='A+ Esthetic',editable=False); created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.code
class PackageDefinition(models.Model):
    name=models.CharField(max_length=140); description=models.TextField(blank=True); sessions=models.PositiveIntegerField(default=1); validity_days=models.PositiveIntegerField(default=365); active=models.BooleanField(default=True); medical_service=models.BooleanField(default=False,help_text='Nur organisatorisch; keine Arztvergütung oder Provision wird verarbeitet.'); issuer=models.CharField(max_length=80,default='A+ Esthetic',editable=False)
    def __str__(self): return self.name
class Referral(models.Model):
    STATUS=[('invited','Eingeladen'),('registered','Registriert'),('visited','Erster Besuch'),('rewarded','Belohnt')]
    referrer=models.ForeignKey(User,on_delete=models.CASCADE,related_name='referrals'); code=models.CharField(max_length=32,unique=True); invited_email=models.EmailField(blank=True); status=models.CharField(max_length=20,choices=STATUS,default='invited'); reward_coins=models.PositiveIntegerField(default=0); created_at=models.DateTimeField(auto_now_add=True); rewarded_at=models.DateTimeField(null=True,blank=True)
    def __str__(self): return f'{self.code} – {self.get_status_display()}'
class Campaign(models.Model):
    AUDIENCE=[('all','Alle Mitglieder'),('inactive','Inaktive Mitglieder'),('vip','Signature / Black'),('birthday','Geburtstag'),('package_expiry','Paket läuft ab')]
    name=models.CharField(max_length=160); audience=models.CharField(max_length=30,choices=AUDIENCE,default='all'); message=models.TextField(); starts_at=models.DateTimeField(); ends_at=models.DateTimeField(); active=models.BooleanField(default=True); issuer=models.CharField(max_length=80,default='A+ Esthetic',editable=False); created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name
class MemberPackage(models.Model):
    STATUS=[('active','Aktiv'),('used','Aufgebraucht'),('expired','Abgelaufen')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='packages'); definition=models.ForeignKey(PackageDefinition,on_delete=models.PROTECT); remaining_sessions=models.PositiveIntegerField(); expires_at=models.DateField(); status=models.CharField(max_length=20,choices=STATUS,default='active'); created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user.username} – {self.definition.name}'
class Service(models.Model):
    CATEGORY=[('medical','Medizinische Ästhetik'),('nonmedical','Kosmetische Leistung'),('consultation','Beratung')]
    name=models.CharField(max_length=140); slug=models.SlugField(unique=True); description=models.TextField(blank=True); category=models.CharField(max_length=20,choices=CATEGORY); duration_minutes=models.PositiveIntegerField(default=30); buffer_minutes=models.PositiveIntegerField(default=10); price_label=models.CharField(max_length=80,blank=True); active=models.BooleanField(default=True); bookable_in_app=models.BooleanField(default=True); requires_medical_confirmation=models.BooleanField(default=False); doctor_revenue_tracked=models.BooleanField(default=False,editable=False)
    def __str__(self): return self.name
class StaffMember(models.Model):
    ROLE=[('doctor','Arzt/Ärztin'),('specialist','Spezialist/in'),('reception','Empfang')]
    user=models.OneToOneField(User,null=True,blank=True,on_delete=models.SET_NULL); display_name=models.CharField(max_length=120); role=models.CharField(max_length=20,choices=ROLE); services=models.ManyToManyField(Service,blank=True); active=models.BooleanField(default=True)
    def __str__(self): return self.display_name
class WorkingHour(models.Model):
    staff=models.ForeignKey(StaffMember,on_delete=models.CASCADE,related_name='working_hours'); weekday=models.PositiveSmallIntegerField(choices=[(0,'Montag'),(1,'Dienstag'),(2,'Mittwoch'),(3,'Donnerstag'),(4,'Freitag'),(5,'Samstag'),(6,'Sonntag')]); start_time=models.TimeField(); end_time=models.TimeField(); active=models.BooleanField(default=True)
    class Meta: unique_together=[('staff','weekday','start_time')]
class BlockedPeriod(models.Model):
    staff=models.ForeignKey(StaffMember,on_delete=models.CASCADE,related_name='blocked_periods'); starts_at=models.DateTimeField(); ends_at=models.DateTimeField(); reason=models.CharField(max_length=160,blank=True)
    def clean(self):
        if self.ends_at<=self.starts_at: raise ValidationError('Ende muss nach Beginn liegen.')
class Appointment(models.Model):
    STATUS=[('requested','Angefragt'),('confirmed','Bestätigt'),('completed','Abgeschlossen'),('cancelled','Storniert'),('no_show','Nicht erschienen')]; SOURCE=[('app','A+ App'),('doctolib','Doctolib'),('simplybook','SimplyBook'),('phone','Telefon'),('admin','Verwaltung')]
    user=models.ForeignKey(User,on_delete=models.PROTECT,related_name='appointments'); service=models.ForeignKey(Service,on_delete=models.PROTECT); staff=models.ForeignKey(StaffMember,null=True,blank=True,on_delete=models.PROTECT); starts_at=models.DateTimeField(); ends_at=models.DateTimeField(); status=models.CharField(max_length=20,choices=STATUS,default='requested'); source=models.CharField(max_length=20,choices=SOURCE,default='app'); notes_customer=models.TextField(blank=True); consent_acknowledged=models.BooleanField(default=False); external_id=models.CharField(max_length=120,blank=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['starts_at']; indexes=[models.Index(fields=['starts_at','staff','status'])]
    def clean(self):
        if self.ends_at<=self.starts_at: raise ValidationError('Ende muss nach Beginn liegen.')
        if self.staff_id and self.status not in {'cancelled'}:
            conflict=Appointment.objects.filter(staff=self.staff,status__in=['requested','confirmed'],starts_at__lt=self.ends_at,ends_at__gt=self.starts_at).exclude(pk=self.pk)
            if conflict.exists(): raise ValidationError('Dieser Termin überschneidet sich mit einem bestehenden Termin.')
    def __str__(self): return f'{self.service} – {self.starts_at:%d.%m.%Y %H:%M}'
class WaitlistEntry(models.Model):
    STATUS=[('active','Aktiv'),('offered','Angeboten'),('booked','Gebucht'),('closed','Geschlossen')]
    user=models.ForeignKey(User,on_delete=models.CASCADE); service=models.ForeignKey(Service,on_delete=models.CASCADE); preferred_from=models.DateTimeField(); preferred_until=models.DateTimeField(); status=models.CharField(max_length=20,choices=STATUS,default='active'); created_at=models.DateTimeField(auto_now_add=True)
class BeautyPassportEntry(models.Model):
    TYPE=[('visit','Besuch'),('treatment','Behandlung'),('product','Produkt'),('note','Notiz'),('document','Dokument')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='passport_entries'); entry_type=models.CharField(max_length=20,choices=TYPE); title=models.CharField(max_length=160); occurred_on=models.DateField(); provider_name=models.CharField(max_length=160,default='A+ Esthetic'); notes=models.TextField(blank=True); metadata=models.JSONField(default=dict,blank=True); visible_to_customer=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-occurred_on','-created_at']
class ConsentTemplate(models.Model):
    key=models.SlugField(); title=models.CharField(max_length=160); text=models.TextField(); version=models.CharField(max_length=20); health_data=models.BooleanField(default=False); marketing=models.BooleanField(default=False); active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: unique_together=[('key','version')]
    def __str__(self): return f'{self.title} v{self.version}'
class ConsentRecord(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='consents'); template=models.ForeignKey(ConsentTemplate,on_delete=models.PROTECT); accepted=models.BooleanField(default=True); accepted_at=models.DateTimeField(auto_now_add=True); withdrawn_at=models.DateTimeField(null=True,blank=True); ip_address=models.GenericIPAddressField(null=True,blank=True); evidence=models.JSONField(default=dict,blank=True)
    class Meta: ordering=['-accepted_at']
class Reminder(models.Model):
    CHANNEL=[('push','Push'),('email','E-Mail'),('inapp','In-App')]; STATUS=[('scheduled','Geplant'),('sent','Gesendet'),('dismissed','Ausgeblendet'),('cancelled','Abgebrochen')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='reminders'); title=models.CharField(max_length=180); body=models.TextField(blank=True); scheduled_for=models.DateTimeField(); channel=models.CharField(max_length=20,choices=CHANNEL,default='inapp'); status=models.CharField(max_length=20,choices=STATUS,default='scheduled'); related_type=models.CharField(max_length=40,blank=True); related_id=models.CharField(max_length=60,blank=True); medical_language_safe=models.BooleanField(default=True,editable=False); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['scheduled_for']
class FollowUp(models.Model):
    STATUS=[('pending','Offen'),('answered','Beantwortet'),('review','Prüfung erforderlich'),('closed','Abgeschlossen')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='followups'); appointment=models.ForeignKey(Appointment,null=True,blank=True,on_delete=models.SET_NULL); title=models.CharField(max_length=180); questions=models.JSONField(default=list); due_at=models.DateTimeField(); status=models.CharField(max_length=20,choices=STATUS,default='pending'); customer_response=models.JSONField(default=dict,blank=True); staff_note=models.TextField(blank=True); requires_review=models.BooleanField(default=False)
class SecureDocument(models.Model):
    CATEGORY=[('medical','Medizinisch'),('consent','Einwilligung'),('invoice','Rechnung'),('photo','Foto'),('other','Sonstiges')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='secure_documents'); title=models.CharField(max_length=180); category=models.CharField(max_length=20,choices=CATEGORY); file=models.FileField(upload_to='documents/%Y/%m/'); marketing_consent=models.BooleanField(default=False); uploaded_by=models.ForeignKey(User,null=True,on_delete=models.SET_NULL,related_name='+'); created_at=models.DateTimeField(auto_now_add=True)
class Thread(models.Model):
    STATUS=[('open','Offen'),('closed','Geschlossen')]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='threads'); subject=models.CharField(max_length=180); status=models.CharField(max_length=20,choices=STATUS,default='open'); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-updated_at']
class Message(models.Model):
    thread=models.ForeignKey(Thread,on_delete=models.CASCADE,related_name='messages'); sender=models.ForeignKey(User,on_delete=models.PROTECT); body=models.TextField(); attachment=models.FileField(upload_to='messages/%Y/%m/',blank=True); is_internal=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['created_at']
class IntegrationConfig(models.Model):
    PROVIDERS=[('doctolib','Doctolib Partner API'),('simplybook','SimplyBook API'),('google','Google Sign-In'),('apple','Sign in with Apple')]
    provider=models.CharField(max_length=20,choices=PROVIDERS,unique=True); enabled=models.BooleanField(default=False); sync_enabled=models.BooleanField(default=False); credential_reference=models.CharField(max_length=180,blank=True,help_text='Nur Name der Server-Umgebungsvariable; keine Secrets hier speichern.'); status=models.CharField(max_length=80,default='Nicht konfiguriert'); last_sync_at=models.DateTimeField(null=True,blank=True); settings=models.JSONField(default=dict,blank=True)
    def __str__(self): return self.get_provider_display()
class SyncEvent(models.Model):
    integration=models.ForeignKey(IntegrationConfig,on_delete=models.CASCADE,related_name='events'); direction=models.CharField(max_length=20); entity_type=models.CharField(max_length=60); external_id=models.CharField(max_length=120,blank=True); status=models.CharField(max_length=30); message=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']
