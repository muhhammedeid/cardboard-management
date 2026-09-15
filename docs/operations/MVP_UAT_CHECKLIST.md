# MVP Operational UAT Checklist

**Package:** P05-W01 — MVP Operational Readiness & End-to-End Validation  
**Site:** `cardboard.localhost`  
**Execution mode:** manual, authenticated, using a clearly identifiable test supplier/item and reversible test records

Do not reset the site or delete unrelated records. Record exact names/IDs and values. For every scenario, complete **Actual Result** and **PASS/FAIL** before moving on.

## UAT-00 — Preparation and baseline

**Preconditions**

- [ ] Complete `MVP_INITIAL_SETUP.md`.
- [ ] Select one controlled cardboard item, one controlled supplier, and one test buyer label.
- [ ] Record current authoritative stock and supplier outstanding before creating test records.
- [ ] Confirm the signed-in user is the intended Cardboard operator/manager, not Administrator.

**Steps**

1. Record Company, default warehouse, item, supplier, date, stock balance, and supplier outstanding.
2. Confirm the user can open the custom Cardboard frontend.
3. Confirm the user cannot open direct Payment Entry, Journal Entry, Stock Entry, or Stock Ledger surfaces unless intentionally assigned administrator access.

**Expected Result**

Baseline values are recorded and the operator starts with least-privilege access.

**Actual Result:**  
**PASS/FAIL:**

## UAT-01 — Normal Cardboard Supply

**Preconditions:** controlled supplier/item; known gross, tare, rate; valid settings.

**Steps**

1. Create a new Cardboard Supply draft.
2. Select the controlled supplier and item.
3. Enter gross weight `G`, tare weight `T`, rate `R`, and No Discount.
4. Save the draft, edit one field, and save again.
5. Confirm the draft values and server-derived values.
6. Submit the supply.
7. Verify the resulting native integration, supplier balance, stock increase, and Supply Ticket.

**Expected Result**

- `net_weight = G - T`
- No Discount produces `discount_weight = 0`.
- `payable_weight = net_weight`.
- `total_amount = payable_weight × R`.
- Submit succeeds once, authoritative stock increases by payable/stock quantity according to the backend contract, supplier outstanding/invoice state updates, and the ticket renders the authoritative values.

**Actual Result:**  
Supply ID:  
Native integration ID (if shown):  
Expected vs actual:  
**PASS/FAIL:**

## UAT-02 — Discount boundaries

**Preconditions:** a new controlled Supply draft.

**Steps**

1. Test No Discount.
2. Test Kg discount with an entered discount weight.
3. Test Percentage discount with a percentage below 100.
4. Try tare greater than gross.
5. Try discount greater than net weight.
6. Try 100% percentage.
7. Try a resulting zero payable weight.

**Expected Result**

Valid discount cases are calculated by the server. Invalid gross/tare, excessive discount, 100% percentage rejection, and zero-payable cases are rejected with an understandable validation message. The frontend does not become the calculation authority.

**Actual Result:**  
**PASS/FAIL:**

## UAT-03 — Partial Supplier Payment

**Preconditions:** submitted supply with positive supplier outstanding; enabled mapped Mode of Payment.

**Steps**

1. Create a Supplier Payment draft for a partial amount.
2. Verify supplier, amount, Mode of Payment, and posting date.
3. Save an edit to the draft.
4. Submit once.
5. Verify the native Payment Entry and supplier outstanding.
6. Create and submit a second partial payment for the remaining amount.

**Expected Result**

Each wrapper creates/uses exactly one valid native Payment Entry through the server. Outstanding decreases by the authoritative paid amounts, FIFO/reference allocation is correct, and the second payment applies only to the remaining outstanding.

**Actual Result:**  
Payment IDs:  
Expected outstanding:  
Actual outstanding:  
**PASS/FAIL:**

## UAT-04 — Cardboard Sale

**Preconditions:** controlled item with known available stock.

