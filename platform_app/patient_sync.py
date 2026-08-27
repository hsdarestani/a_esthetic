import json
import logging
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import ConsentRecord, UserProfile

logger = logging.getLogger(__name__)

DEFAULT_SYNC_URL = 'http://127.0.0.1:8017/api/internal/patient-records/ingest/'
DEFAULT_TOKEN_FILE = '/etc/aesthetic-patient-sync.token'


def _token():
    value = str(os.environ.get('PATIENT_RECORD_SYNC_TOKEN') or '').strip()
    if value:
        return value
    token_file = Path(os.environ.get('PATIENT_RECORD_SYNC_TOKEN_FILE', DEFAULT_TOKEN_FILE))
    try:
        return token_file.read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError):
        return ''


def _endpoint():
    return str(os.environ.get('PATIENT_RECORD_SYNC_URL') or DEFAULT_SYNC_URL).strip()


def _post(payload):
    token = _token()
    endpoint = _endpoint()
    if not token or not endpoint:
        return False
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    request = Request(
        endpoint,
        data=body,
        method='POST',
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8',
            'X-Aesthetic-Patient-Sync': token,
            'User-Agent': 'A+Esthetic-Patient-Sync/1.0',
        },
    )
    timeout = float(os.environ.get('PATIENT_RECORD_SYNC_TIMEOUT', '5'))
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8') or '{}')
            return 200 <= response.status < 300 and result.get('ok') is True
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        logger.warning('Patientenakten-Synchronisation fehlgeschlagen: %s', exc)
        return False


def _patient_identity(record):
    user = record.user
    profile = UserProfile.objects.filter(user=user).only('phone').first()
    return {
        'email': (user.email or '').strip().lower(),
        'phone': profile.phone if profile else '',
        'first_name': (user.first_name or '').strip(),
        'last_name': (user.last_name or '').strip(),
        'full_name': (user.get_full_name() or user.username).strip(),
    }


def _acceptance_payload(record):
    template = record.template
    note = (
        f'{template.title}\n'
        f'Version: {template.version}\n'
        f'Bestätigt am: {record.accepted_at.isoformat()}\n\n'
        f'{template.text}'
    )
    return {
        **_patient_identity(record),
        'source': 'a_esthetic_app',
        'external_id': f'consent:{record.pk}:acceptance',
        'kind': 'form',
        'title': f'Einwilligung · {template.title}'[:180],
        'note': note,
        'captured_at': record.accepted_at.isoformat(),
        'metadata': {
            'document_type': 'consent',
            'consent_record_id': record.pk,
            'template_id': template.pk,
            'template_key': template.key,
            'template_version': template.version,
            'health_data': template.health_data,
            'marketing': template.marketing,
            'accepted': bool(record.accepted),
            'evidence': record.evidence if isinstance(record.evidence, dict) else {},
        },
    }


def _withdrawal_payload(record):
    template = record.template
    return {
        **_patient_identity(record),
        'source': 'a_esthetic_app',
        'external_id': f'consent:{record.pk}:withdrawal',
        'kind': 'form',
        'title': f'Widerruf · {template.title}'[:180],
        'note': (
            f'Widerruf einer zuvor dokumentierten Einwilligung.\n'
            f'Version: {template.version}\n'
            f'Widerrufen am: {record.withdrawn_at.isoformat()}'
        ),
        'captured_at': record.withdrawn_at.isoformat(),
        'metadata': {
            'document_type': 'consent_withdrawal',
            'consent_record_id': record.pk,
            'template_id': template.pk,
            'template_key': template.key,
            'template_version': template.version,
            'accepted': False,
            'withdrawn': True,
        },
    }


def sync_consent_record(record_or_id):
    if isinstance(record_or_id, ConsentRecord):
        record = record_or_id
        if not hasattr(record, 'template'):
            record = ConsentRecord.objects.select_related('template', 'user').get(pk=record.pk)
    else:
        try:
            record = ConsentRecord.objects.select_related('template', 'user').get(pk=record_or_id)
        except ConsentRecord.DoesNotExist:
            return False

    if not record.accepted:
        return True

    acceptance_ok = _post(_acceptance_payload(record))
    if not acceptance_ok:
        return False
    if record.withdrawn_at:
        return _post(_withdrawal_payload(record))
    return True
