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


class MobilePasswordResetView(AestheticPasswordResetView):
    """Use the same allauth token, delivery, account policy and rate limit."""

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        import json

        from django.http import JsonResponse

        if request.content_type != 'application/json' or len(request.body) > 2048:
            return JsonResponse({'ok': False, 'error': 'invalid_request'}, status=400)
        try:
            body = json.loads(request.body)
            email = body['email']
            if not isinstance(email, str):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'invalid_request'}, status=400)
        form = self.get_form_class()(data={'email': email[:320]})
        if not form.is_valid():
            return JsonResponse({'ok': False, 'error': 'invalid_email'}, status=400)
        response = self.form_valid(form)
        if response.status_code == 429:
            return JsonResponse({'ok': False, 'error': 'rate_limited'}, status=429)
        if form.errors:
            return JsonResponse({'ok': False, 'error': 'delivery_unavailable'}, status=503)
        return JsonResponse({'ok': True})