**Steps**

1. Create a Cardboard Sale draft with buyer, item, quantity, and operational rate/value.
2. Save and edit the draft.
3. Submit once.
4. Verify the native stock transaction and current authoritative stock.
5. Confirm the sale surface uses operational-value wording and does not imply revenue/profit accounting.

**Expected Result**

Submission decreases ERPNext authoritative stock by the sale quantity. The frontend does not calculate stock as Supplies minus Sales.

**Actual Result:**  
Sale ID:  
Native stock transaction ID (if shown):  
Expected stock after sale:  
Actual stock after sale:  
**PASS/FAIL:**

## UAT-05 — Insufficient/invalid Sale

**Preconditions:** controlled item with known available quantity.

**Steps**

1. Try quantity greater than available stock.
2. Try exactly the remaining stock.
3. Try zero and negative quantity.
4. Try an invalid/out-of-scope item.

**Expected Result**

Excess quantity, zero/negative quantity, and invalid item are rejected with an Arabic/operator-safe error. Exact remaining stock succeeds if all other validations pass. No partial native stock transaction is left after rejection.

**Actual Result:**  
**PASS/FAIL:**

## UAT-06 — Quick Expense

**Preconditions:** valid expense account, valid Cash/Bank payment source, and mapped settings.

**Steps**

1. Create a Quick Expense draft with category, amount, payment source/mode, reference/notes.
2. Save and update the draft.
3. Submit once.
4. Verify the native accounting result and Expense List/Detail.
5. Cancel using the operational lifecycle if cancellation is permitted.

**Expected Result**

The server creates/cancels the native accounting document. Expense List, Detail, and reporting show the authoritative record. The operator does not need Journal Entry UI.

**Actual Result:**  
Expense ID:  
Native accounting ID (if shown):  
Expected vs actual:  
**PASS/FAIL:**

## UAT-07 — Inventory reconciliation

**Preconditions:** baseline stock `S0`; controlled item; selected warehouse; dates recorded.

**Steps**

1. Record current stock `S0` from the authoritative stock report.
2. Submit Supply `+X`.
3. Submit Sale `-Y`.
4. Submit another Supply `+Z`.
5. Read Current Inventory for today.
6. Read Historical Inventory for the selected prior end-of-day date(s).
7. Read Inventory Movement for the transaction period and the controlled item.

**Expected Result**

- Current Inventory equals the authoritative current ERPNext stock snapshot.
- Historical Inventory equals the selected-date end-of-day snapshot.
- Movement reports inbound `X + Z`, outbound `Y`, and net activity `X + Z - Y` for the same scope.
- Movement net is not presented or treated as stock balance unless the backend explicitly defines it that way.

| Source | Expected | Actual | Result |
|---|---:|---:|---|
| Opening authoritative stock |  |  | PASS/FAIL |
| Supply 1 inbound |  |  | PASS/FAIL |
| Sale outbound |  |  | PASS/FAIL |
| Supply 2 inbound |  |  | PASS/FAIL |
| Current Inventory |  |  | PASS/FAIL |
| Historical Inventory |  |  | PASS/FAIL |
| Movement inbound/outbound/net |  |  | PASS/FAIL |

## UAT-08 — Supplier statement reconciliation

**Preconditions:** one controlled supplier; two supplies; positive outstanding.

**Steps**

1. Submit Supply 1 and Supply 2.
2. Submit a partial payment.
3. Submit a second payment.
4. Compare Supplier Profile, Supplier Summary, Supplier Statement, and authoritative ERPNext purchase-invoice/payment state.
5. Check same-date ordering and document references.

**Expected Result**

Total supplied, total paid, and current outstanding agree across surfaces. Supplier Statement chronology and entries are backend-authoritative; the frontend does not merge, sort, or invent running balances.

