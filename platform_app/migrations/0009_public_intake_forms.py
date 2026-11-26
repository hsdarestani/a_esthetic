import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('platform_app','0008_goae_draft_revision'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    # Equivalent schema already provided by the deployed web intake migration.
    operations = []
