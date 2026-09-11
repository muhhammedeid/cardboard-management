# FE00 backend contract map

No backend endpoint was added or changed. The real transport calls existing whitelisted methods only.

| Frontend service | Existing Frappe method | Confirmed semantics |
|---|---|---|
| `inventory.getOverview` | `cardboard_management.inventory.get_inventory_overview` | Snapshot as of `selected_date`, including server-returned selected-day activity and stock value. |
| `reporting.getOperationsSummary` | `cardboard_management.reporting.get_operations_summary` | Submitted supplies, sales, expenses, payments, and movement for a date range. |
| future `reporting.getInventoryMovement` | `cardboard_management.reporting.get_inventory_movement` | Inbound/outbound/net by date and item. |
| future `reporting.getSalesSummary` | `cardboard_management.reporting.get_sales_summary` | Informational sale aggregates and by-item breakdown. |
| future `reporting.getSupplierSummary` | `cardboard_management.reporting.get_supplier_summary` | Selected supplier history plus current ERPNext outstanding. |
| future `reporting.getSupplierStatement` | `cardboard_management.reporting.get_supplier_statement` | Stable alias of supplier summary. |
| future `reporting.getExpenseSummary` | `cardboard_management.reporting.get_expense_summary` | Quick Expense totals and by-account aggregates. |

## Backend contract gaps

- **BCR-01** — Supplies by Supplier aggregate; required only for the deferred grouped report.
- **BCR-02** — Supplies by Cardboard Type aggregate; required only for deferred type breakdowns.
- **BCR-03** — Sales by Buyer aggregate; required only for the deferred buyer report.
- **BCR-04** — All-supplier outstanding ranking; deferred.
- **BCR-05** — Explicit time-series operations/movement contract; deferred, omit charts until returned.
- **BCR-06** — Server-authoritative operational alert feed; deferred, do not infer alerts in the browser.
