#!/usr/bin/env bash
# Label-only production hotfix. Preserve both databases, Book and existing app worker.
set -Eeuo pipefail
umask 077
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || { echo 'Expected 40-digit source commit'; exit 1; }
SHA="$1"
BASE=/opt/a-esthetic-mobile
OLD="$BASE/releases/0ef54714a2a1fb476061463b56a3515d73d34cae"
NEW="$BASE/releases/patient-labels-$SHA"
UNIT="aesthetic-native-patients-$(echo "$SHA" | cut -c1-10).service"
APP_CONF=/etc/nginx/sites-enabled/a-esthetic-app.conf
OFFICE_CONF=/etc/nginx/sites-enabled/a-esthetic-office.conf
BACK="$BASE/native-release-backups/patient-labels-$(date -u +%Y%m%dT%H%M%SZ)"
SUCCESS=0
[[ $(id -u) == 0 ]] || { echo 'Deployment requires root'; exit 1; }
[[ -d "$OLD" && ! -e "$NEW" && -s /tmp/aesthetic-patient-labels.tgz ]] || { echo 'Missing verified release or files'; exit 1; }
[[ -x "$BASE/venv/bin/gunicorn" && -f "$BASE/mobile.env" ]] || { echo 'Missing current runtime'; exit 1; }
systemctl is-active --quiet aesthetic-native-app-0ef54714a2.service || { echo 'Original native production worker not active'; exit 1; }
for conf in "$APP_CONF" "$OFFICE_CONF"; do
  grep -q '127.0.0.1:8771' "$conf" || { echo "Unexpected current routing in $conf"; exit 1; }
done
ss -ltn '( sport = :8772 )' | grep -q LISTEN && { echo 'New candidate port occupied'; exit 1; }
mkdir -p "$BACK"
chmod 0700 "$BACK"
cp -p "$APP_CONF" "$BACK/app.conf"
cp -p "$OFFICE_CONF" "$BACK/office.conf"
rollback() {
  echo 'PATIENT LABEL RELEASE FAILED — returning existing app/office upstreams'
  cp -p "$BACK/app.conf" "$APP_CONF" || true
  cp -p "$BACK/office.conf" "$OFFICE_CONF" || true
  nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  systemctl stop "$UNIT" 2>/dev/null || true
}
trap 'if [[ "$SUCCESS" != 1 ]]; then rollback; fi' EXIT
cp -a "$OLD" "$NEW"
tar -xzf /tmp/aesthetic-patient-labels.tgz -C "$NEW"
if grep -RInE 'Kunden|Kunde|Kundin' "$NEW/templates/office" "$NEW/www/book-admin.js" "$NEW/www/book-admin-v2.js" "$NEW/www/ops.js"; then
  echo 'Old Kunde terms remain in updated UI'; exit 1
fi
(
 cd "$NEW"; set -a; source "$BASE/mobile.env"; set +a
 export DJANGO_SETTINGS_MODULE=production_native_settings PYTHONPATH="$NEW"
 "$BASE/venv/bin/python" manage.py check
)
cat > "/etc/systemd/system/$UNIT" <<EOF
[Unit]
Description=A+ Esthetic Patient-labelled mobile Django application
After=network.target
[Service]
WorkingDirectory=$NEW
EnvironmentFile=$BASE/mobile.env
Environment=DJANGO_SETTINGS_MODULE=production_native_settings
Environment=PYTHONPATH=$NEW
ExecStart=$BASE/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8772 --workers 1 --timeout 60
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl start "$UNIT"
for url in /office/ /api/mobile/staff/session/; do
  code=''
  for i in $(seq 1 15); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 -H 'Host: office.a-esthetic.de' "http://127.0.0.1:8772$url" || true)
    if [[ "$code" =~ ^(200|401|403)$ ]]; then break; fi
    sleep 1
  done
  [[ "$code" =~ ^(200|401|403)$ ]] || { echo "Candidate cannot serve $url: HTTP=$code"; exit 1; }
done
# Change only the current app/Office upstream. Preserve Book port and all old workers.
python3 - <<'PY'
from pathlib import Path
for path in ('/etc/nginx/sites-enabled/a-esthetic-app.conf','/etc/nginx/sites-enabled/a-esthetic-office.conf'):
    target=Path(path).resolve(strict=True)
    old=target.read_text()
    assert old.count('127.0.0.1:8771')>0 and '127.0.0.1:8772' not in old
    tmp=target.with_name(target.name+'.patient-labels-tmp')
    tmp.write_text(old.replace('127.0.0.1:8771','127.0.0.1:8772'))
    tmp.chmod(target.stat().st_mode)
    tmp.replace(target)
PY
nginx -t
systemctl reload nginx
for url in https://office.a-esthetic.de/office/ https://app.a-esthetic.de/api/mobile/staff/session/; do
  ok=0
  for try in $(seq 1 10); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$url" || true)
    if [[ "$code" =~ ^(200|401|403)$ ]]; then ok=1; break; fi
    sleep 2
  done
  [[ "$ok" == 1 ]] || { echo "New public route failed: $url HTTP=$code"; exit 1; }
  echo "PUBLIC_PATIENT_LABEL_OK $url HTTP=$code"
done
systemctl is-active --quiet "$UNIT"
systemctl is-active --quiet aesthetic-book
SUCCESS=1
echo "PATIENT_LABELS_PRODUCTION_SUCCESS commit=$SHA"
echo 'Existing workers, Book and databases preserved as rollback paths.'
