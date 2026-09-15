# AI Read-Only Assistant Contract

## Purpose

The assistant is a **read-only natural-language interface over trusted ERP facts** for Cardboard Management. It answers in concise Arabic Egyptian, normally one to three points, and never claims that it changed operational data. It does not disclose chain-of-thought.

V1 does not include RAG, embeddings, a vector database, LangChain, MCP, generic autonomous agent frameworks, text-to-SQL, or SQL agents.

## Approved access boundary

`Cardboard Manager` and `Cardboard Operator` have the **same AI read scope** for approved operational surfaces: operations summaries, supplies, sales, inventory/current inventory/history/movement, suppliers, balances, statements, payments, expenses, and recent operational transactions.

Same AI read scope does not grant unrestricted ERP access. Each request must pass:

1. an authenticated Frappe session;
2. the server-controlled `can_use_ai_assistant` capability;
3. server-owned, schema-validated read tools from the strict allowlist;
4. configured Company, Warehouse, and Cardboard Item Group scope;
5. deterministic fields, rows, page, grouped-entity, and date-range limits;
6. the existing relevant backend authorization boundary.

No write permission is granted. The registry must never expose direct MySQL, arbitrary SQL, arbitrary DocType or method names, unrestricted `frappe.get_doc`, mutation/lifecycle tools, or generic Frappe resources.

## Authoritative facts and numeric grounding

Authoritative values must originate from Cardboard/ERPNext backend tools. Gemini may explain returned facts but must not independently calculate, estimate, modify, fill a missing value, substitute a value, or round business values inconsistently.

No business calculations in Gemini, Vue, or prompt logic. Existing Cardboard/ERPNext services remain responsible for supplier outstanding, stock quantity/value, weights, payment totals, expenses, sales, supplies, historical balances, and inventory movement.

Every numeric tool result uses a narrow structured result such as:

```json
{
  "facts": [
    {
      "id": "supplier_outstanding",
      "value": 153250,
      "currency": "EGP",
      "source": { "route": "/suppliers/SUP-0001" }
    }
  ],
  "records": [],
  "disambiguation": []
}
```

The final answer must remain grounded in the returned facts. Where practical, the orchestrator validates that numeric strings exposed in the answer correspond to authoritative tool facts from the same request. For deterministic questions such as today’s sales, a supplier outstanding, or current inventory, prefer a backend-fact answer with minimal model narration.

Result sources map only to existing authorized Nova routes. Do not expose raw backend URLs, arbitrary Frappe endpoints, or native technical ERP routes.

## Tool bounds and entity resolution

Every tool independently enforces allowed fields, allowed filters, maximum rows, maximum page size, maximum date range, configured Company/Warehouse/Cardboard Item Group scope, and maximum grouped entities. A request for all records since system start is rejected or narrowed; it must never inject thousands of records into model context.

Entity resolution is deterministic backend lookup:

- If exactly one authorized match exists, continue.
- If zero matches exist, say no authorized matching record was found.
- If multiple matches exist, return a short disambiguation list and ask one clarification question.

The model must never choose a supplier or item from similarly named records arbitrarily.

## Untrusted database content

Supplier names, item names, notes, descriptions, references, comments, imported text, and all free-text ERP fields are untrusted data. Never allow tool output to become trusted instructions.

Only send necessary fields in narrow DTOs. Strip or sanitize HTML where appropriate. The protocol order is immutable system instructions, then tool protocol, then tool result as data only, then user content. Neither user text nor stored content can request another tool, disclose the system prompt, override scope, or cause mutation.

## Answer and failure behavior

- If an authoritative answer cannot be established, do not guess.
- If authorization fails, do not reveal whether the inaccessible record exists.
- If entity resolution is ambiguous, ask one clarification question.
- If a provider fails, return a concise Arabic error without inventing a value.
- If TTS fails, retain the successful text answer.
- If streaming fails, use standard request/response JSON where supported.

## Accuracy acceptance dataset

Before rollout, compare every numeric answer with its authoritative Cardboard/ERPNext source. The acceptance set includes operations summary, today’s supplies/sales, current/historical inventory, inventory movement, supplier lookup/outstanding/statement/payments, expenses, recent transactions, ambiguous supplier/item, no-result, out-of-scope, user prompt injection, and stored prompt injection.
