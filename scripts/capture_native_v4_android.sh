#!/usr/bin/env bash
set -euo pipefail
apk="${APLUS_QA_APK:-}"
if [[ -z "$apk" ]]; then
  mapfile -t packages < <(find artifacts -maxdepth 1 -type f -name 'APlus-Esthetic-V4-*-B*.apk' | sort)
  if [[ ${#packages[@]} -ne 1 ]]; then echo "Expected exactly one versioned QA APK; found ${#packages[@]}" >&2; exit 1; fi
  apk="${packages[0]}"
fi
test -s "$apk"
adb install -r "$apk"
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
  for attempt in $(seq 1 16); do
    sleep 1
    adb shell uiautomator dump /sdcard/aplus-qa.xml >/dev/null 2>&1 || continue
    xml=$(adb exec-out cat /sdcard/aplus-qa.xml)
    # Only dismiss the emulator launcher ANR, never an ANR in the app under test.
    if [[ "$xml" == *"Quickstep"* && "$xml" == *"isn't responding"* ]]; then
      xy=$(printf '%s' "$xml" | python3 -c 'import sys,xml.etree.ElementTree as E,re; root=E.fromstring(sys.stdin.read()); a=next((n for n in root.iter("node") if n.get("text")=="Close app"),None); b=list(map(int,re.findall(r"\d+",a.get("bounds","")))) if a is not None else []; print((str((b[0]+b[2])//2)+" "+str((b[1]+b[3])//2)) if len(b)==4 else "")')
      if [[ -n "$xy" ]]; then echo "Recovered unrelated emulator Quickstep ANR"; adb shell input tap $xy; fi
      continue
    fi
    if [[ "$xml" == *"$expected"* ]]; then matched=true; break; fi
  done
  if [ "$matched" != true ]; then echo "Native screen did not load: $(basename "$fixture") (expected synthetic label: $expected)" >&2; adb exec-out screencap -p > "$target/$(basename "$fixture" .json)-failed.png"; exit 1; fi
  if [[ "$(basename "$fixture")" == "02a-calendar-navigation.json" ]]; then
    adb logcat -d -s APlusCalendarQA:I '*:S' | grep -F 'PASS B62 calendar header and native root retained across day/week updates'
  fi
  adb exec-out screencap -p > "$target/$(basename "$fixture" .json).png"
  if [[ "$(basename "$fixture")" == "02b-calendar-week.json" ]]; then
    python3 scripts/test_native_calendar_swipe.py "$target/02b-calendar-week.png"
  fi
  if [[ "$(basename "$fixture")" == "13-patient-profile.json" ]]; then
    adb shell input keyevent KEYCODE_HOME
    adb shell am start -W -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n de.aplusesthetic.app/.MainActivity
    adb shell uiautomator dump /sdcard/aplus-qa.xml >/dev/null
    adb exec-out cat /sdcard/aplus-qa.xml | grep -Fq "$expected"
    adb exec-out screencap -p > "$target/13-patient-profile-resumed.png"
    python3 - "$target/13-patient-profile.png" "$target/13-patient-profile-resumed.png" <<'PY'
import sys
from PIL import Image, ImageStat

for filename in sys.argv[1:]:
    with Image.open(filename) as image:
        crop = image.crop((0, image.height // 8, image.width, image.height * 7 // 8)).convert('L')
        stats = ImageStat.Stat(crop)
        assert stats.median[0] > 120 and stats.stddev[0] > 8, f'Native screenshot is blank: {filename}'
print('PASS: foreground staff screenshots before and after switching apps')
PY
  fi
done
