from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('platform_app', '0006_public_intake_forms')]
    operations = [
        migrations.AlterField(
            model_name='invoiceitem', name='goae_factor',
            field=models.DecimalField(max_digits=7, decimal_places=4, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoiceitem', name='goae_agreement_document',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='goae_agreed_items', to='platform_app.securedocument'),
        ),
        migrations.AddField(
            model_name='invoiceitem', name='goae_agreement_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
