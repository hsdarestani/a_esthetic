# A+ Esthetic P0 integration

This branch starts from the current `main` release and integrates production-critical parts from the older complete-feature branch without merging that branch wholesale.

Target scope:

- versioned Django migrations
- production email/auth foundations
- real account-deletion request workflow
- effective device/session revocation
- slot-based appointment booking and appointment-change flow
- privacy/data-export foundations
- regression tests for the migrated P0 behavior

The current native customer-club release remains the compatibility baseline while these changes are integrated and validated.
