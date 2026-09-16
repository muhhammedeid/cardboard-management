<!-- HISTORICAL / DEPRECATED — V2 tool catalog retained for audit only. The V3 semantic architecture replaced this tool surface; see docs/ai-assistant-v3.md. -->\n\n# AI Assistant V2 — System Data Coverage Matrix

This inventory is derived from the Cardboard Management services and Nova routes that exist at V2 implementation time. Tools are business-question interfaces over those services; they are not generic ERP/DocType access.

| Domain | Available business data | Current service/API | V1 AI tool | V2 capability/tool | Source route |
|---|---|---|---|---|---|
| Suppliers | identity, current outstanding, lifetime supply/payment facts | `reporting.get_supplier_summary`, `suppliers.list_suppliers` | search/balance/statement/latest | supplier supply and payment history | `/suppliers/:id` |
| Supplier dues | per-supplier current outstanding, supply total, paid total, ranking | `reporting.get_outstanding_report` | none | `list_suppliers_with_balances`, `get_supplier_dues_summary` | `/suppliers` |
| Supplies | submitted records, supplier, item, payable weight, value | `supply.list_supplies`, `supply.get_supply` | latest supplier supply only | `search_supplies`, `get_supply_summary`, `compare_supply_periods` | `/supplies` |
| Sales | submitted record, buyer text, item, quantity, informational value | `sales.list_sales`, `reporting.get_sales_summary` | summary | `search_sales`, `compare_sales_periods` | `/sales` |
| Inventory | current/historical ERPNext stock snapshot, value, movement by item | `inventory.get_inventory_overview`, `reporting.get_inventory_movement` | snapshot/movement | `compare_inventory_periods` | `/inventory` |
| Expenses | submitted totals by expense account and records | `reporting.get_expense_summary`, `expenses.list_expenses` | summary | `search_expenses`, `compare_expense_periods` | `/expenses` |
| Supplier payments | submitted supplier payment history and totals | `supplier_payments.list_supplier_payments`, `reporting.get_supplier_summary` | recent transactions | supplier payment history | `/payments` |
| Cross-domain operations | supplies, sales, payments, expenses, movement totals | `reporting.get_operations_summary` | summary | retained; supports multi-tool comparison planning | `/reports` |
| Cash/bank summary | no safe app-owned aggregate service found | no V2-safe service | none | **BACKEND CAPABILITY REQUIRED** | — |
| Account balance / raw GL | accounting integrations exist but no safe summary service for V2 | no V2-safe service | none | **BACKEND CAPABILITY REQUIRED**; raw GL excluded | — |
| Profit/loss | sales are informational and no authoritative P&L service exists | no V2-safe service | none | **BACKEND CAPABILITY REQUIRED** | — |
| Purchase-rate trend | individual supply details have rate/weights but no scoped trend service exists | no V2-safe aggregate service | none | **BACKEND CAPABILITY REQUIRED** | — |

## Result policy

- Searches: maximum 25 result records per request.
- Supplier due summary: top 10; supplier balance list: top 25.
- Aggregates and comparisons: up to 10 years, calculated server-side, without raw record dumps.
- The planner never receives raw ledger rows, generic DocTypes, SQL, or generic Frappe methods.

## Structured state

The server cache keeps only a bounded schema: resolved supplier/item IDs, active period, previous intent, comparison reference, and the last tool/source label. It never stores transcript history, answers, business values, raw tool results, or audio. A later reference such as `ليه` may resolve only if one relevant entity is already active; otherwise the assistant must clarify.
