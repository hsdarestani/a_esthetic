from django.db import migrations


class Migration(migrations.Migration):
    # Preserve both historical dependencies. The deployments have separate
    # recorded migration histories; never add a dependency to an applied node.
    dependencies = [
        ('platform_app', '0008_goae_draft_request'),
        ('platform_app', '0009_public_intake_forms'),
    ]
    operations = []
