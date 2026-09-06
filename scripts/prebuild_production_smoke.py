#!/usr/bin/env python3
"""Production-safe smoke test for the five-function A+ Esthetic patient app.

Creates isolated temporary users, exercises customer/admin endpoints, never sends a
real push, never books a real appointment and cleans all temporary data afterwards.
Successful booking/referral writes are covered by the local Django suites because
those actions can send real customer/admin email in production.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path('/opt/a-esthetic-mobile')
VENDOR = ROOT / 'vendor'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(VENDOR))
os.chdir(ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from platform_app.models import MemberAccount, UserProfile, WalletAccount  # noqa: E402
from p0_app.models import GoogleReviewActivity  # noqa: E402
from p0_app.ops_models import PushDevice  # noqa: E402

BASE = 'https://esthetic.smarbiz.sbs'
BOOK = 'https://book.a-esthetic.de'
STAMP = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
EMAIL = f"prebuild-{STAMP}@example.invalid"
ADMIN_EMAIL = f"prebuild-admin-{STAMP}@example.invalid"
PASSWORD = f"Smoke-{uuid.uuid4().hex}-A9!"
PREFIX = f"PREBUILD-{STAMP}"
created_user = None
created_admin = None
record_id = None


def log(name: str, detail: str = 'OK') -> None:
    print(f"[PASS] {name}: {detail}", flush=True)


def request_json(url: str, *, token: str = '', method: str = 'GET', data=None, expected=(200,)):
    body = None
    headers = {'Accept': 'application/json', 'User-Agent': 'APlus-Prebuild-Smoke/1.0'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=25) as resp:
            raw = resp.read()
            status = resp.status
            ctype = resp.headers.get('Content-Type', '')
    except HTTPError as exc:
        raw = exc.read()
        status = exc.code
        ctype = exc.headers.get('Content-Type', '')
    if status not in expected:
        raise AssertionError(f'{method} {url} -> {status}; expected {expected}; body={raw[:800]!r}')
    payload = json.loads(raw.decode('utf-8')) if 'json' in ctype.lower() or raw[:1] in {b'{', b'['} else None
    return status, payload, raw


def request_binary(url: str, *, token: str = '', expected=(200,)):
    headers = {'User-Agent': 'APlus-Prebuild-Smoke/1.0'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = Request(url, method='GET', headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
            status = resp.status
            ctype = resp.headers.get('Content-Type', '')
    except HTTPError as exc:
        raw = exc.read()
        status = exc.code
        ctype = exc.headers.get('Content-Type', '')
    if status not in expected:
        raise AssertionError(f'GET {url} -> {status}; expected {expected}; body={raw[:500]!r}')
    return status, ctype, raw


def multipart_upload(url: str, token: str, fields: dict[str, str], filename: str, content: bytes):
    boundary = f'----APlusPrebuild{uuid.uuid4().hex}'
    chunks = []
    for key, value in fields.items():
        chunks += [
            f'--{boundary}\r\n'.encode(),
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
            str(value).encode(), b'\r\n',
        ]
    chunks += [
        f'--{boundary}\r\n'.encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        b'Content-Type: text/plain\r\n\r\n', content, b'\r\n',
        f'--{boundary}--\r\n'.encode(),
    ]
    body = b''.join(chunks)
    req = Request(url, data=body, method='POST', headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': 'application/json',
        'User-Agent': 'APlus-Prebuild-Smoke/1.0',
    })
    try:
        with urlopen(req, timeout=35) as resp:
            raw, status = resp.read(), resp.status
    except HTTPError as exc:
        raw, status = exc.read(), exc.code
    if status not in (200, 201):
        raise AssertionError(f'patient upload -> {status}: {raw[:800]!r}')
    return json.loads(raw.decode('utf-8'))


def cleanup_book() -> None:
    cleanup = r'''
import os
from pathlib import Path
from booking.models import Customer, PatientRecord
email=os.environ['SMOKE_EMAIL']
for r in PatientRecord.objects.filter(customer__email__iexact=email):
    if r.stored_name:
        roots=[Path(os.environ.get('PATIENT_FILES_ROOT','')), Path.cwd()/'media']
        for root in roots:
            if str(root) and root.exists():
                for candidate in (root/r.stored_name, root/'patient-records'/r.stored_name):
                    try:
                        if candidate.is_file(): candidate.unlink()
                    except OSError: pass
    r.delete()
Customer.objects.filter(email__iexact=email, appointments__isnull=True).delete()
print('BOOK_SMOKE_CLEANUP=ok')
'''
    env = dict(os.environ)
    env['SMOKE_EMAIL'] = EMAIL
    cmd = [
        'runuser', '-u', 'aestheticbook', '--preserve-environment', '--', 'bash', '-lc',
        "set -a; source /etc/aesthetic-book.env; set +a; cd /opt/aesthetic-book/app; /opt/aesthetic-book/venv/bin/python manage.py shell -c "$'" + cleanup.replace("'", "'\\''") + "'"",
    ]
    # Avoid making cleanup failure hide the actual smoke result; print diagnostics.
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=40)
        print(result.stdout[-1000:], flush=True)
        if result.returncode:
            print('[WARN] Book cleanup:', result.stderr[-1000:], flush=True)
    except Exception as exc:
        print(f'[WARN] Book cleanup exception: {exc}', flush=True)


def main() -> None:
    global created_user, created_admin, record_id

    created_user = User.objects.create_user(
        username=f'prebuild-{STAMP}', email=EMAIL, password=PASSWORD,
        first_name='Prebuild', last_name='Patient', is_active=True,
    )
    profile, _ = UserProfile.objects.get_or_create(user=created_user)
    profile.role = 'customer'
    profile.phone = '+490000000000'
    profile.save(update_fields=['role', 'phone'])
    member, _ = MemberAccount.objects.get_or_create(user=created_user)
    member.status = 'active'
    member.save(update_fields=['status'])
    WalletAccount.objects.get_or_create(user=created_user)

    created_admin = User.objects.create_user(
        username=f'prebuild-admin-{STAMP}', email=ADMIN_EMAIL, password=PASSWORD,
        first_name='Prebuild', last_name='Admin', is_active=True, is_staff=True, is_superuser=True,
    )
    admin_profile, _ = UserProfile.objects.get_or_create(user=created_admin)
    admin_profile.role = 'admin'
    admin_profile.save(update_fields=['role'])

    status, login, _ = request_json(f'{BASE}/api/mobile/login/', method='POST', data={'email': EMAIL, 'password': PASSWORD})
    assert login['ok'] and login['account_type'] == 'customer' and not login['admin']
    token = login['token']
    log('customer login')

    _, admin_login, _ = request_json(f'{BASE}/api/mobile/login/', method='POST', data={'email': ADMIN_EMAIL, 'password': PASSWORD})
    assert admin_login['ok'] and admin_login['account_type'] == 'admin' and admin_login['admin']
    admin_token = admin_login['token']
    log('admin login separation')

    _, me, _ = request_json(f'{BASE}/api/mobile/me/', token=token)
    assert me['ok'] and me['profile']['email'].lower() == EMAIL.lower()
    log('account / me')

    # Canonical Book integration: auth, catalog, staff and live availability.
    _, booking, _ = request_json(f'{BOOK}/api/mobile/booking/', token=token)
    assert booking['ok'] and booking.get('slot_mode') is True
    assert booking.get('services'), 'canonical Book returned no bookable services'
    assert booking.get('staff'), 'canonical Book returned no active staff'
    service_id = booking['services'][0]['id']
    found_slots = False
    from datetime import date, timedelta
    for offset in range(1, 46):
        day = (date.today() + timedelta(days=offset)).isoformat()
        url = f'{BOOK}/api/mobile/slots/?{urlencode({"service_id": service_id, "day": day})}'
        st, slots, _ = request_json(url, expected=(200, 400))
        if st == 200 and slots.get('slots'):
            found_slots = True
            break
    assert found_slots, 'no live bookable slot found in next 45 days'
    log('canonical booking catalog + live slots')

    # Booking write transport/auth without creating an appointment/email.
    st, invalid_booking, _ = request_json(
        f'{BOOK}/api/mobile/booking/', token=token, method='POST',
        data={'service_id': 999999999, 'starts_at': '2099-01-01T12:00:00+00:00'}, expected=(400,),
    )
    assert invalid_booking.get('error') == 'service_not_found'
    log('booking POST transport/auth guard')

    # Google review lifecycle.
    _, reviews, _ = request_json(f'{BASE}/api/mobile/reviews/', token=token)
    assert reviews['ok'] and reviews.get('review_url', '').startswith('https://')
    request_json(f'{BASE}/api/mobile/reviews/', token=token, method='POST', data={'action': 'opened'}, expected=(200,))
    _, submitted, _ = request_json(
        f'{BASE}/api/mobile/reviews/', token=token, method='POST',
        data={'action': 'submitted', 'rating': 5, 'review_text': PREFIX}, expected=(200,),
    )
    assert any(x.get('status') == 'submitted' and x.get('review_text') == PREFIX for x in submitted['activities'])
    review_id = next(x['id'] for x in submitted['activities'] if x.get('review_text') == PREFIX)
    _, verified, _ = request_json(
        f'{BASE}/api/mobile/admin/reviews/{review_id}/', token=admin_token, method='POST',
        data={'action': 'verify', 'rating': 5}, expected=(200,),
    )
    assert verified['review']['status'] == 'verified'
    log('Google review open/submitted/admin verify/history')

    # Referrals: production GET plus validation/self-protection. Real SMTP success is unit-tested.
    _, club, _ = request_json(f'{BASE}/api/mobile/club/', token=token)
    assert club['ok'] and isinstance(club.get('referrals'), list)
    _, invalid_ref, _ = request_json(f'{BASE}/api/mobile/club/', token=token, method='POST', data={'invited_email': 'not-an-email'}, expected=(400,))
    assert invalid_ref.get('error') == 'valid_email_required'
    _, self_ref, _ = request_json(f'{BASE}/api/mobile/club/', token=token, method='POST', data={'invited_email': EMAIL}, expected=(409,))
    assert self_ref.get('error') == 'cannot_refer_yourself'
    log('referral history + validation + self-protection')

    # Wallet read, QR, Apple pass and admin QR/credit flow.
    _, wallet, _ = request_json(f'{BASE}/api/mobile/wallet/', token=token)
    assert wallet['ok'] and isinstance(wallet.get('balance_cents'), int)
    baseline = wallet['balance_cents']
    _, pass_info, _ = request_json(f'{BASE}/api/mobile/wallet-pass/', token=token)
    assert pass_info['ok'] and pass_info['providers']['apple']['configured'] is True
    _, qr_type, qr = request_binary(f'{BASE}/api/mobile/wallet-pass/qr/', token=token)
    assert qr and ('image/' in qr_type or qr.startswith(b'\x89PNG'))
    _, pk_type, pkpass = request_binary(f'{BASE}/api/mobile/wallet-pass/apple/', token=token)
    assert pkpass[:2] == b'PK' and len(pkpass) > 1000
    log('wallet read + QR + signed Apple pkpass')

    _, lookup, _ = request_json(
        f'{BASE}/api/mobile/admin/wallet/lookup/', token=admin_token, method='POST',
        data={'qr_token': member.qr_token}, expected=(200,),
    )
    assert lookup['customer']['id'] == created_user.pk
    request_json(
        f'{BASE}/api/mobile/admin/customers/{created_user.pk}/', token=admin_token, method='POST',
        data={'credit_delta_cents': 1234}, expected=(200,),
    )
    _, wallet_after, _ = request_json(f'{BASE}/api/mobile/wallet/', token=token)
    assert wallet_after['balance_cents'] == baseline + 1234
    request_json(
        f'{BASE}/api/mobile/admin/customers/{created_user.pk}/', token=admin_token, method='POST',
        data={'credit_delta_cents': -1234}, expected=(200,),
    )
    _, wallet_restored, _ = request_json(f'{BASE}/api/mobile/wallet/', token=token)
    assert wallet_restored['balance_cents'] == baseline
    log('admin QR wallet lookup + credit add/remove')

    # Push device registration only: fake tokens are registered/deleted, never delivered.
    for plat in ('android', 'ios'):
        fake = f'prebuild-{plat}-{STAMP}'
        _, dev, _ = request_json(
            f'{BASE}/api/mobile/notifications/devices/', token=token, method='POST',
            data={'token': fake, 'platform': plat, 'app_version': 'prebuild'}, expected=(200, 201),
        )
        assert dev['push'][plat] is True
        _, removed, _ = request_json(
            f'{BASE}/api/mobile/notifications/devices/', token=token, method='DELETE',
            data={'token': fake}, expected=(200,),
        )
        assert removed['ok']
    log('Android/iOS push registration + credential exposure')

    # Patient record: list, consent, upload, list, file, archive.
    _, records, _ = request_json(f'{BASE}/api/mobile/patient-records/', token=token)
    assert records['ok'] and records['upload']['max_mb'] == 10
    file_bytes = f'{PREFIX}\npatient record smoke\n'.encode()
    uploaded = multipart_upload(
        f'{BASE}/api/mobile/patient-records/upload/', token,
        {'kind': 'document', 'title': PREFIX, 'note': 'Automated prebuild smoke', 'health_data_consent': '1'},
        f'{PREFIX}.txt', file_bytes,
    )
    assert uploaded['ok'] and uploaded.get('record_id')
    record_id = uploaded['record_id']
    _, records_after, _ = request_json(f'{BASE}/api/mobile/patient-records/', token=token)
    assert any(str(r.get('id')) == str(record_id) for r in records_after['records'])
    _, _, downloaded = request_binary(f'{BASE}/api/mobile/patient-records/{record_id}/file/?download=1', token=token)
    assert downloaded == file_bytes
    _, archived, _ = request_json(
        f'{BASE}/api/mobile/patient-records/{record_id}/archive/', token=token, method='POST', data={}, expected=(200,),
    )
    assert archived.get('archived') is True
    log('patient record list/upload/download/archive + health consent')

    # Legal/store-required pages.
    for path in ('/datenschutz/', '/nutzungsbedingungen/', '/impressum/', '/support/', '/konto-loeschen/'):
        st, ctype, raw = request_binary(BASE + path)
        assert st == 200 and len(raw) > 100
    log('privacy / terms / imprint / support / deletion pages')

    # Surface must be the five focused functions only, with native push and Apple-only wallet.
    _, _, index = request_binary(BASE + '/')
    html = index.decode('utf-8', 'replace')
    for asset in ('core-app.js', 'booking-direct-api.js', 'booking-book-flow.js', 'focused-upgrade.js', 'native-push.js', 'apple-wallet-only.css'):
        assert asset in html, f'missing production asset {asset}'
    for legacy in ('src="./app.js', 'src="./p0.js', 'src="./ops.js'):
        assert legacy not in html, f'legacy runtime loaded: {legacy}'
    log('focused five-function production surface')


if __name__ == '__main__':
    failure = None
    try:
        main()
    except Exception as exc:
        failure = exc
        print(f'[FAIL] {type(exc).__name__}: {exc}', flush=True)
    finally:
        try:
            cleanup_book()
        finally:
            if created_user:
                GoogleReviewActivity.objects.filter(user=created_user).delete()
                PushDevice.objects.filter(user=created_user).delete()
                created_user.delete()
            if created_admin:
                created_admin.delete()
            print('AESTHETIC_SMOKE_CLEANUP=ok', flush=True)
    if failure:
        raise failure
    print('FOCUSED_PREBUILD_PRODUCTION_SMOKE=success', flush=True)
