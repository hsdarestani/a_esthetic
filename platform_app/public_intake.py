"""Private general Aufnahmebogen persistence and canonical Book synchronization.

The public route never responds with any patient identifier, medical record,
matching decision, signed PDF, or clinical history.
"""
import base64
import binascii
import json
import re
import unicodedata
import uuid

import requests
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.dateparse import parse_date
from django.utils import timezone

from .book_sync import _headers, _sync_token
from .models import (AuditLog, MemberAccount, OfficeIntakeLock,
                     OfficeIntakeSubmission, UserProfile)

BOOK_INTAKE_URL = 'https://book.a-esthetic.de/api/internal/patient-intake/ingest/'
ANSWER_FIELDS = (
    'profession','gender','allergies','allergies_notes','other_diseases',
    'medications','medications_notes','surgeries','surgeries_notes','pregnancy',
    'smoking','cigarettes','alcohol','alcohol_frequency','expectations',
    'prior_treatments','prior_treatments_notes','referral','referral_other',
    'photo_consultation','photo_marketing',
)
LIST_FIELDS = ('diseases','interests')


def parse_answers(post):
    result = {k:str(post.get(k) or '').strip()[:3000] for k in ANSWER_FIELDS}
    for k in LIST_FIELDS:
        result[k] = [str(v).strip()[:150] for v in post.getlist(k)[:20] if str(v).strip()]
    return result


def valid_signature(raw):
    if not isinstance(raw, str) or not raw.startswith('data:image/png;base64,') or len(raw) > 260000:
        return False
    try:
        data=base64.b64decode(raw.split(',',1)[1],validate=True)
    except (ValueError,binascii.Error):
        return False
    return len(data) <= 190000 and data.startswith(b'\x89PNG\r\n\x1a\n')


def _name(raw):
    return ' '.join(unicodedata.normalize('NFC',str(raw or '')).casefold().split())


def _phone(raw):
    digits=re.sub('[^0-9]','',str(raw or ''))
    if digits.startswith('00'):digits=digits[2:]
    elif digits.startswith('0'):digits='49'+digits[1:]
    return digits if 8 <= len(digits) <= 15 else ''


def _parts(data):
    return (_name(data.get('first_name')),_name(data.get('last_name')),
            _phone(data.get('phone')),str(data.get('date_of_birth') or ''),
            str(data.get('email') or '').strip().casefold())


def _user_parts(user):
    try:profile=user.profile
    except UserProfile.DoesNotExist:profile=None
    return (_name(user.first_name),_name(user.last_name),
            _phone(profile.phone if profile else ''),
            profile.date_of_birth.isoformat() if profile and profile.date_of_birth else '',
            str(user.email or '').strip().casefold())


def _score(left,right):
    return sum(bool(x and y and x==y) for x,y in zip(left,right))


def _match_or_create(identity):
    """Only one unique 3/5 match is linked; otherwise leave the form unlinked."""
    incoming=_parts(identity)
    people=list(User.objects.filter(is_active=True).select_related('profile').order_by('pk'))
    strong=[]
    overlapping=[]
    for person in people:
        present=_user_parts(person)
        if _score(incoming,present)>=3:
            strong.append(person)
        if ((incoming[2] and incoming[2]==present[2]) or
            (incoming[4] and incoming[4]==present[4])):
            overlapping.append(person)
    if len(strong)==1 and (not overlapping or {x.pk for x in overlapping}=={strong[0].pk}):
        user=strong[0]
        profile=UserProfile.objects.filter(user=user).first()
        if user.is_staff or user.is_superuser or (profile and profile.role!='customer'):
            return None,'review'
        if profile and not profile.date_of_birth:
            parsed=parse_date(identity['date_of_birth'])
            profile.date_of_birth=parsed
            profile.save(update_fields=['date_of_birth'])
        return user,'linked'
    if strong or overlapping:
        return None,'review'
    from .office_views import _unique_username
    user=User(username=_unique_username(identity['email']),email=identity['email'],
              first_name=identity['first_name'],last_name=identity['last_name'],is_active=True)
    user.set_unusable_password()
    user.save()
    UserProfile.objects.create(user=user,role='customer',
        phone=identity['phone'],date_of_birth=parse_date(identity['date_of_birth']),
        salutation=identity.get('salutation') or '',street=identity.get('street') or '',
        postal_code=identity.get('postal_code') or '',city=identity.get('city') or '',
        country='DE',onboarding_required=True)
    MemberAccount.objects.get_or_create(user=user)
    AuditLog.objects.create(actor=None,action='Office Aufnahmebogen patient created',
        entity_type='User',entity_id=str(user.pk),metadata={'source':'office_public_intake'})
    return user,'linked'


def create_signed_submission(identity,answers,signature):
    if not valid_signature(signature):
        raise ValueError('Bitte digital unterschreiben.')
    if len(json.dumps(answers,ensure_ascii=False))>80000:
        raise ValueError('Die Formulardaten sind zu umfangreich.')
    with transaction.atomic():
        OfficeIntakeLock.objects.get_or_create(pk=1)
        OfficeIntakeLock.objects.select_for_update().get(pk=1)
        user,match_status=_match_or_create(identity)
        if user is None and match_status == 'review':
            from .intake_identity import queue_review
            queue_review(identity)
        row=OfficeIntakeSubmission.objects.create(
            user=user,identity=identity,answers=answers,signature_png=signature)
    sync_submission(row)
    return row


def sync_submission(row):
    if not _sync_token():
        row.sync_status='error'
        row.save(update_fields=['sync_status'])
        return False
    payload={'source_id':str(row.public_id),'identity':row.identity,
             'answers':row.answers,'signature':row.signature_png,
             'consent_accepted':True}
    try:
        response=requests.post(BOOK_INTAKE_URL,json=payload,headers=_headers(),timeout=9)
        body=response.json() if response.content else {}
    except (requests.RequestException, ValueError):
        response=None
        body={}
    if response is not None and response.ok and body.get('ok'):
        row.sync_status='linked' if body.get('status')=='linked' else 'review'
        row.book_customer_id=body.get('customer_id') or None
        row.book_record_id=str(body.get('record_id') or '')[:36]
    else:
        row.sync_status='error'
    row.save(update_fields=['sync_status','book_customer_id','book_record_id'])
    return row.sync_status in {'linked','review'}
