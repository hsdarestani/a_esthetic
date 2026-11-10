"""Branded password reset with explicit delivery failure handling."""
import logging
import smtplib

from django.conf import settings
from allauth.account.views import PasswordResetView

logger = logging.getLogger(__name__)
UNAVAILABLE_MESSAGE = (
    "Der E-Mail-Versand ist momentan nicht verfügbar. "
    "Bitte versuchen Sie es später erneut oder kontaktieren Sie den Support."
)


class AestheticPasswordResetView(PasswordResetView):
    """Never claim an email was sent when production has no email transport."""

    def form_valid(self, form):
        backend = settings.EMAIL_BACKEND
        # Django console/dummy backends never deliver messages to real inboxes.
        if backend.endswith(("console.EmailBackend", "dummy.EmailBackend")):
            logger.error("Password reset email delivery disabled: non-delivering backend")
            form.add_error(None, UNAVAILABLE_MESSAGE)
            return self.form_invalid(form)

        # The STRATO relay requires SMTP authentication; a missing password
        # cannot successfully deliver recovery messages.
        if (
            backend.endswith("smtp.EmailBackend")
            and settings.EMAIL_HOST.lower() == "smtp.strato.de"
            and (not settings.EMAIL_HOST_PASSWORD or not settings.EMAIL_HOST_USER)
        ):
            logger.error("Password reset SMTP credentials are not configured")
            form.add_error(None, UNAVAILABLE_MESSAGE)
            return self.form_invalid(form)

        try:
            return super().form_valid(form)
        except (OSError, smtplib.SMTPException):
            logger.exception("Password reset SMTP delivery failed")
            form.add_error(None, UNAVAILABLE_MESSAGE)
            return self.form_invalid(form)
