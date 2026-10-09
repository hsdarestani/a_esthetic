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

# Always configure the Google Play release version, not Capacitor's default 1.
python3 - <<'PY'
import os
import re
from pathlib import Path

gradle = Path("android/app/build.gradle")
if not gradle.is_file():
    raise SystemExit("Expected Android app Gradle file not found")
version = os.environ.get("APP_VERSION_NAME", os.environ.get("APP_VERSION", "1.0.0")).strip()
build = os.environ.get("APP_BUILD_NUMBER", os.environ.get("BUILD_NUMBER", "1")).strip()
if not build.isdecimal() or int(build) < 1:
    raise SystemExit("APP_BUILD_NUMBER must be a positive integer")
if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", version):
    raise SystemExit("APP_VERSION_NAME must be a numeric dotted version")
source = gradle.read_text(encoding="utf-8")
source, code_count = re.subn(
    r'(?m)^(\s*versionCode\s+)\d+(\s*(?://[^\n]*)?)$',
    lambda m: m.group(1) + build + m.group(2),
    source, count=1,
)
source, name_count = re.subn(
    r'''(?m)^(\s*versionName\s+)["'][^"']+["'](\s*(?://[^\n]*)?)$''',
    lambda m: m.group(1) + '"' + version + '"' + m.group(2),
    source, count=1,
)
if code_count != 1 or name_count != 1:
    raise SystemExit("Could not set Android versionCode and versionName")
gradle.write_text(source, encoding="utf-8")
print(f"Verified Android Play versionName={version} versionCode={build}")
PY

# The Android Google login is completed in the system browser and returns to
# the app with a short-lived signed bridge code. Register the callback URI on
# the generated Capacitor MainActivity before Gradle packages the app.
python3 - <<'PY'
from pathlib import Path
import re

manifest = Path('android/app/src/main/AndroidManifest.xml')
text = manifest.read_text(encoding='utf-8')
scheme = 'de.aplusesthetic.app'
host = 'social-login'

activity = re.search(
    r'(<activity\b[^>]*android:name="[^"]*MainActivity"[^>]*>)(.*?)(</activity>)',
    text,
    flags=re.S,
)
if not activity:
    raise SystemExit('Could not locate generated MainActivity in AndroidManifest.xml')

block = activity.group(0)
if f'android:scheme="{scheme}"' not in block:
    intent = f'''
            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="{scheme}" android:host="{host}" />
            </intent-filter>
'''
    block = activity.group(1) + activity.group(2) + intent + activity.group(3)
    text = text[:activity.start()] + block + text[activity.end():]
    manifest.write_text(text, encoding='utf-8')

updated = manifest.read_text(encoding='utf-8')
if f'android:scheme="{scheme}"' not in updated or f'android:host="{host}"' not in updated:
    raise SystemExit('Android social-login callback intent filter was not installed')
print('Android Google OAuth callback intent filter verified.')
PY

# Android 15+ enforces edge-to-edge drawing. Insets exposed to CSS are not
# reliable in all WebView/OEM combinations, so shrink the native content view
# to the actual system-bar safe rectangle. Fixed web navigation then uses the
# safe WebView viewport instead of sitting behind the status/navigation bars.
python3 - <<'PY'
from pathlib import Path
import re

candidates = list(Path('android/app/src/main/java').rglob('MainActivity.java'))
if len(candidates) != 1:
    raise SystemExit(f'Expected one generated MainActivity.java, found {len(candidates)}')
path = candidates[0]
original = path.read_text(encoding='utf-8')
match = re.search(r'^package\s+([\w.]+);', original, re.M)
if not match:
    raise SystemExit('Could not resolve Android application package')
package = match.group(1)
text = f'''package {package};

import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {{
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);

        Window window = getWindow();
        window.setStatusBarColor(Color.WHITE);
        window.setNavigationBarColor(Color.WHITE);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {{
            window.setNavigationBarContrastEnforced(false);
        }}

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {{
            window.setDecorFitsSystemWindows(false);
            WindowInsetsController controller = window.getInsetsController();
            if (controller != null) {{
                int appearance = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                        | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                controller.setSystemBarsAppearance(appearance, appearance);
            }}

            View content = findViewById(android.R.id.content);
            content.setOnApplyWindowInsetsListener((view, insets) -> {{
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return insets;
            }});
            content.requestApplyInsets();
        }} else {{
            int flags = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {{
                flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            }}
            window.getDecorView().setSystemUiVisibility(flags);
        }}
    }}
}}
'''
path.write_text(text, encoding='utf-8')
print(f'Applied native system-bar inset handling to {path}')
PY

# Apply the version supplied by A+ Publisher before Gradle packages the bundle.
python3 scripts/configure_android_release.py

# Use the exact icon uploaded as iconesth.png for the Android launcher. The
# source is a valid opaque PNG, so keeping it as PNG avoids format/extension
# mismatches and makes the Publisher build use the same artwork as iOS.
LAUNCHER_SOURCE="$ROOT/iconesth.png"
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
cp "$LAUNCHER_SOURCE" "$LAUNCHER_DIR/launcher_icon.png"

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

echo "Installed iconesth.png as the A+ Esthetic Android launcher icon."

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
