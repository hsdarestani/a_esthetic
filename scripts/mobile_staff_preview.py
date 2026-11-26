"""Run both feature branches on loopback with two disposable PostgreSQL clusters.

Run with Python after installing each repo's requirements in a separate venv.
Pass the directory containing PostgreSQL's initdb, pg_ctl and createdb via
--pg-bin. pgserver also supplies these binaries on Linux.
"""

import argparse
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlsplit
import secrets
import subprocess
import sys
import tempfile

APP = Path(__file__).resolve().parent.parent
APP_URL = 'http://127.0.0.1:5181'
BOOK_URL = 'http://127.0.0.1:5182'
DEMO_PASSWORD = os.environ.get('PREVIEW_DEMO_PASSWORD', 'Preview-only-2026!')
PUBLIC_APP_URL = os.environ.get('PREVIEW_PUBLIC_APP_URL', APP_URL)
PUBLIC_BOOK_URL = os.environ.get('PREVIEW_PUBLIC_BOOK_URL', BOOK_URL)
SETTINGS = """
from config.settings import *
import os
from pathlib import Path

state = Path(os.environ['PREVIEW_STATE'])
OFFICE_SYNTHETIC_STAGE = True
# These settings are imported only by the separate synthetic preview processes.
if os.environ.get('PREVIEW_REMOTE') == '1':
    DEBUG = False
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    STORAGES = {**STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
MIDDLEWARE = ['mobile_staff_preview.PreviewFiles', *MIDDLEWARE]
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = state / 'mail'
PATIENT_FILES_ROOT = state / 'records'
MEDIA_ROOT = state / 'media'
MOBILE_STAFF_BOOK_ORIGIN = 'http://127.0.0.1:5182'
MOBILE_STAFF_IDENTITY_ORIGIN = 'http://127.0.0.1:5181'
AESTHETIC_PACKAGE_RELEASE_INTERNAL_URL = MOBILE_STAFF_IDENTITY_ORIGIN + '/api/mobile/internal/book-package-release/'
MOBILE_STAFF_PACKAGE_CANCEL_URL = MOBILE_STAFF_IDENTITY_ORIGIN + '/api/mobile/internal/staff-cancel-package/'
AESTHETIC_PACKAGE_API_URL = MOBILE_STAFF_IDENTITY_ORIGIN + '/api/mobile/package-booking/'
AESTHETIC_BOOKING_NOTIFICATION_URL = MOBILE_STAFF_IDENTITY_ORIGIN + '/api/mobile/internal/booking-notifications/'
AESTHETIC_REFERRAL_BOOKING_URL = MOBILE_STAFF_IDENTITY_ORIGIN + '/api/mobile/internal/referral-booking/'
"""


class PreviewFiles:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import HttpResponse

        if os.environ['PREVIEW_ROLE'] != 'app' or request.method != 'GET':
            return self.get_response(request)
        web = (APP / 'www').resolve()
        rel = request.path.removeprefix('/')
        target = (web / (rel or 'index.html')).resolve()
        if not target.is_relative_to(web) or not target.is_file():
            return self.get_response(request)
        data = target.read_bytes()
        if target.suffix in {'.js', '.mjs'}:
            data = data.replace(b'https://book.a-esthetic.de', PUBLIC_BOOK_URL.encode())
            data = data.replace(b'https://app.a-esthetic.de', PUBLIC_APP_URL.encode())
            data = data.replace(b'https://esthetic.smarbiz.sbs', PUBLIC_APP_URL.encode())
            data = data.replace(b'https://office.a-esthetic.de', PUBLIC_APP_URL.encode())
        response = HttpResponse(data, content_type=mimetypes.guess_type(target)[0] or 'application/octet-stream')
        response['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            f"connect-src 'self' {PUBLIC_BOOK_URL}; img-src 'self' data: blob:; "
            "frame-src 'none'; form-action 'self'; object-src 'none'; base-uri 'none'"
        )
        response['Cache-Control'] = 'no-store'
        return response


def _guard(event, args):
    if event == 'socket.connect':
        address = args[1]
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1'):
            raise PermissionError('Preview blocks outbound connections.')
    if event == 'socket.getaddrinfo' and args[0] not in (None, '127.0.0.1', '::1', 'localhost'):
        raise PermissionError('Preview blocks external DNS resolution.')


