import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('platform_app','0008_goae_draft_revision'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='OfficeIntakeSubmission',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('public_id',models.UUIDField(default=uuid.uuid4,editable=False,unique=True)),
                ('identity',models.JSONField(default=dict)),
                ('answers',models.JSONField(default=dict)),
                ('signature_png',models.TextField()),
                ('consent_version',models.CharField(default='intake-2026-11',max_length=40)),
                ('sync_status',models.CharField(choices=[('pending','Übertragung offen'),('linked','Zugeordnet'),('review','Identität prüfen'),('error','Übertragung fehlgeschlagen')],db_index=True,default='pending',max_length=12)),
                ('book_customer_id',models.PositiveBigIntegerField(blank=True,null=True)),
                ('book_record_id',models.CharField(blank=True,max_length=36)),
                ('created_at',models.DateTimeField(auto_now_add=True,db_index=True)),
                ('user',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='office_intake_submissions',to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering':['-created_at'],'verbose_name':'Digitaler Aufnahmebogen','verbose_name_plural':'Digitale Aufnahmebögen'},
        ),
    ]