#!/usr/bin/env python3
from __future__ import annotations

import json, os, subprocess, sys, time, uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path('/opt/a-esthetic-mobile'); sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]; os.chdir(ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from django.contrib.auth.models import User
from platform_app.models import MemberAccount, UserProfile, WalletAccount
from p0_app.models import GoogleReviewActivity
from p0_app.ops_models import PushDevice

BASE='https://esthetic.smarbiz.sbs'; BOOK='https://book.a-esthetic.de'
STAMP=f"{int(time.time())}-{uuid.uuid4().hex[:6]}"; EMAIL=f"prebuild-{STAMP}@example.invalid"; ADMIN_EMAIL=f"prebuild-admin-{STAMP}@example.invalid"
PASSWORD=f"Smoke-{uuid.uuid4().hex}-A9!"; PREFIX=f"PREBUILD-{STAMP}"
customer=admin=None

def ok(name): print(f'[PASS] {name}',flush=True)

def req(url, token='', method='GET', data=None, expected=(200,), binary=False):
    headers={'Accept':'application/json','User-Agent':'APlus-Prebuild-Smoke/1.0'}
    if token: headers['Authorization']=f'Bearer {token}'
    body=None
    if data is not None:
        body=json.dumps(data).encode(); headers['Content-Type']='application/json'
    r=Request(url,data=body,method=method,headers=headers)
    try:
        with urlopen(r,timeout=35) as x: status=x.status; raw=x.read(); ctype=x.headers.get('Content-Type','')
    except HTTPError as x:
        status=x.code; raw=x.read(); ctype=x.headers.get('Content-Type','')
    if status not in expected: raise AssertionError(f'{method} {url} -> {status}: {raw[:800]!r}')
    if binary: return status,ctype,raw
    return status,(json.loads(raw.decode()) if raw else {}),raw

def upload(token, fields, filename, content):
    b=f'----APlus{uuid.uuid4().hex}'; chunks=[]
    for k,v in fields.items(): chunks += [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()]
    chunks += [f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: text/plain\r\n\r\n'.encode(),content,b'\r\n',f'--{b}--\r\n'.encode()]
    r=Request(f'{BASE}/api/mobile/patient-records/upload/',data=b''.join(chunks),method='POST',headers={'Authorization':f'Bearer {token}','Content-Type':f'multipart/form-data; boundary={b}','Accept':'application/json','User-Agent':'APlus-Prebuild-Smoke/1.0'})
    try:
        with urlopen(r,timeout=40) as x: status=x.status; raw=x.read()
    except HTTPError as x: status=x.code; raw=x.read()
    if status not in (200,201): raise AssertionError(f'patient upload -> {status}: {raw[:800]!r}')
    return json.loads(raw.decode())

def cleanup_book():
    script="""
import os
from pathlib import Path
from booking.models import Customer,PatientRecord
email=os.environ['SMOKE_EMAIL']
for r in PatientRecord.objects.filter(customer__email__iexact=email):
    if r.stored_name:
        for root in [Path(os.environ.get('PATIENT_FILES_ROOT','')),Path.cwd()/'media']:
            if str(root):
                for p in [root/r.stored_name,root/'patient-records'/r.stored_name]:
                    try:
                        if p.is_file(): p.unlink()
                    except OSError: pass
    r.delete()
Customer.objects.filter(email__iexact=email,appointments__isnull=True).delete()
print('BOOK_SMOKE_CLEANUP=ok')
"""
    env=dict(os.environ); env['SMOKE_EMAIL']=EMAIL
    cmd=['runuser','-u','aestheticbook','--preserve-environment','--','bash','-lc','set -a; source /etc/aesthetic-book.env; set +a; cd /opt/aesthetic-book/app; /opt/aesthetic-book/venv/bin/python manage.py shell']
    try:
        p=subprocess.run(cmd,input=script,text=True,capture_output=True,env=env,timeout=45)
        print(p.stdout[-1000:],flush=True)
        if p.returncode: print('[WARN] book cleanup '+p.stderr[-1000:],flush=True)
    except Exception as e: print(f'[WARN] book cleanup {e}',flush=True)

def main():
    global customer,admin
    customer=User.objects.create_user(username=f'prebuild-{STAMP}',email=EMAIL,password=PASSWORD,first_name='Prebuild',last_name='Patient',is_active=True)
    p,_=UserProfile.objects.get_or_create(user=customer); p.role='customer'; p.phone='+490000000000'; p.save(update_fields=['role','phone'])
    member,_=MemberAccount.objects.get_or_create(user=customer); member.status='active'; member.save(update_fields=['status']); WalletAccount.objects.get_or_create(user=customer)
    admin=User.objects.create_user(username=f'prebuild-admin-{STAMP}',email=ADMIN_EMAIL,password=PASSWORD,first_name='Prebuild',last_name='Admin',is_active=True,is_staff=True,is_superuser=True)
    ap,_=UserProfile.objects.get_or_create(user=admin); ap.role='admin'; ap.save(update_fields=['role'])

    _,x,_=req(f'{BASE}/api/mobile/login/',method='POST',data={'email':EMAIL,'password':PASSWORD}); assert x['ok'] and x['account_type']=='customer' and not x['admin']; token=x['token']; ok('customer login')
    _,x,_=req(f'{BASE}/api/mobile/login/',method='POST',data={'email':ADMIN_EMAIL,'password':PASSWORD}); assert x['ok'] and x['account_type']=='admin' and x['admin']; at=x['token']; ok('admin login separation')
    _,x,_=req(f'{BASE}/api/mobile/me/',token); assert x['profile']['email'].lower()==EMAIL.lower(); ok('account / me')

    _,book,_=req(f'{BOOK}/api/mobile/booking/',token); assert book['ok'] and book['slot_mode'] and book['services'] and book['staff']; sid=book['services'][0]['id']
    live=False
    for off in range(1,46):
        day=(date.today()+timedelta(days=off)).isoformat(); s,p,_=req(f'{BOOK}/api/mobile/slots/?{urlencode({"service_id":sid,"day":day})}',expected=(200,400))
        if s==200 and p.get('slots'): live=True; break
    assert live,'no bookable slot in next 45 days'; ok('canonical booking catalog + live slots')
    _,e,_=req(f'{BOOK}/api/mobile/booking/',token,'POST',{'service_id':999999999,'starts_at':'2099-01-01T12:00:00+00:00'},(400,)); assert e['error']=='service_not_found'; ok('booking POST transport/auth guard')

    _,r,_=req(f'{BASE}/api/mobile/reviews/',token); assert r['review_url'].startswith('https://')
    req(f'{BASE}/api/mobile/reviews/',token,'POST',{'action':'opened'})
    _,r,_=req(f'{BASE}/api/mobile/reviews/',token,'POST',{'action':'submitted','rating':5,'review_text':PREFIX}); rid=next(i['id'] for i in r['activities'] if i.get('review_text')==PREFIX)
    _,r,_=req(f'{BASE}/api/mobile/admin/reviews/{rid}/',at,'POST',{'action':'verify','rating':5}); assert r['review']['status']=='verified'; ok('Google review lifecycle + history')

    _,c,_=req(f'{BASE}/api/mobile/club/',token); assert isinstance(c['referrals'],list)
    _,e,_=req(f'{BASE}/api/mobile/club/',token,'POST',{'invited_email':'bad'},(400,)); assert e['error']=='valid_email_required'
    _,e,_=req(f'{BASE}/api/mobile/club/',token,'POST',{'invited_email':EMAIL},(409,)); assert e['error']=='cannot_refer_yourself'; ok('referral history + validation')

    _,w,_=req(f'{BASE}/api/mobile/wallet/',token); base=w['balance_cents']; assert isinstance(base,int)
    _,pi,_=req(f'{BASE}/api/mobile/wallet-pass/',token); assert pi['providers']['apple']['configured'] is True
    _,ct,qr=req(f'{BASE}/api/mobile/wallet-pass/qr/',token,binary=True); assert qr and ('image/' in ct or qr.startswith(b'\x89PNG'))
    _,_,pk=req(f'{BASE}/api/mobile/wallet-pass/apple/',token,binary=True); assert pk[:2]==b'PK' and len(pk)>1000; ok('wallet + QR + signed Apple Wallet pass')
    _,lk,_=req(f'{BASE}/api/mobile/admin/wallet/lookup/',at,'POST',{'qr_token':member.qr_token}); assert lk['customer']['id']==customer.pk
    req(f'{BASE}/api/mobile/admin/customers/{customer.pk}/',at,'POST',{'credit_delta_cents':1234}); _,w,_=req(f'{BASE}/api/mobile/wallet/',token); assert w['balance_cents']==base+1234
    req(f'{BASE}/api/mobile/admin/customers/{customer.pk}/',at,'POST',{'credit_delta_cents':-1234}); _,w,_=req(f'{BASE}/api/mobile/wallet/',token); assert w['balance_cents']==base; ok('admin QR lookup + wallet credit add/remove')

    for plat in ('android','ios'):
        fake=f'prebuild-{plat}-{STAMP}'; _,d,_=req(f'{BASE}/api/mobile/notifications/devices/',token,'POST',{'token':fake,'platform':plat,'app_version':'prebuild'},(200,201)); assert d['push'][plat] is True
        _,d,_=req(f'{BASE}/api/mobile/notifications/devices/',token,'DELETE',{'token':fake}); assert d['ok']
    ok('Android/iOS push registration + configured providers')

    _,pr,_=req(f'{BASE}/api/mobile/patient-records/',token); assert pr['upload']['max_mb']==10
    content=f'{PREFIX}\npatient record smoke\n'.encode(); u=upload(token,{'kind':'document','title':PREFIX,'note':'Automated prebuild smoke','health_data_consent':'1'},f'{PREFIX}.txt',content); rec=str(u['record_id'])
    _,pr,_=req(f'{BASE}/api/mobile/patient-records/',token); assert any(str(i['id'])==rec for i in pr['records'])
    _,_,raw=req(f'{BASE}/api/mobile/patient-records/{rec}/file/?download=1',token,binary=True); assert raw==content
    _,a,_=req(f'{BASE}/api/mobile/patient-records/{rec}/archive/',token,'POST',{}); assert a['archived'] is True; ok('patient record list/upload/download/archive + consent')

    for pth in ('/datenschutz/','/nutzungsbedingungen/','/impressum/','/support/','/konto-loeschen/'):
        _,_,raw=req(BASE+pth,binary=True); assert len(raw)>100
    ok('legal + support + account deletion pages')
    _,_,raw=req(BASE+'/',binary=True); html=raw.decode('utf-8','replace')
    for asset in ('core-app.js','booking-direct-api.js','booking-book-flow.js','focused-upgrade.js','native-push.js','apple-wallet-only.css'): assert asset in html,asset
    for legacy in ('src="./app.js','src="./p0.js','src="./ops.js'): assert legacy not in html,legacy
    ok('focused five-function production surface + native push bridge')

if __name__=='__main__':
    err=None
    try: main()
    except Exception as e: err=e; print(f'[FAIL] {type(e).__name__}: {e}',flush=True)
    finally:
        cleanup_book()
        if customer:
            GoogleReviewActivity.objects.filter(user=customer).delete(); PushDevice.objects.filter(user=customer).delete(); customer.delete()
        if admin: admin.delete()
        print('AESTHETIC_SMOKE_CLEANUP=ok',flush=True)
    if err: raise err
    print('FOCUSED_PREBUILD_PRODUCTION_SMOKE=success',flush=True)
