# Publisher setup – A+ Esthetic

Repository: `hsdarestani/a_esthetic`
Branch: `main`

## Identity

- App name: `A+ Esthetic`
- Product: customer club / loyalty app
- Android package: `de.aplusesthetic.app`
- iOS bundle ID: `de.aplusesthetic.app`
- Production web service: `https://esthetic.smarbiz.sbs`

## Android build contract

Build command:

```bash
bash scripts/build-android.sh
```

Artifact:

```text
artifacts/a-esthetic-release.aab
```

Signing secrets expected by the build command:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`
- `REQUIRE_ANDROID_SIGNING=1` for store builds

The keystore is decoded only inside the build agent and is never committed.

## iOS build contract

Requires a macOS Publisher agent.

Build command:

```bash
bash scripts/build-ios.sh
```

Artifact:

```text
artifacts/a-esthetic.ipa
```

Supported build environment:

- `APP_VERSION` (example: `1.0.0`)
- `BUILD_NUMBER` (example: `1`)
- `APPLE_TEAM_ID`
- `IOS_ALLOW_PROVISIONING_UPDATES=1` when the agent is allowed to resolve signing automatically
- optional `IOS_EXPORT_OPTIONS_PLIST_BASE64` for a Publisher-managed export options file

Certificates/provisioning profiles/App Store Connect credentials remain secrets on the Publisher/macOS agent and are not committed to this repository.

## Preflight

Every build starts with:

```bash
python3 scripts/store_positioning_check.py
```

The store metadata and release notes must describe A+ Esthetic as a customer club/loyalty product, not as a healthcare, diagnosis or treatment product.
