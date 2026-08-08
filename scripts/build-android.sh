#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/store_positioning_check.py

if [ ! -d node_modules ]; then
  if [ -f package-lock.json ]; then npm ci; else npm install; fi
fi

if [ ! -d android ]; then
  npx cap add android
fi
npx cap sync android

mkdir -p artifacts

# Optional signing contract for Publisher/CI.
# If all four values are present, patch the generated Capacitor project to sign
# the release bundle. The keystore itself is never committed.
if [ -n "${ANDROID_KEYSTORE_BASE64:-}" ] && \
   [ -n "${ANDROID_KEYSTORE_PASSWORD:-}" ] && \
   [ -n "${ANDROID_KEY_ALIAS:-}" ] && \
   [ -n "${ANDROID_KEY_PASSWORD:-}" ]; then
  printf '%s' "$ANDROID_KEYSTORE_BASE64" | base64 --decode > android/app/aesthetic-release.jks
  export AESTHETIC_KEYSTORE_FILE="$ROOT/android/app/aesthetic-release.jks"
  python3 scripts/configure_android_signing.py
elif [ "${REQUIRE_ANDROID_SIGNING:-0}" = "1" ]; then
  echo "Android signing secrets are required but missing." >&2
  exit 2
else
  echo "Signing secrets not supplied; creating an unsigned release bundle for build verification."
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
