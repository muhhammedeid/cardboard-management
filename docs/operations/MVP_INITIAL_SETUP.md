# MVP Initial Setup Checklist

**Package:** P05-W01 — MVP Operational Readiness & End-to-End Validation  
**Site:** `cardboard.localhost`  
**Scope:** minimum master data required before Cardboard operational pilot

Complete this checklist in the target site before entering real operations. Use enabled, non-group masters unless a line explicitly says otherwise.

## 1. Company and warehouse

- [ ] A valid Company exists and is selected in **Cardboard Dashboard Settings**.
- [ ] The default warehouse exists, is enabled, is a leaf warehouse, and belongs to the selected Company.
- [ ] The selected warehouse is physically the intended receiving/dispatch location.
- [ ] The selected Company and warehouse are confirmed by creating a draft Supply and draft Sale; do not rely on a frontend label alone.

**Current development-site readback:**

- Company: `El Nos`
- Default warehouse: `Main Warehouse - RN`

## 2. Cardboard item masters

- [ ] The configured Cardboard Item Group exists and is the intended root group.
- [ ] Cardboard Item Group descendants are configured if the business uses subgroups.
- [ ] Each operational cardboard item is enabled.
- [ ] Each operational cardboard item is a stock item.
- [ ] Each operational cardboard item uses `Kg` as Stock UOM.
- [ ] Item codes and names are unique and approved for RTL display.
- [ ] Opening stock, if any, is posted through the approved ERPNext stock process and verified in the authoritative stock report.

**Current development-site readback:**

- Cardboard Item Group: `Used Cardboard`

## 3. Suppliers

- [ ] The default Supplier Group exists, is enabled, and is a leaf group.
- [ ] Each supplier has a unique stable supplier name/code.
- [ ] Each supplier is enabled for use.
- [ ] Supplier payable account configuration is present for the selected Company.
- [ ] At least one controlled supplier is selected for UAT reconciliation.

**Current development-site readback:**

- Default Supplier Group: `Cardboard Suppliers`

## 4. Modes of Payment and accounting mappings

- [ ] At least one enabled Mode of Payment exists.
- [ ] The selected default Mode of Payment has an enabled Cash/Bank account mapping for the selected Company.
- [ ] Supplier payable accounts resolve through ERPNext party configuration.
- [ ] Expense accounts exist under the selected Company, are enabled, and are leaf accounts.
- [ ] Cash/Bank payment accounts exist under the selected Company, are enabled, are leaf accounts, and have compatible currency.
- [ ] Expense category and payment-source lookups return only valid configured accounts.
- [ ] The operator does not need to open Journal Entry or Payment Entry to perform daily work.

**Current development-site readback:**

- Default Mode of Payment: `Cash`
- Settings capabilities: read/write available to the current verification user

## 5. Cardboard Dashboard Settings

- [ ] `company` is valid.
- [ ] `default_warehouse` is valid, enabled, non-group, and belongs to `company`.
- [ ] `cardboard_item_group` is valid.
- [ ] `default_supplier_group` is valid, enabled, and non-group.
- [ ] `default_mode_of_payment` is enabled and mapped for `company`.
- [ ] Save the settings and read them back before pilot start.
- [ ] Do not infer or hard-code Company/Warehouse/Item Group scope in the frontend.

## 6. Pilot readiness record

Record the selected values in the pilot runbook without storing passwords or tokens:

| Master | Selected value | Verified by | Date |
|---|---|---|---|
| Company |  |  |  |
| Default warehouse |  |  |  |
| Cardboard Item Group |  |  |  |
| Default Supplier Group |  |  |  |
| Default Mode of Payment |  |  |  |
| Controlled cardboard item |  |  |  |
| Controlled supplier |  |  |  |

## Minimum approval rule

Do not start the pilot if any required line above is unchecked, if a lookup returns a disabled/group master, if a Company/Warehouse mismatch is found, or if a native accounting/stock mapping is missing. Correct the master data and repeat the relevant UAT scenarios.