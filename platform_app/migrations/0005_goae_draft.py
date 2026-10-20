from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("platform_app", "0004_office_invoicing")]
    operations = [
        migrations.AddField(model_name="invoice", name="billing_method",
            field=models.CharField(max_length=12,default="standard",
                choices=[("standard","Standard"),("goae","GOÄ")])),
        migrations.AddField(model_name="invoiceitem", name="goae_number",
            field=models.CharField(max_length=24,blank=True)),
        migrations.AddField(model_name="invoiceitem", name="goae_factor",
            field=models.DecimalField(max_digits=4,decimal_places=2,blank=True,null=True)),
        migrations.AddField(model_name="invoiceitem", name="goae_base_cents",
            field=models.PositiveIntegerField(blank=True,null=True)),
        migrations.AddField(model_name="invoiceitem", name="goae_justification",
            field=models.TextField(blank=True)),
    ]