def app_seed():
    from django.contrib.auth.models import Group, User
    from django.contrib.sites.models import Site
    from django.utils import timezone
    from platform_app import account_onboarding
    from platform_app.models import MemberPackage, PackageDefinition, UserProfile
    from datetime import timedelta

    account_onboarding.MAIL_RELAY_URL = BOOK_URL + '/api/internal/app-mail/'
    Site.objects.filter(pk=1).update(domain='127.0.0.1:5181', name='A+ Esthetic Vorschau')
    for handle, first, last, role in (
        ('admin', 'Mara', 'Winter', 'admin'), ('doctor', 'Qamar', 'Hameed', 'specialist'),
        ('customer', 'Nora', 'Berg', 'customer'),
    ):
        user, created = User.objects.get_or_create(username=handle, defaults={
            'email': handle + '@example.test', 'first_name': first, 'last_name': last,
            'is_staff': role != 'customer', 'is_superuser': handle == 'admin',
        })
        if created or os.environ.get('PREVIEW_REMOTE') == '1':
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=['password'])
            if created:
                UserProfile.objects.update_or_create(user=user, defaults={'role': role, 'salutation': 'divers'})
        if handle == 'doctor':
            user.groups.add(Group.objects.get_or_create(name='aesthetic_qamar_doctor')[0])
        if handle == 'customer' and created:
            package = PackageDefinition.objects.create(
                name='Laser Paket', sessions=5, validity_days=90,
            )
            MemberPackage.objects.create(
                user=user, definition=package, remaining_sessions=5, expires_at=timezone.localdate()+timedelta(days=90),
            )


def book_seed():
    from datetime import datetime, time, timedelta
    from django.contrib.auth.models import User
    from django.utils import timezone
    from booking.models import Appointment, BlockedPeriod, Customer, PatientRecord, Service, StaffMember, WorkingHour

    if StaffMember.objects.filter(display_name='Mara Winter').exists():
        if os.environ.get('PREVIEW_REMOTE') == '1':
            existing = User.objects.filter(username='preview', is_superuser=True).first()
            if existing:
                existing.set_password(DEMO_PASSWORD)
                existing.save(update_fields=['password'])
        return
    User.objects.create_superuser(username='preview', email='desktop@example.test', password=DEMO_PASSWORD)
    doctor = StaffMember.objects.get_or_create(display_name='Qamar Hameed', defaults={'role':'doctor'})[0]
    # Keep this synthetic workspace available for named clinician testing.
    BlockedPeriod.objects.filter(staff=doctor, reason__contains='Keine Online-Termine bis 31.12.2026').delete()
    specialist = StaffMember.objects.create(display_name='Mara Winter',role='specialist')
    service = Service.objects.create(name='Laser Haarentfernung',slug='preview-laser',duration_minutes=45,buffer_minutes=0)
    visit = Service.objects.create(name='Ästhetische Beratung',slug='preview-consultation',duration_minutes=30,buffer_minutes=0)
    doctor.services.add(visit)
    specialist.services.add(service, visit)
    for provider in (specialist, doctor):
        for weekday in range(7):
            WorkingHour.objects.get_or_create(staff=provider, weekday=weekday, start_time=time(9), defaults={'end_time':time(19)})
    names = [('Nora','Berg','customer'), ('Lea','Sommer','lea'), ('Jonas','Feld','jonas'), ('Mila','Stein','mila')]
    people = [Customer.objects.create(first_name=f,last_name=l,email=e+'@example.test') for f,l,e in names]
    date = timezone.localdate()
    historical = timezone.make_aware(datetime.combine(date - timedelta(days=7), time(11)))
    Appointment.objects.create(
        customer=people[0], staff=specialist, service=visit, starts_at=historical,
        ends_at=historical+timedelta(minutes=visit.duration_minutes),
        status='completed', source='admin',
    )
    for offset in range(5):
        day = date + timedelta(days=offset)
        start = timezone.make_aware(datetime.combine(day,time(10)))
        for index, (staff, treatment) in enumerate(((specialist,service),(doctor,visit),(specialist,visit))):
            at = start + timedelta(minutes=index*90)
            patient = people[3] if index == 1 else people[(offset+index)%3]
            item = Appointment.objects.create(customer=patient,staff=staff,service=treatment,starts_at=at,
                ends_at=at+timedelta(minutes=treatment.duration_minutes),status='confirmed' if index < 2 else 'new',source='admin')
            if offset == 0 and index == 1:
                PatientRecord.objects.create(customer=patient,appointment=item,kind='note',title='Erstgespräch',note='Synthetischer Akteneintrag.')
        at = start + timedelta(hours=4)
        BlockedPeriod.objects.create(staff=specialist,starts_at=at,ends_at=at+timedelta(hours=1),reason='[BLOCKNOTE][STAFF] Mittagspause')


