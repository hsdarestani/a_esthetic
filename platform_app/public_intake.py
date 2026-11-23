"""General public intake persistence and private Book patient-record synchronization.

The public response reveals no patient lookup result or clinical history.
Only the server-to-server token can submit the signed form to Book.
"""
import base64
import binascii
import json
import re

import requests
from django.contrib.auth.models import User
from django.db import transaction

from .book_sync import _headers, _sync_token
from .intake_identity import potential_matches, score, user_data, queue_review
from .models import MemberAccount, OfficeIntakeSubmission, OfficeIntakeLock, UserProfile

BOOK_INTAKE_URL = 'https://book.a-esthetic.de/api/internal/patient-intake/ingest/'

ANSWER_FIELDS = (
    'profession','gender','allergies','allergies_notes','other_diseases',
    'medications','medications_notes','surgeries','surgeries_notes',
    'pregnancy','smoking','cigarettes','alcohol','alcohol_frequency',
    'expectations','prior_treatments','prior_treatments_notes',
    'referral','referral_other','photo_consultation','photo_marketing',
)
LIST_FIELDS = ('diseases','interests')


def parse_answers(post):
    answers={key:str(post.get(key) or '').strip()[:3000] for key in ANSWER_FIELDS}
    for key in LIST_FIELDS:
        answers[key]=[str(v).strip()[:150] for v in post.getlist(key)[:20] if str(v).strip()]
    return answers


def valid_signature(raw):
    if not isinstance(raw,str) or not raw.startswith('data:image/png;base64,') or len(raw)>260000:
        return False
    try:
        blob=base64.b64decode(raw.split(',',1)[1],validate=True)
    except (ValueError,binascii.Error):
        return False
    return len(blob)<=190000 and blob.startswith(b'\x89PNG\r\n\x1a\n')


def create_signed_submission(data, answers, signature):
    """Use >=3/5 unique identity in A+; conflicting profiles stay unlinked."""
    if not valid_signature(signature):
        raise ValueError('Bitte digital unterschreiben.')
    if len(json.dumps(answers,ensure_ascii=False))>80000:
        raise ValueError('Die Formulardaten sind zu umfangreich.')
    from .office_views import _submit_unverified_intake
    with transaction.atomic():
        OfficeIntakeLock.objects.get_or_create(pk=1)
        OfficeIntakeLock.objects.select_for_update().get(pk=1)
        candidates=potential_matches(data)
        strong=list(User.objects.filter(pk__in=candidates))
        strong=[u for u in strong if score(data,user_data(u))>=3]
        user=None
        if len(strong)==1 and set(candidates)=={strong[0].pk}:
            user=strong[0]
        elif not candidates:
            member,pending=_submit_unverified_intake(data)
            if member is not None:
                user=member.user
        if user is None:
            queue_review(data)
        submission=OfficeIntakeSubmission.objects.create(
            user=user, identity=data, answers=answers,signature_png=signature)
    sync_submission(submission)
    return submission


def sync_submission(submission):
    if not _sync_token():
        submission.sync_status='error'
        submission.save(update_fields=['sync_status'])
        return False
    payload={
        'source_id':str(submission.public_id),
        'identity':submission.identity,
        'answers':submission.answers,
        'signature':submission.signature_png,
        'consent_accepted':True,
    }
    try:
        response=requests.post(BOOK_INTAKE_URL,json=payload,headers=_headers(),timeout=9)
        data=response.json() if response.content else {}
    except (requests.RequestException,ValueError):
        data={}
        response=None
    if response is not None and response.ok and data.get('ok'):
        submission.sync_status='linked' if data.get('status')=='linked' else 'review'
        submission.book_customer_id=data.get('customer_id') or None
        submission.book_record_id=str(data.get('record_id') or '')[:36]
    else:
        submission.sync_status='error'
    submission.save(update_fields=['sync_status','book_customer_id','book_record_id'])
    return submission.sync_status in {'linked','review'}
