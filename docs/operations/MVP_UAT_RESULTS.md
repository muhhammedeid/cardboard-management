# MVP UAT Results

**Package:** P05-W02 — Controlled Operational UAT & Pilot Sign-Off  
**Site:** `cardboard.localhost`  
**Evidence owner:** user-owned authenticated manual UAT  
**Current evidence date:** 2026-09-13

## Evidence policy

This file records only observed preflight results and explicitly supplied manual evidence. A scenario is not marked PASS because a route/API renders or because an automated test passes. UAT-01 through UAT-12 require the operator to enter the actual document IDs and expected/actual business values below.

## UAT-00 — Environment Preflight

- **Date:** 2026-09-13
- **User:** read-only verification session; authenticated pilot user not manually signed off
- **Preconditions:** existing development bench/site; no configuration changes
- **Test data:** site settings and health endpoints only
- **Expected:** backend/frontend reachable, valid settings readable, operator role and escalation path identifiable
- **Actual:**
  - Backend `frappe.ping`: HTTP 200, `{"message":"pong"}`.
  - Frontend `/reports`: HTTP 200; returned Arabic RTL HTML with `dir="rtl"`.
  - Company: `El Nos`.
  - Default warehouse: `Main Warehouse - RN`.
  - Cardboard Item Group: `Used Cardboard`.
  - Default Supplier Group: `Cardboard Suppliers`.
  - Default Mode of Payment: `Cash`.
  - Non-Administrator users with `Cardboard Operator`: 2.
  - `Administrator` escalation account: exists.
  - Dedicated `Cardboard Manager` role: not provisioned.
  - `bench doctor`: one worker online; scheduler disabled/inactive.
  - Installed apps: Frappe `15.120.0`, ERPNext `15.121.0`, Cardboard Management `0.0.1`.
- **PASS/FAIL:** PASS WITH ACTION — technical preflight passed; actual operator login, manager escalation, and browser access require user confirmation.
- **Issue ID:** P05-W02-A01
- **Resolution:** documented as an action; no permission or configuration changes made.
- **Retest result:** pending authenticated user check.

## UAT-01 — Controlled Supply

- **Date:**
- **User:**
- **Preconditions:** controlled supplier/item and valid settings
- **Test data:** Supply ID; gross; tare; discount; rate
- **Expected:** net `900 Kg`, discount `50 Kg`, payable `850 Kg`, total `8,500 EGP` for the recommended example; submitted state, ticket, inventory, and supplier outstanding agree with authoritative records
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

## UAT-02 — Percentage Discount

- **Date:**
- **User:**
- **Preconditions:** new controlled Supply draft
- **Test data:** gross `1000 Kg`; tare `200 Kg`; percentage `10%`; rate; Supply ID
- **Expected:** net `800 Kg`, discount `80 Kg`, payable `720 Kg`; server-authoritative values
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

## UAT-03 — Partial Supplier Payment

- **Date:**
- **User:**
- **Preconditions:** submitted controlled supply with positive outstanding and mapped payment mode
- **Test data:** supplier; payment ID; amount; native Payment Entry ID; before/after outstanding
- **Expected:** partial payment submits once, native Payment Entry is created, supplier profile/summary/statement agree, and remaining outstanding is correct
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

## UAT-04 — Controlled Sale

- **Date:**
- **User:**
- **Preconditions:** controlled item with known authoritative available stock
- **Test data:** Sale ID; stock before; sale quantity; native stock transaction ID
- **Expected:** with `850 Kg` available and `200 Kg` sale, remaining authoritative stock is `650 Kg`; Sale Detail, Current Inventory, Movement, and Sales Report agree
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

## UAT-05 — Insufficient Stock

- **Date:**
- **User:**
- **Preconditions:** controlled item and recorded available stock
- **Test data:** attempted quantity; Sale draft ID; stock before/after
- **Expected:** submission is rejected with an Arabic operator-safe error; no submitted record or partial stock effect exists; inventory is unchanged
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

## UAT-06 — Quick Expense

- **Date:**
- **User:**
- **Preconditions:** two valid expense categories/accounts and valid Cash/Bank source
- **Test data:** Expense IDs; categories; `500 EGP` transport; `300 EGP` loading; native Journal Entry IDs
- **Expected:** total `800 EGP`; Expense List, Detail, Expense Summary, Operations Summary, and native accounting agree
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

## UAT-07 — Inventory Reconciliation

- **Date:**
- **User:**
- **Preconditions:** UAT-01, UAT-02, and UAT-04 records completed; same item/warehouse/date scope
- **Test data:** starting stock; Supply 1; Supply 2; Sale; selected historical dates
- **Expected:** current stock equals authoritative ERPNext snapshot; historical view equals selected-date end-of-day snapshot; movement equals inbound/outbound/net activity and is not treated as stock balance
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

