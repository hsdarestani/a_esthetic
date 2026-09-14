from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("p0_app", "0006_dashboard_banner")]
    operations = [
        migrations.AddField(
            model_name="dashboardbanner",
            name="cover_image",
            field=models.FileField(blank=True, upload_to="dashboard_banners/%Y/%m/"),
        ),
    ]
