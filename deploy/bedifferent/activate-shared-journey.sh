#!/usr/bin/env bash
# BE DIFFERENT isolated on the A+ Esthetic VPS; never restart its other apps.
set -euo pipefail
APP=/opt/bedifferent-temp
ENVFILE=/etc/bedifferent-temp.env
SERVICE=bedifferent-temp
test -n "$BD_RUN_ID" && test -n "$BD_EXPECT_SHA"
NEW="$APP/releases/$BD_RUN_ID"
test "$(id -u)" -eq 0
test -L "$APP/current" && test -s "$ENVFILE"
test -d /opt/a-esthetic-mobile && test -d /opt/aesthetic-book
for svc in nginx postgresql a-esthetic-mobile aesthetic-book "$SERVICE"; do systemctl is-active --quiet "$svc"; done
OLD="$(readlink -f "$APP/current")"
case "$OLD" in "$APP"/releases/*) ;; *) echo WRONG_RELEASE_ROOT >&2; exit 1;; esac
test -s "$OLD/server.js"
test -s /tmp/bd-journey-release.tgz
test ! -e "$NEW"
test "$(awk '/MemAvailable/ {print $2}' /proc/meminfo)" -gt 900000
test "$(df -Pk "$APP" | awk 'NR==2 {print $4}')" -gt 1500000
curl -fsS --max-time 10 http://127.0.0.1:3100/api/ready >/dev/null
curl -fsS --max-time 15 https://esthetic.smarbiz.sbs/api/mobile/status/ >/dev/null
curl -fsS --max-time 15 https://book.a-esthetic.de/api/health/ >/dev/null
umask 077
mkdir -p "$NEW"
tar -xzf /tmp/bd-journey-release.tgz -C "$NEW"
test "$(cat "$NEW/.source-sha")" = "$BD_EXPECT_SHA"
test -s "$NEW/server.js"
test -x "$NEW/bin/node"
test -s "$NEW/node_modules/prisma/build/index.js"
test -s "$NEW/prisma/schema.prisma"
chown -R root:root "$NEW"
chmod -R go-w "$NEW"
mkdir -p "$NEW/.next/cache"
chown -R bedifferenttemp:bedifferenttemp "$NEW/.next/cache"
mkdir -p "$APP/backups"
chmod 700 "$APP/backups"
BACKUP="$APP/backups/journey-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$BACKUP"
runuser -u postgres -- pg_dump -Fc -d bedifferent_temp >"$BACKUP/db.dump"
test "$(wc -c < "$BACKUP/db.dump")" -gt 4096
test "$(head -c 5 "$BACKUP/db.dump")" = PGDMP
pg_restore -l "$BACKUP/db.dump" >/dev/null
cp -p "$ENVFILE" "$BACKUP/env"
tar -czf "$BACKUP/data.tar.gz" -C "$APP" data
test -s "$BACKUP/data.tar.gz"
echo BE_DIFFERENT_BACKUP_VERIFIED
changed=0
rollback(){
 rc=$?
 trap - ERR
 if [ "$changed" -eq 1 ]; then
  cp -p "$BACKUP/env" "$ENVFILE" || true
  ln -sfn "$OLD" "$APP/current.next"
  mv -Tf "$APP/current.next" "$APP/current"
  systemctl restart "$SERVICE" || true
 fi
 echo "BE_DIFFERENT_APP_ROLLBACK_ONLY BACKUP=$BACKUP EXIT=$rc" >&2
 exit "$rc"
}
trap rollback ERR
set -a
. "$ENVFILE"
set +a
case "$DATABASE_URL" in *"/bedifferent_temp"*) ;; *) echo WRONG_DB_TARGET >&2; false;; esac
runuser -u bedifferenttemp -- env DATABASE_URL="$DATABASE_URL" "$NEW/bin/node" "$NEW/node_modules/prisma/build/index.js" migrate diff --from-url "$DATABASE_URL" --to-schema-datamodel "$NEW/prisma/schema.prisma" --script >"$BACKUP/schema.sql"
if grep -Eiq '^[[:space:]]*(DROP|TRUNCATE|DELETE)[[:space:]]|ALTER[[:space:]]+TABLE.*DROP' "$BACKUP/schema.sql"; then
 echo DESTRUCTIVE_SQL_BLOCKED >&2
 false
fi
runuser -u bedifferenttemp -- env DATABASE_URL="$DATABASE_URL" "$NEW/bin/node" "$NEW/node_modules/prisma/build/index.js" db push --schema "$NEW/prisma/schema.prisma" --skip-generate
runuser -u bedifferenttemp -- env DATABASE_URL="$DATABASE_URL" "$NEW/bin/node" "$NEW/scripts/backfill-published-journey-snapshots.mjs"
set_flag(){
 key="$1"
 tmp="$(mktemp /etc/bedifferent-temp.env.XXXXXX)"
 grep -v "^$key=" "$ENVFILE" >"$tmp" || true
 printf '%s=true\n' "$key" >>"$tmp"
 chown --reference="$ENVFILE" "$tmp"
 chmod 600 "$tmp"
 mv -f "$tmp" "$ENVFILE"
}
changed=1
for flag in JOURNEY_ONBOARDING_ENABLED JOURNEY_EDITOR_ENABLED JOURNEY_TESTS_ENABLED JOURNEY_OVERVIEW_ENABLED NEXT_PUBLIC_JOURNEY_ONBOARDING_ENABLED NEXT_PUBLIC_JOURNEY_OVERVIEW_ENABLED STEP09_ENABLED; do set_flag "$flag"; done
ln -sfn "$NEW" "$APP/current.next"
mv -Tf "$APP/current.next" "$APP/current"
systemctl restart "$SERVICE"
ready=0
for n in $(seq 1 40); do
 if curl -fsS --max-time 6 http://127.0.0.1:3100/api/ready >"$BACKUP/readiness.json"; then
  if grep -q '"todayCoach":true' "$BACKUP/readiness.json"; then ready=1; break; fi
 fi
 sleep 3
done
test "$ready" -eq 1
for flag in onboarding editor tests overview webOnboarding webOverview todayCoach; do
 grep -q "\"$flag\":true" "$BACKUP/readiness.json"
done
for route in /api/journey/overview /api/journey/tests /api/admin/journeys /api/admin/journey-tests /api/step09/today /api/admin/technique-reviews; do
 code="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:3100$route")"
 [[ "$code" == 401 || "$code" == 403 ]] || { echo "BAD_AUTH_GATE=$route:$code" >&2; false; }
done
for svc in nginx postgresql a-esthetic-mobile aesthetic-book "$SERVICE"; do systemctl is-active --quiet "$svc"; done
curl -fsS --max-time 15 https://esthetic.smarbiz.sbs/api/mobile/status/ >/dev/null
curl -fsS --max-time 15 https://book.a-esthetic.de/api/health/ >/dev/null
test "$(cat "$APP/current/.source-sha")" = "$BD_EXPECT_SHA"
rm -f /tmp/bd-journey-release.tgz
echo "BE_DIFFERENT_SHARED_HOST_RELEASE_OK $BD_EXPECT_SHA"
trap - ERR
