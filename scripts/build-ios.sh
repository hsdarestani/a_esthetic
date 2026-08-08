#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "iOS builds require the Publisher macOS agent." >&2
  exit 2
fi

python3 scripts/store_positioning_check.py

if [ ! -d node_modules ]; then
  if [ -f package-lock.json ]; then npm ci; else npm install; fi
fi

if [ ! -d ios ]; then
  npx cap add ios
fi
npx cap sync ios

npx @capacitor/assets generate --ios \
  --iconBackgroundColor '#000000' \
  --iconBackgroundColorDark '#000000' \
  --splashBackgroundColor '#000000' \
  --splashBackgroundColorDark '#000000' \
  --logoSplashScale 0.34

mkdir -p artifacts build/ios
ARCHIVE="$ROOT/build/ios/AEsthetic.xcarchive"
EXPORT_DIR="$ROOT/build/ios/export"
VERSION="${APP_VERSION_NAME:-${APP_VERSION:-1.0.0}}"
BUILD="${APP_BUILD_NUMBER:-${BUILD_NUMBER:-1}}"
TEAM_ID="${APPLE_TEAM_ID:-${IOS_TEAM_ID:-}}"
AUTH_KEY_PATH="${APPLE_AUTH_KEY_PATH:-${APPLE_API_KEY_PATH:-}}"

# Capacitor 8 may generate a Swift Package Manager project without an
# .xcworkspace. Support both SPM (.xcodeproj) and CocoaPods (.xcworkspace)
# layouts so the Publisher build remains deterministic across Capacitor updates.
if [ -d ios/App/App.xcworkspace ]; then
  XCODE_CONTAINER=(-workspace ios/App/App.xcworkspace)
elif [ -d ios/App/App.xcodeproj ]; then
  XCODE_CONTAINER=(-project ios/App/App.xcodeproj)
else
  echo "Neither ios/App/App.xcworkspace nor ios/App/App.xcodeproj exists after cap sync." >&2
  find ios -maxdepth 3 -print >&2 || true
  exit 4
fi

XCODE_ARGS=(
  "${XCODE_CONTAINER[@]}"
  -scheme App
  -configuration Release
  -destination generic/platform=iOS
  -archivePath "$ARCHIVE"
  MARKETING_VERSION="$VERSION"
  CURRENT_PROJECT_VERSION="$BUILD"
  CODE_SIGN_STYLE=Automatic
  TARGETED_DEVICE_FAMILY=1
)

if [ -n "$TEAM_ID" ]; then
  XCODE_ARGS+=(DEVELOPMENT_TEAM="$TEAM_ID")
fi

if [ -n "$AUTH_KEY_PATH" ] && [ -n "${APPLE_KEY_ID:-}" ] && [ -n "${APPLE_ISSUER_ID:-}" ]; then
  XCODE_ARGS+=(
    -allowProvisioningUpdates
    -authenticationKeyPath "$AUTH_KEY_PATH"
    -authenticationKeyID "$APPLE_KEY_ID"
    -authenticationKeyIssuerID "$APPLE_ISSUER_ID"
  )
elif [ "${IOS_ALLOW_PROVISIONING_UPDATES:-0}" = "1" ]; then
  XCODE_ARGS+=(-allowProvisioningUpdates)
fi

xcodebuild "${XCODE_ARGS[@]}" clean archive

EXPORT_PLIST="$ROOT/build/ios/ExportOptions.plist"
if [ -n "${IOS_EXPORT_OPTIONS_PLIST_BASE64:-}" ]; then
  printf '%s' "$IOS_EXPORT_OPTIONS_PLIST_BASE64" | base64 --decode > "$EXPORT_PLIST"
else
  TEAM_LINE=""
  if [ -n "$TEAM_ID" ]; then
    TEAM_LINE="<key>teamID</key><string>${TEAM_ID}</string>"
  fi
  cat > "$EXPORT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>method</key><string>app-store-connect</string>
<key>signingStyle</key><string>automatic</string>
<key>stripSwiftSymbols</key><true/>
<key>uploadSymbols</key><true/>
${TEAM_LINE}
</dict></plist>
PLIST
fi

rm -rf "$EXPORT_DIR"
EXPORT_ARGS=(
  -exportArchive
  -archivePath "$ARCHIVE"
  -exportPath "$EXPORT_DIR"
  -exportOptionsPlist "$EXPORT_PLIST"
)
if [ -n "$AUTH_KEY_PATH" ] && [ -n "${APPLE_KEY_ID:-}" ] && [ -n "${APPLE_ISSUER_ID:-}" ]; then
  EXPORT_ARGS+=(
    -allowProvisioningUpdates
    -authenticationKeyPath "$AUTH_KEY_PATH"
    -authenticationKeyID "$APPLE_KEY_ID"
    -authenticationKeyIssuerID "$APPLE_ISSUER_ID"
  )
fi
xcodebuild "${EXPORT_ARGS[@]}"

IPA="$(find "$EXPORT_DIR" -name '*.ipa' -type f | head -n 1)"
if [ -z "$IPA" ]; then
  echo "No IPA was produced." >&2
  exit 3
fi
cp "$IPA" artifacts/a-esthetic.ipa

echo "iOS artifact: $ROOT/artifacts/a-esthetic.ipa"
