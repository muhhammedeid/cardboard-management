# P05-W03 — Real Backend Cutover & Demo Data Cleanup

## Status

**BLOCKED — USER ACTION REQUIRED**

The normal runtime is cut over to the real app-owned backend and the backend dataset has a clean operational baseline. Authenticated browser CRUD and visual confirmation remain user-owned gates because the authenticated browser profile was unavailable to automation.

## Runtime configuration

- Runtime mode: `real`.
- UAT file: `frontend/.env.local` (ignored; contains only `VITE_API_MODE=real` and an empty `VITE_API_BASE_URL`).
- Safe reference: `frontend/.env.example` documents `real` as the normal mode and `mock` as explicit test/demo selection.
- `getFrontendConfig()` now defaults to `real`; invalid values still fail fast.
- Vite proxies `/api` to loopback port `8000` and sends `Host: cardboard.localhost`. This preserves Frappe site routing and session cookies when using `http://localhost:5173`.
- No database, Bench, MariaDB, Redis, or ERPNext/Frappe core restart/change was performed.

## Service composition and fallback audit

- `createServices()` selects real service implementations only for `apiMode=real`.
- Mock services remain available only for explicit `apiMode=mock` and test fixtures.
- Real transport failures remain normalized network/permission/validation errors; there is no real-to-mock fallback.
- Real transport uses `credentials: include`.
- Real POST/RPC requests obtain a session CSRF token from the app-owned authenticated session endpoint and send `X-Frappe-CSRF-Token`.
- The session endpoint rejects Guest access.

## Runtime/API evidence

- `http://localhost:5173/api/method/frappe.ping` → HTTP 200, `{"message":"pong"}`.
- Vite transformed config → `VITE_API_MODE: "real"`, empty API base URL.
- Guest request to the session endpoint → HTTP 403, as required.
- Rollback-only app-contract smoke:
  - Supplier create/read: `UAT-CUTOVER-SUPPLIER` read back in `Cardboard Suppliers`; transaction rolled back.
  - Supply draft create/read: `CS-2026-00007`, draft, server-derived payable `85 Kg`, total `850`; transaction rolled back.
- Authenticated browser route/session/CRUD verification: **PENDING USER**. Automation timed out on both `cardboard.localhost:5173` and `localhost:5173`; no browser visual acceptance is claimed.

## Backend inventory before cleanup

All records below were identified on the configured `cardboard.localhost` site before cleanup. Names alone were not used as the deletion decision; ownership, links, document status, and native dependencies were inspected.

| DocType | Record IDs | Display/source classification | Referenced by | Action/reason |
|---|---|---|---|---|
| Supplier | `Test Supplier` | App UAT/test master, owner `muhamedeiddev@gmail.com`, group `Cardboard Suppliers` | All listed custom transactions and native vouchers | Retained while linked native history remains |
| Item | `CARDBOARD-A` / `Cardboard Type A` | App UAT cardboard master, group `Used Cardboard`, UOM `Kg` | All listed Supply/Sale records | Retained as required UAT item |
| Cardboard Supply | `CS-2026-00001` | App test record; submitted; no native voucher | None | Cancelled and deleted through DocType lifecycle |
| Cardboard Supply | `CS-2026-00002`, `CS-2026-00004`, `CS-2026-00006` | App test drafts | None | Deleted as standalone drafts |
| Cardboard Supply | `CS-2026-00003` | Cancelled app test wrapper | `ACC-PINV-2026-00001` | Retained with native history |
| Cardboard Supply | `CS-2026-00005` | Submitted app test wrapper | `ACC-PINV-2026-00002` | Cancelled normally, retained with native history |
| Cardboard Sale | `SALE-2026-00001` | App test draft | None | Deleted as standalone draft |
| Cardboard Supplier Payment | `CSP-2026-00001` | Cancelled app test wrapper | `ACC-PAY-2026-00001` | Retained with native history |
| Cardboard Supplier Payment | `CSP-2026-00002` | Submitted app test wrapper | `ACC-PAY-2026-00002` | Cancelled normally, retained with native history |
| Quick Expense | `QE-2026-00001` | App test draft, no accounting document | None | Deleted as standalone draft |
| Purchase Invoice | `ACC-PINV-2026-00001`, `ACC-PINV-2026-00002` | Linked native accounting documents | Supply wrappers and GL/Stock Ledger rows | Cancelled/retained; not deleted to avoid orphan immutable ledgers |
| Payment Entry | `ACC-PAY-2026-00001`, `ACC-PAY-2026-00002` | Linked native accounting documents | Supplier Payment wrappers and GL rows | Cancelled/retained; not deleted to avoid orphan immutable ledgers |
| Supplier fixtures | `_Test Supplier*` | ERPNext test fixtures in `_Test Supplier Group`; not app UAT data | No listed app records | Preserved; not assumed safe to delete |