def child(argv):
    sys.addaudithook(_guard)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'preview_settings'
    from django import setup
    from django.core.management import execute_from_command_line

    setup()
    role = os.environ['PREVIEW_ROLE']
    if role == 'app':
        from platform_app import account_onboarding, public_intake
        account_onboarding.MAIL_RELAY_URL = BOOK_URL + '/api/internal/app-mail/'
        public_intake.BOOK_INTAKE_URL = BOOK_URL + '/api/internal/patient-intake/ingest/'
    if argv[0] == 'seed':
        (app_seed if role == 'app' else book_seed)()
    else:
        execute_from_command_line(['preview', *argv])


def validate_public_origins(app_url, book_url):
    """Require a pair of explicit, distinct HTTPS staging-only origins."""
    if not app_url and not book_url:
        return APP_URL, BOOK_URL, False
    hosts = []
    for origin in (app_url, book_url):
        if not origin:
            raise ValueError('Both staging origins are required.')
        parsed = urlsplit(origin)
        host = parsed.hostname or ''
        if (parsed.scheme != 'https' or not host or parsed.port is not None or
            parsed.username or parsed.password or parsed.path not in ('', '/') or
            parsed.query or parsed.fragment or
            not any(label.startswith(('stage', 'preview', 'staging')) for label in host.split('.'))):
            raise ValueError('Use explicit staging/preview HTTPS hostnames, never production.')
        if host in {'a-esthetic.de','app.a-esthetic.de','book.a-esthetic.de','office.a-esthetic.de','esthetic.smarbiz.sbs'}:
            raise ValueError('Production origins are prohibited.')
        hosts.append(host)
    if hosts[0] == hosts[1]:
        raise ValueError('Use distinct app and Book staging origins.')
    return app_url.rstrip('/'), book_url.rstrip('/'), True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--book', type=Path, required=True)
    parser.add_argument('--app-python', type=Path, required=True)
    parser.add_argument('--book-python', type=Path, required=True)
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--state', type=Path)
    parser.add_argument('--public-app-url')
    parser.add_argument('--public-book-url')
    args = parser.parse_args()
    public_app, public_book, remote = validate_public_origins(args.public_app_url, args.public_book_url)
    if remote:
        if not args.state:
            parser.error('A dedicated --state directory is required for remote staging.')
        demo_password = os.environ.get('APLUS_STAGE_DEMO_PASSWORD', '')
        if len(demo_password) < 16 or demo_password == 'Preview-only-2026!':
            parser.error('Set a unique staging-only APLUS_STAGE_DEMO_PASSWORD of at least 16 characters.')
    else:
        demo_password = 'Preview-only-2026!'
    state = (args.state or Path(tempfile.mkdtemp(prefix='aesthetic-preview-'))).resolve()
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if remote and state.stat().st_mode & 0o077:
        parser.error('Remote staging state directory must not be accessible to other users.')
    if remote:
        marker = state / 'staging-origins.txt'
        expected = public_app+'\n'+public_book+'\n'
        if marker.exists() and marker.read_text() != expected:
            parser.error('This state directory belongs to another staging origin.')
        if not marker.exists():
            if any((state / (role+'-db') / 'PG_VERSION').exists() for role in ('app','book')):
                parser.error('Never reuse an existing unmarked database for remote staging.')
            marker.write_text(expected)
    (state / 'preview_settings.py').write_text(SETTINGS)
    token = secrets.token_urlsafe(32)
    children = []
    clusters = []
    hosts = ['127.0.0.1','localhost'] + ([urlsplit(public_app).hostname,urlsplit(public_book).hostname] if remote else [])
    env_base = {'PATH':os.environ['PATH'], 'PYTHONUNBUFFERED':'1', 'DJANGO_DEBUG':'1',
                'DJANGO_ALLOWED_HOSTS':','.join(hosts),
                'PREVIEW_PUBLIC_APP_URL':public_app, 'PREVIEW_PUBLIC_BOOK_URL':public_book,
                'PREVIEW_REMOTE':'1' if remote else '0', 'PREVIEW_DEMO_PASSWORD':demo_password,
                'CSRF_TRUSTED_ORIGINS':public_app+','+public_book,
                'DJANGO_CSRF_TRUSTED_ORIGINS':public_app+','+public_book, 'PATIENT_SYNC_TOKEN':token,
                'DJANGO_SECRET_KEY':secrets.token_urlsafe(48), 'PREVIEW_STATE':str(state),
                'BOOKING_CORS_ORIGINS':public_app, 'AESTHETIC_MEMBER_API_URL':APP_URL+'/api/mobile/me/'}
    try:
        for role, repo, python, port in (('book', args.book.resolve(), args.book_python, 5182),
                                         ('app', APP, args.app_python, 5181)):
            cluster = state / (role+'-db')
            db_port = port + 36000
            pg = lambda name: str(args.pg_bin.resolve()/name)
            if not (cluster/'PG_VERSION').is_file():
                subprocess.run([pg('initdb'),'-D',str(cluster),'-U','preview','-A','trust','--no-locale','-E','UTF8'],check=True,stdout=subprocess.DEVNULL)
            subprocess.run([pg('pg_ctl'),'-D',str(cluster),'-l',str(state/(role+'-postgres.log')),
                            '-o',f"-p {db_port} -c listen_addresses=127.0.0.1 -c unix_socket_directories=''",'-w','start'],check=True,stdout=subprocess.DEVNULL)
            clusters.append(cluster)
            env = {
                **env_base, 'PREVIEW_ROLE':role, 'PYTHONPATH':os.pathsep.join((str(repo),str(state),str(APP/'scripts'))),
                'DB_ENGINE':'postgresql', 'DB_NAME':'postgres', 'DB_USER':'preview',
                'DB_HOST':'127.0.0.1','DB_PORT':str(db_port),
                'DATABASE_URL':f'postgresql://preview@127.0.0.1:{db_port}/postgres',
            }
            command = [str(python.absolute()),str(Path(__file__).resolve()),'_child']
            subprocess.run([*command,'migrate','--noinput'],env=env,check=True,cwd=repo,stdout=subprocess.DEVNULL)
            subprocess.run([*command,'seed'],env=env,check=True,cwd=repo)
            log = (state/(role+'.log')).open('a')
            children.append(subprocess.Popen([*command,'runserver',f'127.0.0.1:{port}','--noreload', *(['--insecure'] if remote else [])],
                                             env=env,cwd=repo,stdout=log,stderr=subprocess.STDOUT))
            if role == 'book':
                reconcile = (state/'reconcile.sh')
                import shlex
                line = ['cd',str(repo)]
                cmd = ['env','-i', *(k+'='+v for k,v in env.items()),*command,'reconcile_mobile_cancellations']
                fd = os.open(reconcile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o700)
                with os.fdopen(fd,'w') as out:
                    out.write('#!/bin/sh\n'+shlex.join(line)+' && '+shlex.join(cmd)+'\n')
        print(f'Preview {public_app}  ·  Book {public_book}  ·  Isolated state {state}', flush=True)
        for process in children:
            process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in children:
            process.terminate()
        for process in children:
            process.wait(timeout=15)
        for cluster in reversed(clusters):
            subprocess.run([str(args.pg_bin.resolve()/'pg_ctl'),'-D',str(cluster),'-m','fast','stop'],
                           stdout=subprocess.DEVNULL,check=False)


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '_child':
        child(sys.argv[2:])
    else:
        main()
