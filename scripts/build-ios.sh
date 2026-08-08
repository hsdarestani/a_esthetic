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

mkdir -p artifacts build/ios
ARCHIVE="$ROOT/build/ios/AEsthetic.xcarchive"
EXPORT_DIR="$ROOT/build/ios/export"
VERSION="${APP_VERSION:-1.0.0}"
BUILD="${BUILD_NUMBER:-1}"

XCODE_ARGS=(
  -workspace ios/App/App.xcworkspace
  -scheme App
  -configuration Release
  -destination generic/platform=iOS
  -archivePath "$ARCHIVE"
  MARKETING_VERSION="$VERSION"
  CURRENT_PROJECT_VERSION="$BUILD"
)

if [ -n "${APPLE_TEAM_ID:-}" ]; then
  XCODE_ARGS+=(DEVELOPMENT_TEAM="$APPLE_TEAM_ID")
fi

if [ "${IOS_ALLOW_PROVISIONING_UPDATES:-0}" = "1" ]; then
  XCODE_ARGS+=(-allowProvisioningUpdates)
fi

xcodebuild "${XCODE_ARGS[@]}" clean archive

EXPORT_PLIST="$ROOT/build/ios/ExportOptions.plist"
if [ -n "${IOS_EXPORT_OPTIONS_PLIST_BASE64:-}" ]; then
  printf '%s' "$IOS_EXPORT_OPTIONS_PLIST_BASE64" | base64 --decode > "$EXPORT_PLIST"
else
  TEAM_LINE=""
  if [ -n "${APPLE_TEAM_ID:-}" ]; then
    TEAM_LINE="<key>teamID</key><string>${APPLE_TEAM_ID}</string>"
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
xcodebuild -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportPath "$EXPORT_DIR" \
  -exportOptionsPlist "$EXPORT_PLIST"

IPA="$(find "$EXPORT_DIR" -name '*.ipa' -type f | head -n 1)"
if [ -z "$IPA" ]; then
  echo "No IPA was produced." >&2
  exit 3
fi
cp "$IPA" artifacts/a-esthetic.ipa

echo "iOS artifact: $ROOT/artifacts/a-esthetic.ipa"
