from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("p0_app", "0008_dashboard_banner_cover_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardHeroImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variant", models.CharField(
                    choices=[
                        ("frau", "Damen (Anrede Frau)"),
                        ("herr", "Herren (Anrede Herr)"),
                        ("default", "Standard (Divers / keine Anrede)"),
                    ],
                    max_length=10,
                    unique=True,
                )),
                ("image", models.ImageField(upload_to="dashboard_heroes/%Y/%m/")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Startseitenbild",
                "verbose_name_plural": "Startseitenbilder",
                "ordering": ["variant"],
            },
        ),
    ]
