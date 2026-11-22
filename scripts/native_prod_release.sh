#!/usr/bin/env bash
# Blue/green release. Live Book checkout, media, patient files and existing workers untouched.
set -Eeuo pipefail
umask 077
[[ $# -eq 2 && "$1" =~ ^[0-9a-f]{40}$ && "$2" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid release SHAs'; exit 1; }
[[ $(id -u) -eq 0 ]] || { echo 'Root deployment permissions required'; exit 1; }
A_SHA="$1"; B_SHA="$2"; A_ROOT=/opt/a-esthetic-mobile; B_ROOT=/opt/aesthetic-book
A="$A_ROOT/releases/$A_SHA"; B="$B_ROOT/releases/$B_SHA"
BACK="$A_ROOT/native-release-backups/$(date -u +%Y%m%dT%H%M%SZ)"
A_UNIT="aesthetic-native-app-$(echo "$A_SHA" | cut -c1-10).service"
B_UNIT="aesthetic-native-book-$(echo "$B_SHA" | cut -c1-10).service"
A_CONF=/etc/nginx/sites-enabled/a-esthetic-app.conf
O_CONF=/etc/nginx/sites-enabled/a-esthetic-office.conf
B_CONF=/etc/nginx/sites-enabled/aesthetic-book.conf
revert() {
  echo "RELEASE FAILED: restore nginx routes; leave original production workers serving"
  for item in "app:$A_CONF" "office:$O_CONF" "book:$B_CONF"; do
    key=$(echo "$item" | cut -d: -f1)
    dest=$(echo "$item" | cut -d: -f2-)
    if [[ -f "$BACK/nginx/$key" ]]; then cp -f "$BACK/nginx/$key" "$dest" || true; fi
  done
  nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  systemctl stop "$A_UNIT" 2>/dev/null || true
  systemctl stop "$B_UNIT" 2>/dev/null || true
  echo 'DB backups retained. Additive migrations are intentionally not reversed.'
}
trap revert ERR
for p in /tmp/aesthetic-native-app.tgz /tmp/aesthetic-native-book.tgz "$A_ROOT/db.sqlite3" "$A_ROOT/mobile.env" /etc/aesthetic-book.env "$A_CONF" "$O_CONF" "$B_CONF"; do
  [[ -f "$p" ]] || { echo "Required file missing: $p"; exit 1; }
done
for p in "$A_ROOT/venv/bin/gunicorn" "$B_ROOT/venv/bin/gunicorn"; do [[ -x "$p" ]] || { echo "Missing gunicorn $p"; exit 1; }; done
for port in 8018 8771; do
  if ss -ltn "( sport = :$port )" | grep -q LISTEN; then echo "Candidate port busy: $port"; exit 1; fi
done
[[ ! -e "$A" && ! -e "$B" ]] || { echo 'Candidate release directory already exists'; exit 1; }
mkdir -p "$BACK/nginx" "$A" "$B"
# The non-root Book worker must traverse the release parent without seeing other files.
chmod 0751 "$B_ROOT/releases"
chmod 0700 "$BACK"
cp -p "$A_CONF" "$BACK/nginx/app"
cp -p "$O_CONF" "$BACK/nginx/office"
cp -p "$B_CONF" "$BACK/nginx/book"
echo 'Create consistent SQLite and PostgreSQL backups before any migration'
APP_DB="$A_ROOT/db.sqlite3" DB_BACK="$BACK/app-before.sqlite3" python3 - <<'PY'
import os,sqlite3
a=sqlite3.connect('file:'+os.environ['APP_DB']+'?mode=ro',uri=True)
b=sqlite3.connect(os.environ['DB_BACK'])
a.backup(b)
assert b.execute('PRAGMA quick_check').fetchone()[0]=='ok'
a.close();b.close()
PY
runuser -u postgres -- pg_dump -Fc aestheticbook > "$BACK/book-before.dump"
test -s "$BACK/book-before.dump"
if runuser -u postgres -- psql -Atq aestheticbook -c "select to_regclass('public.booking_patientidentitydecision')" | grep -q booking_patientidentitydecision; then
  count=$(runuser -u postgres -- psql -Atq aestheticbook -c "select count(*) from booking_patientidentitydecision where reviewed_by_id is null")
  [[ "$count" == 0 ]] || { echo "Identity decisions require manual review before constraint migration: count=$count"; exit 1; }
fi
tar -xzf /tmp/aesthetic-native-app.tgz -C "$A"
tar -xzf /tmp/aesthetic-native-book.tgz -C "$B"
test -f "$A/manage.py"
test -f "$B/manage.py"
# Explicit absolute DB location: SQLite WAL/SHM must never split across symlinked directories.
printf "from config.settings import *\nDATABASES['default']['NAME']='/opt/a-esthetic-mobile/db.sqlite3'\n" > "$A/production_native_settings.py"
for base in media; do
  if [[ -d "$A_ROOT/$base" && ! -e "$A/$base" ]]; then ln -s "$A_ROOT/$base" "$A/$base"; fi
  if [[ -d "$B_ROOT/app/$base" && ! -e "$B/$base" ]]; then ln -s "$B_ROOT/app/$base" "$B/$base"; fi
done
chown -R aestheticbook:aestheticbook "$B"
chmod 0750 "$B"
(
  cd "$A"; set -a; source "$A_ROOT/mobile.env"; set +a
  export DJANGO_SETTINGS_MODULE=production_native_settings PYTHONPATH="$A:$A_ROOT/vendor"
  "$A_ROOT/venv/bin/python" manage.py check
  "$A_ROOT/venv/bin/python" manage.py makemigrations --check --dry-run
)
runuser -u aestheticbook -- bash -c "set -a; source /etc/aesthetic-book.env; set +a; cd '$B'; '$B_ROOT/venv/bin/python' manage.py check && '$B_ROOT/venv/bin/python' manage.py makemigrations --check --dry-run"
echo 'Applying additive Book and A+ migrations; current workers stay active'
runuser -u aestheticbook -- bash -c "set -a; source /etc/aesthetic-book.env; set +a; cd '$B'; '$B_ROOT/venv/bin/python' manage.py migrate --noinput && '$B_ROOT/venv/bin/python' manage.py collectstatic --noinput"
(
  cd "$A"; set -a; source "$A_ROOT/mobile.env"; set +a
  export DJANGO_SETTINGS_MODULE=production_native_settings PYTHONPATH="$A:$A_ROOT/vendor"
  "$A_ROOT/venv/bin/python" manage.py migrate --noinput
  "$A_ROOT/venv/bin/python" manage.py collectstatic --noinput
)
cat > "/etc/systemd/system/$B_UNIT" <<EOF
[Unit]
Description=A+ Book native candidate
After=network.target postgresql.service
[Service]
User=aestheticbook
Group=aestheticbook
WorkingDirectory=$B
EnvironmentFile=/etc/aesthetic-book.env
ExecStart=$B_ROOT/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8018 --workers 1 --timeout 60
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
cat > "/etc/systemd/system/$A_UNIT" <<EOF
[Unit]
Description=A+ Esthetic native mobile candidate
After=network.target
[Service]
WorkingDirectory=$A
EnvironmentFile=$A_ROOT/mobile.env
Environment=DJANGO_SETTINGS_MODULE=production_native_settings
Environment=PYTHONPATH=$A:$A_ROOT/vendor
ExecStart=$A_ROOT/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8771 --workers 1 --timeout 60
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl start "$A_UNIT"
systemctl start "$B_UNIT"
check() {
  local host="$1" port="$2" url="$3" code=''
  for i in $(seq 1 20); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 -H "Host: $host" "http://127.0.0.1:$port$url" || true)
    if [[ "$code" =~ ^(200|301|302|303|401|403|405)$ ]]; then echo "Candidate $host $url HTTP=$code"; return 0; fi
    sleep 2
  done
  echo "Candidate failed: $host $url HTTP=$code"; return 1
}
check app.a-esthetic.de 8771 /api/mobile/staff/session/
check office.a-esthetic.de 8771 /office/
check book.a-esthetic.de 8018 /
check book.a-esthetic.de 8018 /api/mobile/staff/overview/
echo 'Switching ONLY app, office and book nginx upstreams to verified candidate workers'
python3 - <<'PY'
from pathlib import Path
for name,old,new in [
 ('a-esthetic-app.conf','http://127.0.0.1:8770','http://127.0.0.1:8771'),
 ('a-esthetic-office.conf','http://127.0.0.1:8770','http://127.0.0.1:8771'),
 ('aesthetic-book.conf','http://127.0.0.1:8017','http://127.0.0.1:8018')]:
 p=Path('/etc/nginx/sites-enabled')/name
 value=p.read_text()
 assert value.count(old)>0 and new not in value,(name,'unexpected route')
 q=p.with_name(name+'.native-tmp')
 q.write_text(value.replace(old,new))
 q.chmod(p.stat().st_mode)
 q.replace(p)
PY
nginx -t
systemctl reload nginx
for url in https://book.a-esthetic.de/ https://office.a-esthetic.de/office/ https://app.a-esthetic.de/api/mobile/staff/session/; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$url" || true)
  [[ "$code" =~ ^(200|301|302|303|401|403|405)$ ]] || { echo "Public smoke failed $url HTTP=$code"; exit 1; }
  echo "PUBLIC_SMOKE_OK $url HTTP=$code"
done
systemctl is-active --quiet a-esthetic-mobile
systemctl is-active --quiet aesthetic-book
systemctl is-active --quiet "$A_UNIT"
systemctl is-active --quiet "$B_UNIT"
trap - ERR
echo "RELEASE_OK app=$A_SHA book=$B_SHA backups=$BACK"
echo 'Original Book checkout, real patient files, and original worker services preserved.'
