#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/store_positioning_check.py

if [ ! -d node_modules ]; then
  if [ -f package-lock.json ]; then npm ci; else npm install; fi
fi

# Publisher's cloud agent materializes the upload key under android/ before a
# custom Capacitor project exists. Preserve those job-scoped files while
# Capacitor creates the actual native project, then restore them.
TMP_SIGNING_DIR=""
if [ ! -f android/gradlew ] && [ -d android ]; then
  if [ -f android/upload-keystore.jks ] || [ -f android/key.properties ]; then
    TMP_SIGNING_DIR="$(mktemp -d)"
    [ ! -f android/upload-keystore.jks ] || mv android/upload-keystore.jks "$TMP_SIGNING_DIR/"
    [ ! -f android/key.properties ] || mv android/key.properties "$TMP_SIGNING_DIR/"
  fi
  rmdir android 2>/dev/null || {
    echo "android/ exists but is not a generated Capacitor project." >&2
    exit 2
  }
fi

if [ ! -f android/gradlew ]; then
  npx cap add android
fi

if [ -n "$TMP_SIGNING_DIR" ]; then
  [ ! -f "$TMP_SIGNING_DIR/upload-keystore.jks" ] || mv "$TMP_SIGNING_DIR/upload-keystore.jks" android/upload-keystore.jks
  [ ! -f "$TMP_SIGNING_DIR/key.properties" ] || mv "$TMP_SIGNING_DIR/key.properties" android/key.properties
  rmdir "$TMP_SIGNING_DIR"
fi

npx cap sync android

# Apply the version supplied by A+ Publisher before Gradle packages the bundle.
python3 scripts/configure_android_release.py

# Use the exact current Play Store artwork, re-encoded as a standard WebP that
# AAPT2 can compile reliably. This avoids the malformed/stale PNG that caused the
# previous Publisher build to fail and also prevents Capacitor's default icon
# from appearing on OEM launchers.
LAUNCHER_SOURCE="$ROOT/assets/appicon.webp"
LAUNCHER_DIR="$ROOT/android/app/src/main/res/drawable-nodpi"
MANIFEST="$ROOT/android/app/src/main/AndroidManifest.xml"

if [ ! -f "$LAUNCHER_SOURCE" ]; then
  echo "Missing A+ Esthetic launcher artwork: $LAUNCHER_SOURCE" >&2
  exit 6
fi
if [ ! -f "$MANIFEST" ]; then
  echo "Missing generated AndroidManifest.xml: $MANIFEST" >&2
  exit 6
fi

mkdir -p "$LAUNCHER_DIR"
rm -f "$LAUNCHER_DIR/launcher_icon.png" "$LAUNCHER_DIR/launcher_icon.webp"
cp "$LAUNCHER_SOURCE" "$LAUNCHER_DIR/launcher_icon.webp"

python3 - <<'PY'
from pathlib import Path
import re

manifest = Path('android/app/src/main/AndroidManifest.xml')
text = manifest.read_text(encoding='utf-8')

if '<application' not in text:
    raise SystemExit('AndroidManifest.xml has no <application> element')

if re.search(r'android:icon="[^"]+"', text):
    text = re.sub(
        r'android:icon="[^"]+"',
        'android:icon="@drawable/launcher_icon"',
        text,
        count=1,
    )
else:
    text = text.replace(
        '<application',
        '<application android:icon="@drawable/launcher_icon"',
        1,
    )

if re.search(r'android:roundIcon="[^"]+"', text):
    text = re.sub(
        r'android:roundIcon="[^"]+"',
        'android:roundIcon="@drawable/launcher_icon"',
        text,
        count=1,
    )
else:
    text = text.replace(
        '<application',
        '<application android:roundIcon="@drawable/launcher_icon"',
        1,
    )

manifest.write_text(text, encoding='utf-8')

if 'android:icon="@drawable/launcher_icon"' not in text:
    raise SystemExit('Failed to set android:icon')
if 'android:roundIcon="@drawable/launcher_icon"' not in text:
    raise SystemExit('Failed to set android:roundIcon')

print('Android manifest launcher references verified.')
PY

echo "Installed AAPT-safe A+ Esthetic Play Store artwork as Android launcher icon."

mkdir -p artifacts

# Publisher Cloud Linux supplies a job-scoped keystore path. Local CI can
# alternatively provide the same key as base64. Neither form is committed.
SIGNING_READY=0
if [ -n "${ANDROID_KEYSTORE_PATH:-}" ] && [ -f "${ANDROID_KEYSTORE_PATH}" ] && \
   [ -n "${ANDROID_KEYSTORE_PASSWORD:-}" ] && [ -n "${ANDROID_KEY_ALIAS:-}" ] && \
   [ -n "${ANDROID_KEY_PASSWORD:-}" ]; then
  export AESTHETIC_KEYSTORE_FILE="$ANDROID_KEYSTORE_PATH"
  SIGNING_READY=1
elif [ -n "${ANDROID_KEYSTORE_BASE64:-}" ] && \
     [ -n "${ANDROID_KEYSTORE_PASSWORD:-}" ] && [ -n "${ANDROID_KEY_ALIAS:-}" ] && \
     [ -n "${ANDROID_KEY_PASSWORD:-}" ]; then
  printf '%s' "$ANDROID_KEYSTORE_BASE64" | base64 --decode > android/app/aesthetic-release.jks
  export AESTHETIC_KEYSTORE_FILE="$ROOT/android/app/aesthetic-release.jks"
  SIGNING_READY=1
fi

if [ "$SIGNING_READY" = "1" ]; then
  python3 scripts/configure_android_signing.py
elif [ "${REQUIRE_ANDROID_SIGNING:-0}" = "1" ]; then
  echo "Android signing credentials are required but missing." >&2
  exit 2
else
  echo "Signing credentials not supplied; creating a release bundle for build verification only."
fi

(
  cd android
  ./gradlew --no-daemon clean bundleRelease
)

AAB="$(find android/app/build/outputs/bundle/release -name '*.aab' -type f | head -n 1)"
if [ -z "$AAB" ]; then
  echo "No release AAB was produced." >&2
  exit 3
fi
cp "$AAB" artifacts/a-esthetic-release.aab

echo "Android artifact: $ROOT/artifacts/a-esthetic-release.aab"
