#!/usr/bin/env bash
set -euo pipefail
adb install -r "${APLUS_QA_APK:-artifacts/APlus-Esthetic-V4-1.0.55-B61.apk}"
target=${APLUS_QA_OUTPUT:-screenshots/android}
mkdir -p "$target"
fixtures=(qa-fixtures/*.json)
if [[ -n ${APLUS_QA_FIXTURES:-} ]]; then read -r -a fixtures <<< "$APLUS_QA_FIXTURES"; fi
for fixture in "${fixtures[@]}"; do
  adb shell am force-stop de.aplusesthetic.app
  payload=$(base64 -w0 "$fixture")
  adb shell am start -W -n de.aplusesthetic.app/.MainActivity --es APLUS_NATIVE_QA_FIXTURE "$payload"
  expected=$(python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))["screen"]; print(("Choose patient" if s.get("language")=="en" else "Patient auswählen") if s.get("openChoice")=="customer_id" else s.get("hero") or s["title"])' "$fixture")
  matched=false
  for attempt in 1 2 3 4 5 6; do
    sleep 1
    adb shell uiautomator dump /sdcard/aplus-qa.xml >/dev/null 2>&1 || continue
    xml=$(adb exec-out cat /sdcard/aplus-qa.xml)
    if [[ "$xml" == *"$expected"* ]]; then matched=true; break; fi
  done
  if [ "$matched" != true ]; then echo "Native screen did not load: $(basename "$fixture") (expected synthetic label: $expected)" >&2; adb exec-out screencap -p > "$target/$(basename "$fixture" .json)-failed.png"; exit 1; fi
  adb exec-out screencap -p > "$target/$(basename "$fixture" .json).png"
done
