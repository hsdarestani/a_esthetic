# Admin V4 progress

- App source branch: `feature/admin-v4-native-20261124`. Base V3: `8f17cf1256a47c076485406e00c2990b3b756284`.
- App first incremental commit: `aece3532fe9f38c42750ae53f1b0a3cf469efad9`.
- Book API branch: `feature/admin-v4-native-api-20261124`, commit `8ac6b7e96d52f73b59088331192821c0375ea6d9`.
- Implemented: forest/gold native workspace, dashboard, custom calendar sheets and pickers, patient sections/pagination, signed intake list/detail/PDF/identity review, GOÄ backend quote preview.
- Existing calendar/source-writeback and authorization preserved; no production patient or booking mutations; no store submission.
- Pending: CI compilation and real device screenshots, inspect screenshots and fix issues; verify backend integration on isolated stage; remaining full patient/web parity (wallet, packages, record management, camera, and unsupported forms).
- Build target: 1.0.49 (55), workflow `.github/workflows/admin-v4-appetize-20261124.yml`. Verify final SHA, artifact layout, and all required QA before declaring release complete.
