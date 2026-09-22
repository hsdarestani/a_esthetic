from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("platform_app", "0002_dedicated_app_admin"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="salutation",
            field=models.CharField(
                blank=True,
                choices=[("herr","Herr"),("frau","Frau"),("divers","Divers")],
                max_length=12,
            ),
        ),
        migrations.AddField(model_name="userprofile", name="onboarding_required", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="userprofile", name="auth_provider", field=models.CharField(default="password", max_length=20)),
        migrations.AddField(model_name="userprofile", name="email_verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="userprofile", name="phone_verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="userprofile", name="profile_completed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="userprofile", name="referral_code_used", field=models.CharField(blank=True, max_length=32)),
        migrations.AddField(
            model_name="referral",
            name="referred_user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="referral_origin",
                to="auth.user",
            ),
        ),
        migrations.AddField(model_name="referral", name="registered_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name="AccountVerification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("email","E-Mail"),("sms","SMS")], max_length=12)),
                ("code_digest", models.CharField(max_length=160)),
                ("sent_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField()),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="verification_challenges", to="auth.user")),
            ],
        ),
        migrations.AddConstraint(
            model_name="accountverification",
            constraint=models.UniqueConstraint(
                fields=("user","channel"),
                name="unique_user_verification_channel",
            ),
        ),
    ]