| Source | Expected | Actual | Result |
|---|---:|---:|---|
| Total supplied |  |  | PASS/FAIL |
| Total paid |  |  | PASS/FAIL |
| Current outstanding |  |  | PASS/FAIL |
| Supplier Summary |  |  | PASS/FAIL |
| Supplier Statement |  |  | PASS/FAIL |
| Supplier Profile |  |  | PASS/FAIL |

## UAT-09 — Reports reconciliation

**Preconditions:** known test records and one identical date range.

Open each route and record source data, expected meaning, actual value, and result:

| Report | Source data | Expected | Actual | Result |
|---|---|---|---|---|
| Operations Summary | Supplies, Sales, payments, expenses in range | Domain totals for same range |  | PASS/FAIL |
| Current Inventory | ERPNext stock snapshot | Current scoped stock |  | PASS/FAIL |
| Inventory Movement | Submitted Supply/Sale activity | Inbound/outbound/net activity |  | PASS/FAIL |
| Expense Summary | Submitted Quick Expenses/native JEs | Total and category breakdown |  | PASS/FAIL |
| Supplier Summary | Controlled supplier history/outstanding | Supplier totals/current outstanding |  | PASS/FAIL |
| Supplier Statement | Controlled supplier entries | Backend-authoritative chronology |  | PASS/FAIL |
| Supplies | Submitted supplies | Paginated rows and values |  | PASS/FAIL |
| Sales | Submitted sales | Paginated rows and operational values |  | PASS/FAIL |

## UAT-10 — Cancellation and reversal

**Preconditions:** one submitted Supply, Sale, Supplier Payment, and Quick Expense created solely for UAT.

**Steps**

1. Cancel each through its custom operational route where supported.
2. Confirm the linked native document is cancelled/reversed by the server.
3. Re-read stock, supplier outstanding, accounting/reporting totals, and status.

**Expected Result**

Cancellation is lifecycle-safe, native integrations are reversed in the approved order, and authoritative balances return to the pre-test baseline. No direct Payment Entry/Journal Entry manipulation is required.

**Actual Result:**  
**PASS/FAIL:**

## UAT-11 — Permissions and ERPNext exposure

**Preconditions:** a real non-Administrator Cardboard operator account.

**Steps**

1. Test Supplies, Sales, Suppliers, Supplier Payments, Expenses, Inventory, Reports, and Settings from the custom frontend.
2. Attempt direct access to Payment Entry, Journal Entry, Purchase Invoice internals, General Ledger, Stock Ledger, account masters, and unrelated ERPNext workspaces.
3. Verify manager-only configuration/cancellation actions with the designated manager account.

**Expected Result**

The operator can perform intended daily custom operations without Administrator privileges and cannot perform unrelated native ERP actions. Record any required manager fallback explicitly.

**Actual Result:**  
Operator account:  
Manager account:  
**PASS/FAIL:**

## UAT-12 — Restart and persistence

**Preconditions:** no unsaved business action; backup procedure reviewed.

**Steps**

1. Record a draft and a submitted test record ID.
2. Stop/start the existing local bench using the documented commands, or perform the approved pilot restart procedure.
3. Verify the records, statuses, linked native IDs, settings, and reports after restart.
4. Do not perform this against live operations without an approved maintenance window.

**Expected Result**

The site returns healthy, records persist exactly, and no duplicate submit occurs after reload/retry.

**Actual Result:**  
**PASS/FAIL:**

## UAT sign-off

| Area | Owner | Date | Result | Notes |
|---|---|---|---|---|
| Supply |  |  |  |  |
| Supplier Payment |  |  |  |  |
| Sale |  |  |  |  |
| Expense |  |  |  |  |
| Inventory |  |  |  |  |
| Supplier balance |  |  |  |  |
| Reports |  |  |  |  |
| Permissions |  |  |  |  |
| Settings |  |  |  |  |
| Backup/recovery |  |  |  |  |

**Final UAT decision:** GO / GO WITH ACTIONS / NO-GO

**Open findings:**