"""Additional V4 end-to-end QA, exclusively on the loopback synthetic preview."""
import base64
from io import BytesIO
from uuid import uuid4
import sys

from PIL import Image
import requests
from mobile_staff_preview import _guard
from test_native_office_preview import APP, login, request, main as core

sys.addaudithook(_guard)


def main():
    core()
    admin, doctor, customer = [login(role) for role in ('admin','doctor','customer')]
    book='/api/mobile/staff/book/'
    office='/api/mobile/staff/office/'
    overview=request(book+'overview/',token=admin)
    assert overview['upcoming_count']>=0 and overview['provider_today']
    patient=request(book+'patients/?q=Nora',token=admin)['items'][0]
    pid=patient['id']
    linked=request(office+f'patient-account/{pid}/',token=admin)
    uid=linked['customer_id']
    assert uid
    account=request(f'/api/mobile/admin/customers/{uid}/',token=admin)['customer']
    before=account['coins']
    assert request(f'/api/mobile/staff/points/{uid}/',token=admin,payload={'key':str(uuid4()),'coin_delta':1})['coins']==before+1
    request(f'/api/mobile/staff/points/{uid}/',token=doctor,payload={'key':str(uuid4()),'coin_delta':1},expected=403)
    photo=BytesIO()
    Image.new('RGB',(40,30),'white').save(photo,format='JPEG')
    assert request(book+'record-upload/',token=admin,payload={'customer_id':pid,'key':str(uuid4()),
        'filename':'synthetic-photo.jpg','base64':base64.b64encode(photo.getvalue()).decode()})['ok']
    assert request(book+'record-note/',token=admin,payload={'customer_id':pid,'key':str(uuid4()),
        'title':'Synthetic V4 note','note':'Original synthetic note'})['ok']
    records=request(book+f'patient/{pid}/',token=admin)['records']
    assert any(r['kind']=='photo' and r['filename']=='synthetic-photo.jpg' for r in records)
    note=next(r for r in records if r['title']=='Synthetic V4 note')
    edit={'customer_id':pid,'record_id':note['id'],'revision':note['revision'],'title':'Synthetic V4 correction','note':'Updated synthetic note'}
    assert request(book+'record-edit/',token=admin,payload=edit|{'key':str(uuid4())})['ok']
    request(book+'record-edit/',token=admin,payload=edit|{'key':str(uuid4())},expected=409)
    png=BytesIO()
    Image.new('RGB',(50,20),'white').save(png,format='PNG')
    session=requests.Session();session.trust_env=False
    assert session.get(APP+'/office/',timeout=10).ok
    token=session.cookies.get('csrftoken')
    payload={'csrfmiddlewaretoken':token,'first_name':'Synthetic','last_name':'V4 Intake','email':'v4-signed@example.test',
             'phone':'+49 170 5550198','date_of_birth':'05.04.1990','street':'Testweg 1','postal_code':'60313','city':'Frankfurt',
             'consent_accepted':'on','privacy_ack':'on','signature_png':'data:image/png;base64,'+base64.b64encode(png.getvalue()).decode()}
    response=session.post(APP+'/office/',data=payload,headers={'Referer':APP+'/office/'},timeout=15)
    assert response.ok and 'Vielen Dank' in response.text
    forms=request(book+'forms/?q=V4%20Intake',token=admin)['items']
    assert forms and forms[0]['status']=='linked'
    ident=forms[0]['id']
    assert request(book+f'forms/{ident}/',token=admin)['submission']['signature_png'].startswith('data:image/png;base64,')
    assert request(book+f'forms/{ident}/pdf/',token=admin).startswith(b'%PDF-')
    for role in (doctor,customer):
        request(book+'forms/',token=role,expected=403)
    print('PASS: real V4 dashboard, verified customer wallet/points, private photo, revisioned record correction, signed form sync/detail/PDF and role isolation')


if __name__=='__main__':
    main()
