# Admin V4 progress

- App source branch: `feature/admin-v4-native-20261124`. Base V3: `8f17cf1256a47c076485406e00c2990b3b756284`.
- App first incremental commit: `aece3532fe9f38c42750ae53f1b0a3cf469efad9`.
- App second incremental commit: `b8d2fbc5f3c020b2942184001c676410f6f4e3e2`.
- Book API branch: `feature/admin-v4-native-api-20261124`, commits `8ac6b7e96d52f73b59088331192821c0375ea6d9`, `1fe0d05723730707b52e26b0d6a11574c0153b5e`.
- Implemented: forest/gold native workspace, dashboard, custom calendar sheets and pickers, patient sections/pagination, signed intake list/detail/PDF/identity review, verified account wallet/packages/points/invoices, private photo/camera and audited note corrections, GOÄ backend quote preview and optional target reconciliation.
- Existing calendar/source-writeback and authorization preserved; no production patient or booking mutations; no store submission.
- App code commit `409a38dde01af2c68730336d39c57e9c8a5f8669` compiled on iOS and Android; workflow run `45431640146`. Android screenshots revealed system-bar overlap and empty calendar sheets; correct in next incremental commit and re-run exact builds.
- QA: focused controller/calendar tests passed; offline app Django 15/15, Book 10 passed + 1 PostgreSQL-only skip. Live synthetic two-PostgreSQL integration passed GOÄ draft/replay/edit/PDF, private photos, audited note revisions, signed form sync/PDF, verified wallet/points and role isolation. No production QA writes.
- Owner superseded remote staging requirement: deployment to existing Production authorized, with synthetic QA and no real patient/booking mutations; preserve schema and existing hotfixes. Production App read-only preflight confirmed current web main and existing native schema; Book recheck authorized with documented service identity. Deployment requires schema reconciliation, database and source backups, safe health-checked reload. MEDI-LOGIN proprietary mapping/clinical approval and live invoice issuance remain explicitly gated.
- Build target: 1.0.49 (55), workflow `.github/workflows/admin-v4-appetize-20261124.yml`. Verify final SHA, artifact layout, and all required QA before declaring release complete.
