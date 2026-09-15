# MVP GO / NO-GO Matrix

**Package:** P05-W01 — MVP Operational Readiness & End-to-End Validation  
**Site:** `cardboard.localhost`  
**Decision basis:** source contracts, maintained automated suites, live read-only probes, and required manual UAT

## Matrix

| Area | Status | Evidence / action |
|---|---|---|
| Supply | PASS WITH ACTION | Supply API runtime suite passed 6 tests; lifecycle, permission, lookup, scale, print, and server-derived fields are covered. Execute UAT-01/UAT-02 with controlled real records. |
| Sale | PASS WITH ACTION | Sale API runtime suite passed 8 tests; authoritative stock submission/cancellation, insufficient stock, lifecycle, lookup, and permission paths are covered. Execute UAT-04/UAT-05. |
| Supplier Payment | PASS WITH ACTION | Supplier payment API runtime suite passed 5 tests; native Payment Entry submit/cancel, draft update, mappings, and permission contract are covered. Execute UAT-03/UAT-10. |
| Expense | PASS WITH ACTION | Quick Expense native hardening and source contracts passed; server-owned Journal Entry lifecycle is covered. Execute UAT-06/UAT-10 with at least two categories. |
| Inventory | PASS WITH ACTION | Reporting/read-model runtime suites passed; current stock, historical end-of-day, and movement are separate contracts. Execute UAT-07 and record exact expected/actual values. |
| Supplier Balance | PASS WITH ACTION | Reporting runtime and supplier payment lifecycle tests passed; Supplier Statement chronology is backend-authoritative. Execute UAT-08. |
| Reports | PASS WITH ACTION | Reporting runtime suite passed 7 tests; all eight typed report services/routes are covered by existing frontend tests. Execute UAT-09 using one identical date range and representative records. |
| Permissions | PASS WITH ACTION | Operator runtime permission suite passed 12 tests; custom operations and report gateway access work, native operational documents remain restricted. Validate with the actual pilot user in UAT-11. |
| Settings | PASS WITH ACTION | Live settings readback succeeded: Company `El Nos`, warehouse `Main Warehouse - RN`, item group `Used Cardboard`, supplier group `Cardboard Suppliers`, Mode of Payment `Cash`; capabilities read/write true. Execute invalid-master cases and UAT-00. |
| Backup | PASS WITH ACTION | Procedure is documented; no destructive restore was performed. Complete a disposable-copy backup/restore rehearsal before production-like use. |
| Startup | PASS WITH ACTION | Existing `cardboard-start`/`cardboard-stop` workflow is documented and site ping returned HTTP 200 `pong`. `bench doctor` shows one worker online but scheduler disabled/inactive; confirm scheduler policy before pilot. |
| Error Handling | PASS WITH ACTION | API contracts normalize validation, permission, not-found, configuration, insufficient-stock, accounting, and unexpected-error paths; manual Arabic operator checks remain. |

## Automated and live evidence

- `frappe.ping`: HTTP 200, `{"message":"pong"}`.
- Installed apps: Frappe `15.120.0`, ERPNext `15.121.0`, Cardboard Management `0.0.1`.
- `bench doctor`: one worker online; scheduler disabled/inactive for `cardboard.localhost`.
- Settings validation probe: valid configuration was accepted; invalid Company, warehouse, item group, supplier group, payment mode, wrong-company warehouse, and group warehouse were rejected in a rollback-only console transaction.
- Focused runtime suites:
  - Supply: 6 passed.
  - Supplier Payment: 5 passed.
  - Sale: 8 passed.
  - Reporting: 7 passed.
  - Native integration hardening: 6 passed.
  - Transaction scope: 5 passed, 2 skipped for unavailable optional fixtures.
  - Operator permissions/report gateway: 12 passed.
- Test fixture safety: no prefixed `_P03%` Supply/Sale records were returned by the post-run readback probes; no matching API lifecycle expense payment fixture was returned.

## Gap classification

### P0 — blocks operational pilot

- **None found in automated/source/runtime validation.**

### P1 — serious; action required before pilot sign-off

1. Manual authenticated UAT is still required for real business-state reconciliation across Supply, Sale, Payment, Expense, Inventory, Supplier Balance, Reports, Settings, and cancellation/reversal.
2. Backup/recovery has not been rehearsed against a disposable copy. Complete and sign the procedure before relying on the environment for pilot data.
3. Scheduler is disabled/inactive on the current site. This is acceptable only if the pilot explicitly does not depend on scheduled jobs; otherwise the environment owner must enable and verify it.
4. Permission acceptance with the actual named operator/manager accounts is still user-owned. Automated tests verified the configured role, not pilot account identity and browser access.

### P2/P3 backlog

- Define and provision a dedicated `Cardboard Manager` role only if the pilot requires separation from existing manager/System Manager roles; do not widen permissions merely for convenience.
- Add a controlled reconciliation evidence artifact populated from UAT results.
- Decide whether scheduler health should be part of the local readiness command output.
- Perform a later usability pass for operator-facing diagnostics after P05; no frontend redesign is included here.

## P05-W01 baseline decision

**MVP GO WITH ACTIONS**

The maintained backend/frontend checks and live read-only probes show no unresolved P0 defect and support a controlled pilot. This is not an unconditional production approval: complete UAT-00 through UAT-12 as applicable, verify backup/recovery on a disposable copy, and resolve the scheduler/permission decisions before entering real operational use.

**User UAT required:** YES  
**Next step:** execute `docs/operations/MVP_UAT_CHECKLIST.md` with authenticated, clearly identifiable test records.

## P05-W02 current pilot decision

**PILOT GO WITH ACTIONS — UAT PENDING**

UAT-00 technical preflight passed: backend and frontend health checks returned HTTP 200, configured settings read back correctly, two non-Administrator Cardboard Operator users were found, and the Administrator escalation account exists. UAT-01 through UAT-12 have not been manually executed or signed off in this workspace. No implementation P0 defect is known. Do not convert this status to `PILOT GO` until the user records passing inventory, supplier, report, permission, backup, and persistence evidence in `MVP_UAT_RESULTS.md`.

## P05-W03 current cutover decision

**BLOCKED — USER ACTION REQUIRED**

The normal frontend runtime is explicitly `VITE_API_MODE=real`; Vite `/api` proxying, cookie credentials, CSRF session handshake, real-service composition, no-fallback behavior, backend contract rollback smokes, and the clean backend baseline are verified in `MVP_CUTOVER_RESULTS.md`. Standalone demo drafts were removed, remaining linked transactions were cancelled through normal lifecycle APIs, current stock is `0.0 Kg`, and required master configuration is preserved. Authenticated browser Supplier/Supply CRUD, refresh persistence, login-expiration behavior, and user visual QA remain pending because the authenticated browser profile was unavailable to automation. Do not sign off P05-W03 until the user completes those checks.
