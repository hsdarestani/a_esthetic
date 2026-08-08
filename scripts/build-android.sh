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

# Generate launcher/adaptive icons and splash assets from the official A+ Esthetic logo.
npx @capacitor/assets generate --android \
  --iconBackgroundColor '#000000' \
  --iconBackgroundColorDark '#000000' \
  --splashBackgroundColor '#000000' \
  --splashBackgroundColorDark '#000000' \
  --logoSplashScale 0.34

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
     [ -n "${ANDROID_KEYSTORE_PASSWORD:-}" ] && \
     [ -n "${ANDROID_KEY_ALIAS:-}" ] && \
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
