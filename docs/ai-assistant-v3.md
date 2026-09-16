# Semantic Business Query Engine (V3) execution contract - Cardboard Management

Authoritative design for the semantic-query AI assistant. Any change to the
contract, registry, or validator must update this document and its DB-free tests
in the same change.

## Architecture

    user natural Arabic
    -> DeepSeek interpreter (language) : NEW_QUERY | QUERY_PATCH | CLARIFY | REFUSE
    -> ai_semantic (validator)         : schema + registry allowlists + period + rows
    -> ai_query_engine (executor)      : entity resolution + authoritative services
    -> result DTO (facts/records/disambiguation/source_label)
    -> deterministic formatter or one DeepSeek final formatting call

The LLM never receives SQL, generic DocType access, or raw service payloads.
All numbers/periods/entities are resolved server-side.

## Semantic query contract (version 1)

```
{
  "version": "1",
  "domain": "suppliers|supplies|sales|inventory|expenses|payments",
  "operation": "get|list|aggregate|rank|compare",
  "fields": ["..."],
  "filters": {"supplier": "text", "item": "text", "buyer": "text", "expense_account": "text"},
  "period":  {"type": "name"} | {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "compare_period": same shape,
  "aggregation": {"field": "sum|count|min|max|avg"},
  "group_by": ["supplier", "item"],
  "sort": {"field": "...", "direction": "asc|desc"},
  "limit": 1..25,
  "offset": 0..50
}
```

QUERY_PATCH is a sparse object whose keys are the writable query keys above
(fields, filters, period, compare_period, aggregation, group_by, sort,
limit, offset). The merged query is ALWAYS revalidated by validate_query
before execution. Unknown patch keys, unknown fields, and unknown period
types reject with INVALID_QUERY / UNSUPPORTED_FIELD / INVALID_PERIOD.

## Period vocabulary (server-resolved)

today, yesterday, current_week (Sat-Fri), previous_week, current_month,
previous_month, month_to_date, last_7_days, last_30_days, current_year,
plus {"type": "month_name"}. Explicit from/to bounds: no future dates;
aggregate span cap 3660 days.

## Domain registry (authoritative, server-owned)

- suppliers - ops list|rank|get; fields: name, supplier_name, outstanding,
  supply_value, supplied_weight_tons, supply_count; rank metrics
  outstanding, supply_value; filter supplier.
- supplies - ops get|list|aggregate|compare; fields: date, net_weight_kg,
  payable_weight_kg, payable_weight_tons, rate_per_kg, total_amount,
  supplier, item, source; aggregations sum/count/avg (tons are never summed
  directly: the server aggregates Kg and converts); filters supplier, item;
  sort date, total_amount, payable_weight.
- sales - ops get|list|aggregate|compare; fields: date, quantity,
  total_amount, item, buyer_name; filters item, buyer.
- inventory - op get only (stock read model snapshot); fields item,
  item_name, quantity, stock_uom, stock_value; filter item.
- expenses - ops get|list|aggregate|compare; fields: date, amount,
  expense_account, account_name; aggregations sum/count on amount;
  filter expense_account.
- payments - ops get|list|aggregate|compare; fields: date, amount,
  mode_of_payment, supplier; aggregations sum/count on amount;
  filter supplier.

limit policy: list/get 1..25 (defaults 5/1), rank 1..10, offset 0..50.
The only model execution path is execute_tool(name, {query}) over the six
domain tools.

## AI-facing tools (model-visible, exact count = 6)

query_suppliers
query_supplies
query_sales
query_inventory
query_expenses
query_payments

Internal/shared helpers (ai_semantic validator, ai_query_engine executors,
ai_read_tools wrappers, telemetry) are NOT independently exposed to the model.

## Query patch / conversation design

Conversation state stores ONLY last_semantic_query (the last *validated*
query) plus bounded last_resolved_entities (supplier/item strings, 140 chars).
No raw results, business values, transcripts, or answers. A follow-up turn is
interpreted as a QUERY_PATCH against the stored query; apply_patch merges and
FULLY revalidates before execution (offset for previous-record, period swap,
field narrowing, limit changes).

## Run limits and security (read-only)

- Entity resolution is backend-owned: 0 -> ENTITY_NOT_FOUND; 1 -> resolve;
  multiple -> candidate list for clarification.
- Periods are server-resolved (never model arithmetic).
- All aggregation/ranking/conversion server-owned; tons are never summed
  directly.
- Strictly read-only: no create/update/delete/submit/cancel, payment or
  journal creation, stock mutation. Write and disclosure verbs are refused
  by the chat gate before interpretation.
- No SQL, frappe.get_doc, generic DocType/method access, or arbitrary
  whitelisted surface: the only execution path is execute_query(query).

## Telemetry

Emitted metadata only:

correlation_id, model, provider, semantic_domain, semantic_operation,
query_type, tool_name, result_count, query_status, error_code,
interpretation_latency_ms, query_latency_ms, formatting_latency_ms,
total_latency_ms.

Never logged: user question, semantic query containing entity values,
supplier names, business values, result DTOs, answers, audio, API secrets,
user questions, raw queries containing entity values.

## Latency model

Common flow: one interpretation call (~provider latency), one backend query
(milliseconds), zero or one formatting call. Simple single-fact answers use
the deterministic formatter and skip the second model call.
