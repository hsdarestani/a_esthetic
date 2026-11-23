# A+ Esthetic mobile overhaul

This branch requires the matching Book feature branch. Both the browser preview and the optional test packages use synthetic records. The native preview application ID ends in `.preview`; local QA uses loopback and the final acceptance build requires independent HTTPS staging. Its build does not require Apple signing, Google sign-in credentials or the existing app's signing key.

## Run the isolated preview

Check out both branches side by side. Install each repository's Python requirements in its own virtual environment, and make PostgreSQL's `initdb`, `pg_ctl` and `createdb` available. The Linux `pgserver` package can also supply the PostgreSQL binaries.

From this repository:

```sh
python scripts/mobile_staff_preview.py \
  --book ../book \
  --app-python /path/to/app-venv/bin/python \
  --book-python /path/to/book-venv/bin/python \
  --pg-bin /path/to/postgresql/bin
```

The browser app listens on [127.0.0.1:5181](http://127.0.0.1:5181/) and the Book desktop interface on [127.0.0.1:5182](http://127.0.0.1:5182/verwaltung/login/). The preview initializes independent PostgreSQL clusters on loopback. It clears inherited production configuration, blocks outbound traffic in preview Django processes and captures emails to disk. Public OAuth, native push registrations, production emails, SMS and payments are disabled. The demo credentials are confined to this local fixture.

| Account | Email |
| --- | --- |
| Administrator | admin@example.test |
| Doctor | doctor@example.test |
| Customer | customer@example.test |
| Book desktop | preview (username) |

All preview accounts use the password `Preview-only-2026!`. For the Android APK on a connected device or emulator, run `adb reverse tcp:5181 tcp:5181` and `adb reverse tcp:5182 tcp:5182` on the same computer that runs the preview. The iOS Simulator can reach a preview started on its own macOS host. The APK is a debug build and the iOS simulator bundle cannot be installed on an iPhone.

For browser regression, install Playwright and Chromium, use a clean preview state, and run `python scripts/test_mobile_staff_preview.py`. Add `--output /path/to/evidence` to retain screenshots and a screen recording.

## Feature parity

| Surface | This branch | Release follow-up |
| --- | --- | --- |
| Authentication | New shared sign-in and progressive registration, password controls, in-app reset request, existing email/SMS verification and social provider integrations | Native Apple and Google end-to-end testing, and isolated SMS delivery |
| Customer | Existing account, appointment, package, point, wallet, record and referral routes retained | Device regression for booking, documents, wallet and notifications |
| Administration | Bundled workspace, dashboard, calendar, appointment and patient search, services, account and notification history | Operational settings, provider/service assignment, advanced notifications and desktop workflows |
| Clinician | Scoped calendar, appointments, patient records, download and private notes | File upload/sharing and desktop feature parity |
| Calendar | Day, week, provider and service views, gestures, cached date changes, stable scroll, appointment create/edit/cancel, blocks, notes and availability | Real-device rendering and gesture measurements, source-managed block controls |
| Clinic identity | Existing Book patient IDs and A+ member identities remain separate | Patient creation and identity review continue in Book desktop |
| Points and packages | Point corrections with audit, lookups, package status and cancellation credit reconciliation | Package assignment and entitlement administration continue in existing tools |
| Production | Current production deploy workflows are confined to their existing triggers. Final acceptance workflow is manual and gated on staging and completed QA. | Independent approval and rollout rehearsal |

## Compatibility and release gate

New Book mutations have replay receipts and appointment revisions. The app's existing token format and sign-in exchange remain compatible. The Book desktop site and legacy APIs stay in their original entry points. Keep the package ledger and Book cancellation queue in place during any UI rollback.

Before a real release, verify the live ingress allows the new endpoints and origins, stage old/new clients against both backends, and rehearse switching the staff pilot back to the current app. Do not use the production deploy workflows to stage or generate test packages.


## Preview artifact gate

The local synthetic fixture is for internal QA only. The dedicated acceptance workflow requires two independent HTTPS staging origins and explicit completion of all QA gates; it does not package on PR updates. The Android preview must run the existing native camera/SDK configuration after generating Capacitor, since the barcode dependency requires Android API 26. Do not distribute older standalone artifacts as acceptance previews: the standalone build workflow uses the normal app configuration and does not prove an independent staging backend or absence of production endpoints.

A remotely reachable, isolated two-database staging environment with synthetic users and outbound communication/payment restrictions remains mandatory before any Appetize acceptance build is produced. Do not replace that requirement with a production URL or an unsigned iOS device IPA.


See [current staging and release gates](native-office-release.md) for Issue #82 implementation, acceptance requirements and the future rollback plan.
