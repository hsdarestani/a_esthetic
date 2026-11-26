# A+ Esthetic native remediation

Updated 2026-11-26. See the [master remediation tracker](https://github.com/hsdarestani/book/blob/remediation/aesthetic-20261126/docs/qa/AESTHETIC_REMEDIATION.md) in the [Book repository](https://github.com/hsdarestani/book).

## Baseline

- [Patient main](https://github.com/hsdarestani/a_esthetic/commit/6d85d20edb718ca132eb92e787c94e747a84ebae) and [remediation/aesthetic-20261126](https://github.com/hsdarestani/a_esthetic/tree/remediation/aesthetic-20261126).
- Preserve and inspect [native draft #81](https://github.com/hsdarestani/a_esthetic/pull/81) and [SimplyBook native draft #85](https://github.com/hsdarestani/a_esthetic/pull/85). The [calendar regression branch](https://github.com/hsdarestani/a_esthetic/tree/fix/admin-calendar-regression-20261126) and [native v4 branch](https://github.com/hsdarestani/a_esthetic/tree/feature/admin-v4-native-20261124) represent newer candidates that must be inventoried.
- New remediation CI, deployment, iOS/Android artifacts, Appetize build, real-device acceptance and store submission all await evidence.

| ID | Scope | Status | Evidence or exact next action |
| --- | --- | --- | --- |
| BUG-001 | Patient SMS verification | VERIFIED | Owner confirmed working. |
| BUG-002 | Appointment and calendar timezone | IN_PROGRESS | Verify patient-side Berlin display change `6d85d20`. Trace native date and wall-time construction, transport, and DST behavior in current candidate branches. |
| BUG-003 | Treatment and reserved time | TODO | Check native calendar geometry and detail data against Book payloads and historical appointment spans. |
| BUG-004 | SimplyBook lifecycle | TODO | Compare existing native read-only gates and optional edit flags with the master tracker after Book reconciliation. |
| NATIVE | Native admin inventory, interaction and regression | TODO | Inspect Swift and Android source in current candidates and trace dashboard, calendar gestures/filters, appointment details/contact actions, booking and blocks, files and PDFs, privacy, state and sessions. Keep scope to intended native functionality. |
| RELEASE | iOS/Android builds, Appetize and Publisher release | TODO | Establish current candidate branch and build numbers, then validate compile, screenshot/interaction QA, artifacts and acceptance before Publisher submission. |

Root cause, relevant files, new implementation SHA and PR, automated/manual results and deployment are pending unless recorded above. Update this file at every meaningful checkpoint with evidence, remaining work and the next action. Resume by checking this file, the master tracker, current heads, PRs and CI. Start with BUG-002.
