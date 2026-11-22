"""Exercise native Office API over the actual isolated A+/Book HTTP bridge."""
import json
import base64
import time
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

APP = 'http://127.0.0.1:5181'
BOOK = 'http://127.0.0.1:5182'


def request(path, *, token=None, payload=None, expected=200):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Content-Type':'application/json', 'Accept':'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(APP + path, data=data, headers=headers)
    try:
        reply = urlopen(req, timeout=15)
    except HTTPError as exc:
        reply = exc
    with reply:
        raw = reply.read()
        if reply.status != expected:
            # Avoid printing patient details or tokens in test output.
            raise AssertionError(f'{path}: expected {expected}, got {reply.status}')
        return raw if reply.headers.get_content_type() == 'application/pdf' else json.loads(raw)


def login(role):
    return request('/api/mobile/login/', payload={
        'email':role+'@example.test', 'password':'Preview-only-2026!',
    })['token']


def main():
    for _ in range(90):
        try:
            with urlopen(APP + '/api/mobile/status/', timeout=2):
                pass
            with urlopen(BOOK + '/api/health/', timeout=2):
                pass
            break
        except (URLError, TimeoutError):
            time.sleep(1)
    else:
        raise RuntimeError('Isolated servers not ready')
    admin, doctor, customer = [login(role) for role in ('admin','doctor','customer')]
    office = '/api/mobile/staff/office/'
    book = '/api/mobile/staff/book/'
    addr = {'street':'Synthetic Testweg 1','postal_code':'60313','city':'Frankfurt'}
    request(office+'intake/', token=customer, payload={
        'date_of_birth':'1990-02-03', **addr,
    })
    result = request(office+'intake/', token=customer)
    assert result['patient']['address'] == addr
    user_id = result['patient']['id']
    users = request(office+'customers/?q=Nora', token=admin)['items']
    assert any(item['id'] == user_id for item in users)
    patients = request(book+'patients/?q=Nora', token=admin)['items']
    patient = next(item for item in patients if item['name'] == 'Nora Berg')
    patient_id = patient['id']
    request(office+'link/', token=admin, payload={
        'customer_id':user_id,'book_customer_id':patient_id,'confirmed_same_patient':True,
    })
    details = request(book+f'patient/{patient_id}/', token=admin)
    visit = next(item for item in details['appointments'] if item['status']=='completed')
    payload = {'customer_id':user_id,'request_id':str(uuid4()),'visit_id':visit['public_id'],
               'lines':[{'goae_number':'1','goae_description':'Synthetische Beratung',
                         'goae_base_eur':'10','goae_factor':'2.30','goae_vat_rate':'19'}]}
    invoice = request(office+'draft/', token=admin, payload=payload, expected=201)['invoice']
    assert invoice['service_date'] == visit['date']
    assert invoice['total_cents'] == 2737
    assert invoice['book_appointment_public_id'] == visit['public_id']
    assert request(office+'draft/', token=admin, payload=payload)['replayed']
    assert request(office+f'invoices/{user_id}/', token=admin)['items'][0]['id'] == invoice['id']
    pdf = request(office+f"pdf/{invoice['id']}/", token=admin)
    assert pdf.startswith(b'%PDF')
    edit = payload | {'revision': invoice['revision'], 'lines': [payload['lines'][0] | {'quantity':'2'}]}
    invoice = request(office+f"edit-draft/{invoice['id']}/", token=admin, payload=edit)['invoice']
    assert invoice['total_cents'] == 5474
    issued = request(office+f"issue-simulation/{invoice['id']}/", token=admin,
                     payload={'revision':invoice['revision'],'confirmed_synthetic':True})['invoice']
    assert issued['number'].startswith('TEST-GOAE-')
    uploaded = request(book+'record-upload/', token=admin, payload={
        'key':str(uuid4()),'customer_id':patient_id,'filename':'synthetic-test.pdf',
        'base64':base64.b64encode(pdf).decode(),
    })
    assert uploaded['ok']
    details=request(book+f'patient/{patient_id}/',token=admin)
    assert any(item['filename']=='synthetic-test.pdf' for item in details['records'])
    assert request(office+f"pdf/{invoice['id']}/", token=admin).startswith(b'%PDF')
    for token in (customer, doctor):
        request(office+f'invoices/{user_id}/', token=token, expected=403)
        request(office+'intake-reviews/', token=token, expected=403)
    print('PASS: synthetic account intake, verified cross-database link, completed Book visit, GOAE draft, replay, edit, synthetic numbering, PDF, role isolation')


if __name__ == '__main__':
    main()
