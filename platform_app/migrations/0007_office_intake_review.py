from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('platform_app', '0006_native_office_identity_and_visit'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='OfficeIntakeReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload', models.JSONField(default=dict)),
                ('digest', models.CharField(max_length=64, unique=True)),
                ('status', models.CharField(choices=[('pending','Offen'),('approved','Bestätigt'),('rejected','Abgelehnt')],
                                            db_index=True, default='pending', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                              to='platform_app.checkinsession')),
                ('matched_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name='office_intake_reviews', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name='reviewed_office_intakes', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
