#!/usr/bin/env bash
set -euo pipefail
adb install -r artifacts/APlus-Esthetic-V4-1.0.49-B55.apk
mkdir -p screenshots/android
for fixture in qa-fixtures/*.json; do
  adb shell am force-stop de.aplusesthetic.app
  payload=$(base64 -w0 "$fixture")
  adb shell am start -W -n de.aplusesthetic.app/.MainActivity --es APLUS_NATIVE_QA_FIXTURE "$payload"
  sleep 2
  adb exec-out screencap -p > "screenshots/android/$(basename "$fixture" .json).png"
done
