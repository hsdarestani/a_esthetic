from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('platform_app', '0007_office_intake_review')]
    operations = [
        migrations.AddField(model_name='invoice', name='native_draft_data', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='invoice', name='native_revision', field=models.PositiveIntegerField(default=1)),
    ]
