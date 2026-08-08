# A+ Esthetic – Google Play & App Store checklist

## Release identity

- App: A+ Esthetic
- Product: digital customer club / loyalty app
- Repository: `hsdarestani/a_esthetic`
- Branch: `main`
- Android package: `de.aplusesthetic.app`
- iOS bundle ID: `de.aplusesthetic.app`
- Version for first release: `1.0.0`
- Production: `https://esthetic.smarbiz.sbs`
- Suggested store category: Lifestyle

## Product declaration

The submitted app is a customer club. It does not provide health/medical functionality, diagnosis, treatment recommendations, dosage guidance or clinical decision support.

Do not select a health/medical category merely because separate professionals at a practice may offer services outside the app.

## Before Publisher

- [ ] Customer-club refactor checks pass
- [ ] Production site deployment is healthy
- [ ] Public privacy URL works without login
- [ ] Public support URL works without login
- [ ] Public account-deletion/request URL works without login
- [ ] Final A+ Esthetic app icon is available
- [ ] Final Android/iOS screenshots are available
- [ ] Demo/review member account exists and remains active during review

## Publisher – Android

Repository: `hsdarestani/a_esthetic`
Branch: `main`
Build command:

```bash
bash scripts/build-android.sh
```

Expected artifact:

```text
artifacts/a-esthetic-release.aab
```

Required signing environment:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`
- `REQUIRE_ANDROID_SIGNING=1`

## Google Play Console

### App creation

- App name: A+ Esthetic
- Default language: German (Germany)
- App or game: App
- Free/paid: Free unless business model changes
- Category: Lifestyle

### Store listing

Use `store/metadata.de.json` as the source of truth.

### App content

- Ads: No
- App access: Restricted login; provide the review/demo credentials
- Target audience: select only the real intended customer age groups
- Health functionality: No health functionality in this customer-club release
- Privacy policy: `https://esthetic.smarbiz.sbs/datenschutz/`
- Account deletion/request: `https://esthetic.smarbiz.sbs/konto-loeschen/`

### Data safety baseline

Declare only data actually used by the release. Review `docs/STORE_DATA_DECLARATION.md` before submitting.

Expected customer-club areas can include:
- account/contact information
- user/account identifiers
- club membership/reward activity
- appointment-organisation data
- customer-support messages
- security/audit data

Do not declare health information merely because old unused backend models exist. If a future release actually starts collecting such data, update the app, privacy policy and store declaration before release.

### Release path

- [ ] Upload signed AAB to Internal testing first
- [ ] Install from Play internal track and test login/navigation/logout
- [ ] Test public legal links from the installed app
- [ ] Confirm package ID/version code
- [ ] Promote/submit to Production only after internal verification

## Publisher – iOS

Requires the Publisher macOS agent.

Build command:

```bash
bash scripts/build-ios.sh
```

Expected artifact:

```text
artifacts/a-esthetic.ipa
```

Build environment can include:
- `APP_VERSION=1.0.0`
- `BUILD_NUMBER=1`
- `APPLE_TEAM_ID`
- signing certificate / provisioning profile managed outside the repository

## App Store Connect

### App record

- Name: A+ Esthetic
- Primary language: German
- Bundle ID: `de.aplusesthetic.app`
- Primary category: Lifestyle
- Privacy policy URL: `https://esthetic.smarbiz.sbs/datenschutz/`
- Support URL: `https://esthetic.smarbiz.sbs/support/`
- Marketing URL: `https://a-esthetic.de/`

### App Privacy baseline

Use `docs/STORE_DATA_DECLARATION.md` and the actual enabled release features. Do not identify the app as collecting health data unless the submitted build actually collects it.

### Review access

Because the app is login-protected, provide an active demo member account and concise review notes explaining where the reviewer can see membership, rewards, appointments and customer-service features.

Suggested review note:

> A+ Esthetic is the digital customer club for A+ Esthetic. The app provides membership, loyalty benefits and rewards, organisational appointment requests, reminders and customer-service communication. The app itself does not provide medical advice, diagnosis, treatment recommendations or clinical decision support. A demo member account is provided for App Review.

### Release path

- [ ] Upload first build to TestFlight
- [ ] Test on a real iPhone
- [ ] Verify login/session, safe-area layout and external links
- [ ] Verify privacy/support/deletion URLs
- [ ] Attach final screenshots and metadata
- [ ] Submit for App Review

## Never commit

- Android keystore
- keystore passwords
- Apple distribution certificates/private keys
- provisioning profiles containing secrets
- App Store Connect private keys
- Google Play service-account JSON
- demo account passwords
