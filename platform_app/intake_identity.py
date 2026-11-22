"""Candidate-only duplicate detection for the existing unauthenticated iPad form."""
import hashlib
import json
import re
import unicodedata
from datetime import date

from django.contrib.auth.models import User
from django.utils import timezone

from .models import OfficeIntakeReview, UserProfile


def normalize_name(value):
    return ' '.join(unicodedata.normalize('NFC', str(value or '')).casefold().split())


def normalize_phone(value):
    digits = re.sub(r'[^0-9]', '', str(value or ''))
    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = '49' + digits[1:]
    return digits if 8 <= len(digits) <= 15 else ''


def fields(data):
    email = str(data.get('email') or '').strip().casefold()
    if '@' not in email or email.endswith('@invalid.local'):
        email = ''
    return (normalize_name(data.get('first_name')), normalize_name(data.get('last_name')),
            normalize_phone(data.get('phone')), email, str(data.get('date_of_birth') or ''))


def score(left, right):
    return sum(bool(a and b and a == b) for a, b in zip(fields(left), fields(right)))


def user_data(user):
    profile = UserProfile.objects.filter(user=user).first()
    return {'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email,
            'phone': profile.phone if profile else '',
            'date_of_birth': profile.date_of_birth.isoformat() if profile and profile.date_of_birth else ''}


def potential_matches(data):
    incoming = fields(data)
    found = []
    for user in User.objects.select_related('profile').order_by('pk').iterator(chunk_size=200):
        profile = getattr(user, 'profile', None)
        existing = {'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email,
                    'phone': profile.phone if profile else '',
                    'date_of_birth': profile.date_of_birth.isoformat() if profile and profile.date_of_birth else ''}
        prior = fields(existing)
        if score(data, existing) >= 3 or any(incoming[i] and incoming[i] == prior[i] for i in (2, 3)):
            found.append(user.pk)
    return found


def birth_date(value):
    if not value:
        return None
    result = date.fromisoformat(value)
    if not date(1900, 1, 1) <= result <= timezone.localdate():
        raise ValueError('invalid_date_of_birth')
    return result


def queue_review(data, session=None):
    digest = hashlib.sha256(json.dumps(
        [session.pk if session else None, data], sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()
    return OfficeIntakeReview.objects.get_or_create(digest=digest, defaults={'payload': data, 'session': session})[0]
