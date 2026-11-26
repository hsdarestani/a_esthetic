# A+ Esthetic unified native acceptance: staging & release gate

Both development PRs must be used together. Office is implemented in the A+ Django service (deployment manifest maps the Office hostname to its existing mobile API upstream). Book owns appointments and clinical documents. A+ owns accounts, Office forms and invoices. OfficePatientLink records explicit cross-system identity approval; no production medical record is moved or merged.

## Isolated staging
Use a dedicated nonproduction Linux host, separate TLS hostnames, separate unprivileged runtime and restricted persistent storage. No live database imports, production environment files, credentials or outbound notifications. The synthetic fixture uses two newly initialized PostgreSQL clusters, bound only to 127.0.0.1. The preview processes reject external network/DNS connections. The publicly reachable reverse proxy must route only the two dedicated staging hostnames, require HTTPS and set X-Forwarded-Proto, with appropriate access/rate limits. Do not reuse the existing production nginx deployment workflow.

From matching development heads, install both requirements in separate virtual environments. On the staging host, set a unique staging-only APLUS_STAGE_DEMO_PASSWORD (not the fixture's local password), then run:

```sh
python scripts/mobile_staff_preview.py \\
  --book ../book \\
  --app-python /path/to/app-venv/bin/python \\
  --book-python /path/to/book-venv/bin/python \\
  --pg-bin /path/to/postgresql/bin \\
  --state /private/staging-state \\
  --public-app-url https://preview.example.test \\
  --public-book-url https://preview-book.example.test
```

The example hosts are placeholders and must be replaced with authorized staging origins. The script refuses production origins and unmarked existing databases in remote mode. Run as an unprivileged dedicated service with durable private state; configure proxy and certificates independently. Demo accounts are admin@example.test, doctor@example.test and customer@example.test; convey only the unique staging password privately. Rotate before reuse. Test invoices are clearly non-payable and numbering is permitted only in the synthetic preview settings for example.test patients. Live GOÄ issuance is disabled until physician/accounting approval. The original MEDI-LOGIN functional reference requires authorized access; do not infer proprietary mappings from treatment prices.

## Internal QA and single acceptance build
- Run Book regression including PostgreSQL provider-lock concurrency, Sunday closure, identity decision tests and private file access.
- Run A+ functional regression plus real isolated A+/Book HTTP scenario: intake, verified identity, completed visit, multi-line invoice, edits and replay, test numbering, private PDF/records and role isolation.
- Compile SwiftUI and Android View renderers and exercise the shared controller.
- Complete end-to-end native device/simulator workflows, visual/accessibility audit and feature parity (including uncommon settings, files and error cases) before marking QA complete.
- Verify staging ingress, native login, all roles, privacy boundaries, PDF and appointment/calendar gestures against synthetic data.
- Dispatch the dedicated final acceptance workflow only with both verified HTTPS staging URLs and all_qa_complete=true. It will build the independent .preview iOS simulator bundle and Android APK; do not dispatch early. Upload only those artifacts to the authorized Appetize account. No store submit or production deployment from acceptance workflow.

## Production rollout and rollback (future, separate approval)
1. Obtain final Appetize acceptance and explicit authorization. Confirm fee schedule, VAT classification, permitted expenses, invoice issuer/PDF, physician sign-off, and approved live issuance controls. Compare actual deployed Office/Book/app code and database schema with known revisions; preserve the seven Book hotfixes including Sunday and Botox duration.
2. Take verified, encrypted backups of both databases and private document stores; rehearse restore and migration against isolated copies. Inventory current services/ingress and active bookings. Prepare previous application releases and health checks. Confirm current installed app versions work with both old and updated endpoints.
3. Apply only audited additive migrations in an approved change window, staged Book first and A+ second. Use parallel replacement web workers with compatible schemas and health checks; switch routing progressively only after verification, keeping existing workers serving until replacements are ready. Do not use unconditional reset/restart deployment workflows. Keep the existing Office URLs and Book desktop working.
4. Roll out the new client to an approved pilot and monitor booking conflicts, errors, payment/credit reconciliation and identity/audit events. No live invoice issuance until sign-off; never use test invoice numbering in production.
5. Roll back immediately if integrity, availability, permission or booking checks fail: route traffic back to known-good app/Book workers and leave additive columns/tables and newly created records intact. Do not reverse data migrations or restore a stale snapshot over newer bookings. Stop further feature rollout, preserve audit and file storage, reconcile pending cancellation/ledger tasks, and review affected operations individually. Rehearse these steps on staging before release.

Current status: internal compile and API integration are evidence, not native acceptance. Remote infrastructure, Appetize account access, tariff reference verification, complete on-device feature parity and visual QA remain gates. Do not merge or deploy before approval.
