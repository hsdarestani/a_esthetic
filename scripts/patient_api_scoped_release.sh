#!/usr/bin/env bash
# Preserve the existing runtime configuration, static files, accounts and data.
set -euo pipefail
umask 077
bundle=$1
target=$2
root=/opt/a-esthetic-mobile
service=a-esthetic-mobile.service
env_file=$root/mobile.env
unit=/etc/systemd/system/$service
backups=$root/remediation-rollbacks
install -d -m 0700 "$backups"
exec 9>"$backups/release.lock"
flock -n 9
test -f "$env_file" && test ! -L "$env_file"
test -f "$unit"
systemctl is-active --quiet "$service"
snapshot=$(mktemp -d "$backups/patient-api.XXXXXXXX")
fingerprint() { sha256sum "$env_file" "$unit"; stat -c '%a %u %g' "$env_file" "$unit"; }
fingerprint > "$snapshot/config.before"

while read -r old new path; do
  case "$path" in p0_app/*|platform_app/*|templates/office/*) ;; *) exit 1;; esac
  [[ "$path" != *..* && ! -L "$root/$path" ]]
  test "$(sha256sum "$bundle/files/$path" | cut -d' ' -f1)" = "$new"
  if [[ "$old" == absent ]]; then
    test ! -e "$root/$path" || { echo 'Unexpected existing release file; nothing changed.'; exit 1; }
  else
    test -f "$root/$path" && test "$(sha256sum "$root/$path" | cut -d' ' -f1)" = "$old" || {
      echo 'Unexpected baseline file; nothing changed.'; exit 1;
    }
    mkdir -p "$snapshot/files/$(dirname "$path")"
    cp -a "$root/$path" "$snapshot/files/$path"
  fi
done < "$bundle/manifest"
cp "$bundle/manifest" "$snapshot/manifest"
cutover=0
rollback() {
  result=$?
  if (( result != 0 && cutover )); then
    systemctl stop "$service" || true
    while read -r old new path; do
      if [[ "$old" == absent ]]; then
        rm -f -- "$root/$path"
      else
        cp -a "$snapshot/files/$path" "$root/$path"
      fi
    done < "$snapshot/manifest"
    systemctl restart "$service" && systemctl is-active --quiet "$service" && echo 'Patient API source restored; additive schema retained.' || echo 'Patient API rollback needs operator review.' >&2
  fi
  exit "$result"
}
trap rollback EXIT
set -a
source "$env_file"
set +a
cd "$root"
python=$root/venv/bin/python
test -x "$python"
cutover=1
systemctl stop "$service"
while read -r old new path; do
  mkdir -p "$(dirname "$root/$path")"
  if [[ "$old" == absent ]]; then
    install -m 0644 "$bundle/files/$path" "$root/$path"
  else
    cp "$bundle/files/$path" "$root/$path"
  fi
done < "$snapshot/manifest"

# Check only the reviewed additive schema changes, without dumping DB contents.
if ! "$python" manage.py shell > "$snapshot/validation.log" 2>&1 <<'PY'
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
e = MigrationExecutor(connection)
assert ('platform_app', '0007_goae_agreement_precision') in e.loader.applied_migrations
allowed = {
    ('platform_app', '0008_goae_draft_request'),
    ('platform_app', '0006_native_office_identity_and_visit'),
    ('platform_app', '0007_office_intake_review'),
    ('platform_app', '0008_goae_draft_revision'),
    ('platform_app', '0009_public_intake_forms'),
    ('p0_app', '0010_package_booking_lifecycle'),
}
plan = e.migration_plan(e.loader.graph.leaf_nodes())
assert all(not backwards and (m.app_label, m.name) in allowed for m, backwards in plan)
PY
then echo 'Unexpected migration plan; restoring source.'; exit 1; fi
if ! "$python" manage.py check >> "$snapshot/validation.log" 2>&1 || ! "$python" manage.py migrate --noinput >> "$snapshot/validation.log" 2>&1; then
  echo 'Patient API migration or system check failed.'; exit 1
fi
"$python" manage.py shell >> "$snapshot/validation.log" 2>&1 <<'PY'
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
e = MigrationExecutor(connection)
assert ('platform_app', '0008_goae_draft_request') in e.loader.applied_migrations
assert not e.migration_plan(e.loader.graph.leaf_nodes())
PY
fingerprint > "$snapshot/config.after"
cmp -s "$snapshot/config.before" "$snapshot/config.after"
systemctl restart "$service"
for attempt in {1..12}; do
  code=$(curl -s --max-time 8 -o /dev/null -w '%{http_code}' https://app.a-esthetic.de/api/mobile/staff/session/ || true)
  if systemctl is-active --quiet "$service" && [[ "$code" == 401 ]]; then
    echo "PATIENT_API_DEPLOYED=$target"
    echo 'PATIENT_STAFF_ANONYMOUS=401; ADDITIVE_MIGRATIONS=APPLIED; CONFIG=PRESERVED'
    exit 0
  fi
  sleep 2
done
echo 'Patient API health did not return the expected anonymous response.'
exit 1
