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

## Feature parity — owner-mandated release requirement (2026-11-23)

The authenticated clinic administrator must be able to execute every action
available in the existing Book/Office/A+ desktop admin directly from a genuine
native mobile interface. **The mobile app is the future authoritative console.**
No desktop-only administration, silent WebView substitutions, permanently
read-only records, or arbitrary mobile-only caps are acceptable for release.

This is a target and an acceptance criterion, **not a claim of current feature
parity**. Keep the existing desktop consoles available as safe fallbacks until
every capability is implemented and verified. Explicitly track and close gaps:

| Domain | Native capabilities already present on the draft branch | Still required / mandatory before claiming full admin parity |
| --- | --- | --- |
| Bookings and schedule | Native day/week/provider/service timeline, create/edit/cancel first-party appointments, work hours, blocks and notes | Historical and upstream source-managed booking operations with verified source sync; arbitrary date/provider edits, full booking statuses, bulk workflows, legacy blocks end-to-end on both platforms |
| Patients and clinical records | Search, timeline, private notes, patient PDF read/upload, reviewed identity links | Full create/edit patient demographics, record management, uploads, files sharing/revocation, intake and document workflows |
| Clinicians and service catalog | Read provider list; edit certain services and availability | Create/update/deactivate providers, provider-service assignments, all service catalog fields, service price/duration configuration, every desktop setting |
| Package, wallet and points | Customer view and certain audited point corrections, cancellation credit reconciliation | All package grant/revoke/assign/renew/reconcile, entitlements, wallet/points ledgers, financial adjustments and audit |
| Office and billing | Intake review, identity review, GOÄ draft, quote, PDF/history, issuer/numbering settings | All office actions, safely issued/adjusted invoices after independent medical/accounting approval and official tariff reference validation |
| Staff, notifications, system | Role-scoped staff session, staff dashboard, localized settings | Comprehensive staff identity/roles, reminders, templates, push/email settings, clinic configuration and audit |
| QA/release | Draft iOS and Android native renderers plus synthetic CI | All-role device E2E, exact action-by-action parity inventory, source-of-truth reconciliation, backup/rollback, signed store artifact review |

**SimplyBook caveat:** The new imported-note/blocked-time fix keeps a
local Book override/tombstone so SimplyBook imports do not overwrite an
admin's edit. It does **not** change SimplyBook itself. For imported
source-owned *appointments*, do not simply remove the existing safeguard:
first establish and verify upstream write+reconciliation or an explicit
migration of source ownership, otherwise bookings can silently diverge.

Every admin action must enforce authenticated server-side authorization,
optimistic concurrency and safe idempotency where relevant, auditable actor
identity, patient-data privacy, and canonical Book/A+ financial ledgers.
The native client cannot bypass these safeguards.

**MUST NOT RELEASE AS FULL ADMIN APP** while any mandatory row above lacks
documented production-equivalent E2E evidence on iOS and Android. App Store
and Google Play submission must only use a new build containing the reviewed
client code and compatible Book/A+ server changes, with actual signed
artifacts and release eligibility confirmed.

## Compatibility and release gate

New Book mutations have replay receipts and appointment revisions. The app's existing token format and sign-in exchange remain compatible. The Book desktop site and legacy APIs stay in their original entry points. Keep the package ledger and Book cancellation queue in place during any UI rollback.

Before a real release, verify the live ingress allows the new endpoints and origins, stage old/new clients against both backends, and rehearse switching the staff pilot back to the current app. Do not use the production deploy workflows to stage or generate test packages.


## Preview artifact gate

The local synthetic fixture is for internal QA only. The dedicated acceptance workflow requires two independent HTTPS staging origins and explicit completion of all QA gates; it does not package on PR updates. The Android preview must run the existing native camera/SDK configuration after generating Capacitor, since the barcode dependency requires Android API 26. Do not distribute older standalone artifacts as acceptance previews: the standalone build workflow uses the normal app configuration and does not prove an independent staging backend or absence of production endpoints.

A remotely reachable, isolated two-database staging environment with synthetic users and outbound communication/payment restrictions remains mandatory before any Appetize acceptance build is produced. Do not replace that requirement with a production URL or an unsigned iOS device IPA.


See [current staging and release gates](native-office-release.md) for Issue #82 implementation, acceptance requirements and the future rollback plan.
