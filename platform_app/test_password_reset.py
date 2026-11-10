from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from allauth.account.models import EmailAddress


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED=False,
)
class PasswordResetExperienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reset-customer", email="customer@example.com",
            password="StrongPassword12345!",
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email,
            verified=True, primary=True,
        )

    def test_reset_sends_real_link_and_shows_branded_confirmation(self):
        response = self.client.post(
            reverse("account_reset_password"),
            {"email": self.user.email},
        )
        self.assertRedirects(response, reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/key/", mail.outbox[0].body)
        response = self.client.get(reverse("account_reset_password_done"))
        self.assertContains(response, "Prüfen Sie Ihre E-Mails")
        self.assertContains(response, "A+ ESTHETIC")

    def test_unknown_address_does_not_reveal_account_status(self):
        response = self.client.post(
            reverse("account_reset_password"),
            {"email": "missing@example.com"},
        )
        self.assertRedirects(response, reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.strato.de",
        EMAIL_HOST_PASSWORD="",
    )
    def test_missing_smtp_credential_is_not_reported_as_success(self):
        response = self.client.post(
            reverse("account_reset_password"),
            {"email": self.user.email},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-Mail-Versand ist momentan nicht verfügbar")
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_reset_link_is_branded(self):
        url = reverse(
            "account_reset_password_from_key",
            kwargs={"uidb36": "1", "key": "invalid-token"},
        )
        response = self.client.get(url)
        self.assertContains(response, "Link nicht mehr gültig")
        self.assertContains(response, "A+ ESTHETIC")
