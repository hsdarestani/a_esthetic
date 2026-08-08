from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render

from .models import AuditLog, UserProfile


def _legal(request, page, title, subtitle=''):
    return render(request, 'legal.html', {
        'page': page,
        'legal_title': title,
        'legal_subtitle': subtitle,
    })


def datenschutz(request):
    return _legal(
        request,
        'datenschutz',
        'Datenschutzerklärung',
        'Informationen zur Datenverarbeitung in der A+ Esthetic App',
    )


def privacy_choices(request):
    return _legal(
        request,
        'privacy_choices',
        'Datenschutz-Einstellungen',
        'Ihre Einwilligungen, Auskunfts- und Löschmöglichkeiten',
    )


def impressum(request):
    return _legal(request, 'impressum', 'Impressum', 'Anbieterkennzeichnung gemäß § 5 DDG')


def support(request):
    return _legal(request, 'support', 'Support', 'Hilfe und Kontakt zur A+ Esthetic App')


def medical_notice(request):
    return _legal(
        request,
        'medical_notice',
        'Medizinische Hinweise',
        'Wichtige Grenzen der App und Hinweise zu medizinischen Entscheidungen',
    )


def terms(request):
    return _legal(
        request,
        'terms',
        'Nutzungsbedingungen',
        'Bedingungen für die Nutzung der A+ Esthetic App',
    )


def account_deletion(request):
    error = ''
    submitted = False
    requested_email = ''

    if request.user.is_authenticated:
        requested_email = request.user.email or request.user.username

    if request.method == 'POST':
        actor = request.user if request.user.is_authenticated else None
        requested_email = requested_email if actor else request.POST.get('email', '').strip()

        if not actor:
            try:
                validate_email(requested_email)
            except ValidationError:
                error = 'Bitte geben Sie die E-Mail-Adresse ein, die zu Ihrem A+ Esthetic Konto gehört.'

        if not error:
            AuditLog.objects.create(
                actor=actor,
                action='Kontolöschung angefordert',
                entity_type='UserAccount',
                entity_id=str(actor.pk) if actor else '',
                metadata={
                    'requested_email': requested_email,
                    'source': 'in_app' if actor else 'public_web',
                    'status': 'open',
                },
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            if actor:
                UserProfile.objects.filter(user=actor).update(marketing_consent=False)

            submitted = True

    return render(request, 'legal.html', {
        'page': 'account_deletion',
        'legal_title': 'Konto & Daten löschen',
        'legal_subtitle': 'Löschung Ihres App-Kontos und der zugehörigen Daten anfordern',
        'deletion_error': error,
        'deletion_submitted': submitted,
        'requested_email': requested_email,
    })