| Source | Expected | Actual | Result |
|---|---:|---:|---|
| Starting authoritative stock |  |  | PENDING |
| Supply 1 |  |  | PENDING |
| Supply 2 |  |  | PENDING |
| Sale |  |  | PENDING |
| Current Inventory |  |  | PENDING |
| Historical Inventory |  |  | PENDING |
| Inventory Movement inbound/outbound/net |  |  | PENDING |

## UAT-08 — Supplier Reconciliation

- **Date:**
- **User:**
- **Preconditions:** controlled supplier with two supplies and one or more payments
- **Test data:** Supply IDs; Payment IDs; Purchase Invoice IDs; Payment Entry IDs
- **Expected:** supplies total, payments total, and outstanding agree across Supplier Profile, Supplier Summary, Supplier Statement, source records, and native documents
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

| Source | Expected | Actual | Result |
|---|---:|---:|---|
| Supplies total |  |  | PENDING |
| Payments total |  |  | PENDING |
| Current outstanding |  |  | PENDING |
| Supplier Profile |  |  | PENDING |
| Supplier Summary |  |  | PENDING |
| Supplier Statement |  |  | PENDING |
| Native Purchase Invoice/Payment Entry state |  |  | PENDING |

## UAT-09 — Reports Reconciliation

- **Date:**
- **User:**
- **Preconditions:** controlled records completed; one identical date range used across applicable reports
- **Test data:** date range; report routes; source document IDs
- **Expected:** report values match the authoritative source domain and use the correct semantics
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

| Report | Expected | Actual | Result |
|---|---|---|---|
| Operations Summary | Supplies, sales, payments, expenses for same range |  | PENDING |
| Current Inventory | Current scoped stock snapshot |  | PENDING |
| Inventory Movement | Inbound/outbound/net activity |  | PENDING |
| Expense Summary | Total and category breakdown |  | PENDING |
| Supplier Summary | Supplier totals and current outstanding |  | PENDING |
| Supplier Statement | Backend-authoritative chronology and entries |  | PENDING |
| Supplies Report | Paginated supply records and values |  | PENDING |
| Sales Report | Paginated sale records and operational values |  | PENDING |

## UAT-10 — Cancellation / Reversal

- **Date:**
- **User:**
- **Preconditions:** controlled submitted records only; safe maintenance/test window
- **Test data:** Supply/Sale/Payment/Expense IDs; linked native IDs
- **Expected:** supported cancellation reverses the native effect, restores stock/outstanding where applicable, and updates report results without touching production-like records
- **Actual:** pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:**
- **Resolution:**
- **Retest result:**

## UAT-11 — Permissions

- **Date:**
- **User:**
- **Preconditions:** actual intended pilot Operator and manager/admin escalation account
- **Test data:** user names/roles only; no passwords or tokens
- **Expected:** Operator can use Supplies, Sales, Suppliers, Payments, Expenses, Inventory, and Reports without Administrator; unrelated ERPNext native areas remain blocked; escalation path works
- **Actual:** automated role coverage passed, but browser/login confirmation is pending user execution
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:** P05-W02-A01
- **Resolution:** no role changes made; dedicated Cardboard Manager role remains a documented backlog item
- **Retest result:** pending authenticated user check

## UAT-12 — Restart / Persistence

- **Date:**
- **User:**
- **Preconditions:** controlled records exist; approved maintenance window; backup process reviewed
- **Test data:** controlled draft/submitted IDs and settings values
- **Expected:** documented stop/start workflow returns a healthy site and all records, statuses, native links, settings, and reports persist without duplicate effects
- **Actual:** not performed by this agent; environment is user-managed and no restart was initiated
- **PASS/FAIL:** PENDING USER EXECUTION
- **Issue ID:** P05-W02-A02
- **Resolution:** startup procedure is documented in `MVP_OPERATIONS_RUNBOOK.md`
- **Retest result:** pending user execution

## Backup rehearsal

- **BACKUP:** PENDING — run `bench --site cardboard.localhost backup --with-files` after transaction UAT; record artifact paths and verification.
- **RESTORE REHEARSAL:** NOT PERFORMED — no disposable site/database copy was supplied; do not restore over the active UAT site.

## Scheduler decision

- **Observed:** scheduler disabled/inactive; one worker online.
- **Custom-app inspection:** no `scheduler_events`, `enqueue`, or scheduled business-operation references in the application hooks/business code.
- **Decision:** ACCEPTED FOR PILOT for the synchronous Cardboard flows, subject to environment-owner confirmation that the pilot does not depend on unrelated ERPNext scheduled jobs.

## UAT issue register

| Issue ID | Classification | Description | Status |
|---|---|---|---|
| P05-W02-A01 | P1 action | Actual pilot operator login/permissions and manager escalation account require manual confirmation; dedicated Cardboard Manager role is not provisioned. | OPEN — user action |
| P05-W02-A02 | P1 action | Restart/persistence has not been manually exercised. | OPEN — user action |
| P05-W02-A03 | P1 action | Backup artifact and disposable restore rehearsal are pending transaction UAT. | OPEN — user action |

No implementation P0 defect was discovered in this package. Do not convert pending evidence into PASS without manual results.