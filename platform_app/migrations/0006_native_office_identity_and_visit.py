from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('platform_app', '0007_goae_agreement_precision'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='OfficePatientLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_customer_id', models.PositiveBigIntegerField(unique=True)),
                ('verified_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                    related_name='office_patient_link', to=settings.AUTH_USER_MODEL)),
                ('verified_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name='verified_office_links', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(model_name='invoice', name='book_appointment_public_id',
                            field=models.UUIDField(blank=True, null=True, db_index=True)),
        migrations.AddField(model_name='invoice', name='book_original_service_date',
                            field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='invoice', name='service_date_correction',
                            field=models.CharField(blank=True, default='', max_length=500)),
        migrations.AddField(model_name='invoice', name='native_request_id',
                            field=models.UUIDField(blank=True, null=True, unique=True)),
        migrations.AddField(model_name='invoice', name='native_request_fingerprint',
                            field=models.CharField(blank=True, default='', max_length=64)),
    ]
