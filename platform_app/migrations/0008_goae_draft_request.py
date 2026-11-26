from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("platform_app", "0007_goae_agreement_precision")]
    operations = [
        migrations.AddField(
            model_name="invoice", name="draft_request_id",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="invoice", name="draft_request_digest",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
