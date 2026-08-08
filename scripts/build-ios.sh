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

# Keep the existing logo-driven launch screen, but always use the dedicated
# finished artwork in assets/appicon.png for the actual iOS AppIcon set.
# @capacitor/assets gives assets/ios/icon.* precedence for the iOS icon.
APP_ICON_SOURCE="$ROOT/assets/appicon.png"
IOS_ICON_DIR="$ROOT/assets/ios"
IOS_ICON_OVERRIDE="$IOS_ICON_DIR/icon.png"
if [ ! -f "$APP_ICON_SOURCE" ]; then
  echo "Missing iOS app icon source: $APP_ICON_SOURCE" >&2
  exit 6
fi
mkdir -p "$IOS_ICON_DIR"
cp "$APP_ICON_SOURCE" "$IOS_ICON_OVERRIDE"
trap 'rm -f "$IOS_ICON_OVERRIDE"; rmdir "$IOS_ICON_DIR" 2>/dev/null || true' EXIT

echo "Using dedicated iOS app icon: assets/appicon.png"
npx @capacitor/assets generate --ios \
  --iconBackgroundColor '#000000' \
  --iconBackgroundColorDark '#000000' \
  --splashBackgroundColor '#000000' \
  --splashBackgroundColorDark '#000000' \
  --logoSplashScale 0.34

# Fail early if the generator did not actually create an iOS AppIcon catalog.
APPICON_SET="$ROOT/ios/App/App/Assets.xcassets/AppIcon.appiconset"
if [ ! -d "$APPICON_SET" ] || [ ! -f "$APPICON_SET/Contents.json" ]; then
  echo "iOS AppIcon asset catalog was not generated." >&2
  exit 7
fi

echo "Generated iOS AppIcon set from assets/appicon.png"

mkdir -p artifacts build/ios
ARCHIVE="$ROOT/build/ios/AEsthetic.xcarchive"
EXPORT_DIR="$ROOT/build/ios/export"
VERSION="${APP_VERSION_NAME:-${APP_VERSION:-1.0.0}}"
BUILD="${APP_BUILD_NUMBER:-${BUILD_NUMBER:-1}}"
TEAM_ID="${APPLE_TEAM_ID:-${IOS_TEAM_ID:-}}"
AUTH_KEY_PATH="${APPLE_AUTH_KEY_PATH:-${APPLE_API_KEY_PATH:-}}"
SIGNING_STYLE="${IOS_SIGNING_STYLE:-Automatic}"
PROFILE_SPECIFIER="${IOS_PROVISIONING_PROFILE_SPECIFIER:-}"
CODE_SIGN_IDENTITY="${IOS_CODE_SIGN_IDENTITY:-Apple Distribution}"
SIGNING_KEYCHAIN="${IOS_SIGNING_KEYCHAIN:-}"
BUNDLE_ID="${IOS_BUNDLE_ID:-de.aplusesthetic.app}"

# Capacitor 8 may generate a Swift Package Manager project without an
# .xcworkspace. Support both SPM (.xcodeproj) and CocoaPods (.xcworkspace).
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
  CODE_SIGN_STYLE="$SIGNING_STYLE"
  TARGETED_DEVICE_FAMILY=1
  PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID"
)

if [ -n "$TEAM_ID" ]; then
  XCODE_ARGS+=(DEVELOPMENT_TEAM="$TEAM_ID")
fi

if [ "$SIGNING_STYLE" = "Manual" ]; then
  if [ -z "$PROFILE_SPECIFIER" ] || [ -z "$SIGNING_KEYCHAIN" ]; then
    echo "Manual iOS signing requires IOS_PROVISIONING_PROFILE_SPECIFIER and IOS_SIGNING_KEYCHAIN." >&2
    exit 5
  fi
  XCODE_ARGS+=(
    CODE_SIGN_IDENTITY="$CODE_SIGN_IDENTITY"
    PROVISIONING_PROFILE_SPECIFIER="$PROFILE_SPECIFIER"
    "OTHER_CODE_SIGN_FLAGS=--keychain $SIGNING_KEYCHAIN"
  )
elif [ -n "$AUTH_KEY_PATH" ] && [ -n "${APPLE_KEY_ID:-}" ] && [ -n "${APPLE_ISSUER_ID:-}" ]; then
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
  if [ "$SIGNING_STYLE" = "Manual" ]; then
    cat > "$EXPORT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>method</key><string>app-store-connect</string>
<key>signingStyle</key><string>manual</string>
<key>signingCertificate</key><string>${CODE_SIGN_IDENTITY}</string>
<key>provisioningProfiles</key><dict>
  <key>${BUNDLE_ID}</key><string>${PROFILE_SPECIFIER}</string>
</dict>
<key>stripSwiftSymbols</key><true/>
<key>uploadSymbols</key><true/>
${TEAM_LINE}
</dict></plist>
PLIST
  else
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