## Cleanup result

Removed through Frappe document APIs:

- Supplies: `CS-2026-00001`, `CS-2026-00002`, `CS-2026-00004`, `CS-2026-00006`.
- Sale: `SALE-2026-00001`.
- Quick Expense: `QE-2026-00001`.

Lifecycle-cancelled and retained:

- Supplies: `CS-2026-00003`, `CS-2026-00005` — both cancelled.
- Supplier Payments: `CSP-2026-00001`, `CSP-2026-00002` — both cancelled.
- Native Purchase Invoices: `ACC-PINV-2026-00001`, `ACC-PINV-2026-00002` — retained.
- Native Payment Entries: `ACC-PAY-2026-00001`, `ACC-PAY-2026-00002` — retained.

No direct SQL deletion of accounting/stock documents or ledger rows was used. Post-cleanup verification found all retained GL/Stock Ledger voucher references still point to existing native vouchers.

## UAT starting state

Authoritative post-cleanup baseline:

- Suppliers in app scope: `Test Supplier` remains, plus unrelated ERPNext `_Test Supplier*` fixtures.
- Cardboard items in app scope: `CARDBOARD-A` / `Cardboard Type A` only.
- Current inventory: `0.0 Kg` for `CARDBOARD-A` in `Main Warehouse - RN`.
- Active Cardboard Supplies: none.
- Active Cardboard Sales: none; all Sales records: none.
- Active Supplier Payments: none; retained payment wrappers are cancelled.
- Active Quick Expenses: none.
- Active Purchase Invoices/Payment Entries for this test supplier: none; cancelled native history retained.
- Required settings unchanged: Company `El Nos`; Warehouse `Main Warehouse - RN`; Item Group `Used Cardboard`; Supplier Group `Cardboard Suppliers`; Mode of Payment `Cash`.

## Frontend mock-data classification

Mock fixtures remain intentionally available for automated tests and explicit mock mode. The inspected fixtures are under:

- `frontend/src/services/mocks/`
- `frontend/src/features/reports/report-service.ts` deterministic mock factory
- `frontend/src/services/*spec.ts` and feature `*spec.ts` test fixtures

They are not selected by the normal `.env.local` runtime. Hardcoded example IDs remain inside mock/test sources only; no normal route uses them after real composition selection.

## Changed implementation files

- `frontend/src/app/bootstrap/config.ts`
- `frontend/src/services/api/frappe-rpc.ts`
- `frontend/vite.config.ts`
- `frontend/.env.example`
- `cardboard_management/api/session.py`
- `cardboard_management/tests/test_session_api_source.py`
- `frontend/src/app/bootstrap/config.spec.ts`
- `frontend/src/services/service-composition.spec.ts`

Temporary cleanup/probe code was used only for the controlled read-only/rollback/lifecycle operation and is removed before final handoff.

## Remaining gate

The user must open the real-mode frontend, authenticate through the existing Frappe session, and perform browser CRUD/refresh checks. No JWT or custom authentication was introduced.
