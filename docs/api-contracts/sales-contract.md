# Cardboard Sales frontend contract

All methods are app-owned Frappe whitelisted methods under
`cardboard_management.cardboard_management.api.sales`. Session authentication and
Frappe permissions apply to every method. This contract is a safe frontend
adapter over the existing `Cardboard Sale` DocType/controller; it does not
calculate stock, create stock rows, or post accounting.

## Frozen backend semantics

`Cardboard Sale` fields confirmed from the frozen DocType/controller:

- Buyer is plain text field `buyer_name`; there is no Buyer/Customer master in this workflow.
- Editable Draft fields are `posting_date`, `item`, `quantity`, `rate_per_kg`, `buyer_name`, and `notes`.
- Backend-owned fields are `company`, `warehouse`, `stock_entry`, `total_amount`, `docstatus`, and name.
- `item` is an ERPNext Item but must be scoped to the configured Cardboard Item Group and descendants.
- `company` and `warehouse` resolve from `Cardboard Dashboard Settings` during validation.
- `total_amount` is informational: `quantity * rate_per_kg`; no Sales Invoice, receivable, Payment Entry, revenue GL, or Customer master is created.
- Submit calls the existing `Cardboard Sale.submit()` lifecycle, which validates available stock and creates one native ERPNext `Material Issue` Stock Entry.
- Cancel calls the existing `Cardboard Sale.cancel()` lifecycle, which cancels the linked Stock Entry and restores stock through ERPNext.

The frontend must not calculate stock availability, stock deduction, stock
reversal, `total_amount`, company/warehouse scope, or lifecycle side effects.

## Error envelope

Successful calls return their documented value in Frappe's normal `message`
field. List calls return `{data, page, page_size, total, has_more}`.

On failure, clients should read `sale_error` from the response when present:

```ts
type SaleError = {
  code: 'validation' | 'insufficient_stock' | 'permission_denied' |
    'not_found' | 'invalid_state' | 'configuration_error' |
    'unexpected_error';
  message: string;
  field?: string;
}
```

Insufficient stock is normalized as:

```json
{"code":"insufficient_stock","field":"quantity","message":"..."}
```

## DTOs

```ts
type SaleStatus = 'Draft' | 'Submitted' | 'Cancelled';

type SaleListItem = {
  name: string;
  posting_date: string;
  buyer_name?: string;
  item: string;
  item_name: string;
  quantity: number;
  rate_per_kg: number;
  total_amount: number;
  informational_value: number;
  status: SaleStatus;
  docstatus: 0 | 1 | 2;
};

type SaleCapabilities = {
  can_edit: boolean;
  can_submit: boolean;
  can_cancel: boolean;
};

type SaleDetail = SaleListItem & {
  notes?: string;
  company: string;
  warehouse: string;
  stock_entry?: string;
  capabilities: SaleCapabilities;
};
```

`stock_entry` is returned only as an audit/reference link already present on the
frozen operational DocType. The frontend must not inspect or manipulate native
Stock Entry internals.

## Methods

| Method | Arguments | Returns | Notes |
|---|---|---|---|
| `list_sales` | `from_date`, `to_date`, `item`, `buyer`, `status`, `search`, `page`, `page_size`, `sort` | paged `SaleListItem[]` | Permission-aware server pagination. Page size capped at 100. Default order is `posting_date desc, creation desc, name desc`. Sort field is allowlisted. |
| `get_sale` | `name` | `SaleDetail` | Read permission required. Values are authoritative from the saved document. |
| `lookup_buyers` | `search`, `page_size` | `{data: {buyer_name: string}[]}` | Buyer suggestions come from existing accessible Cardboard Sale rows. No Buyer/Customer master is introduced. Results are deduped and capped. |
| `lookup_items` | `search`, `page_size` | `{data: {name, item_name, item_group, stock_uom}[]}` | Reuses the shared app-owned cardboard item lookup; enabled stock Kg Items in configured Item Group descendants only. |
| `create_sale` | editable fields below | `SaleDetail` | Creates Draft sale and returns the backend-calculated document. Company/warehouse are resolved by the controller. |
| `update_sale` | `name`, editable fields below | `SaleDetail` | Draft only; arbitrary field mutation is rejected. |
| `submit_sale` | `name` | `SaleDetail` | Calls native document submit; existing stock validation and Material Issue generation remain authoritative. |
| `cancel_sale` | `name` | `SaleDetail` | Calls native document cancel; existing Stock Entry reversal remains authoritative. |
| `get_capabilities` | `name` | `{name, capabilities}` | Server-calculated UI hints. Action endpoints still enforce permissions/state. |
| `get_form_action` | `name` | `{name, url, desk_route, query}` | Optional link to the legacy Desk form while Vue is below parity. |

Editable create/update fields are: `posting_date`, `item`, `quantity`,
`rate_per_kg`, `buyer_name`, and `notes`.

## Filters

`status` accepts `Draft`, `Submitted`, or `Cancelled` (lowercase aliases are also
accepted). `buyer` filters `buyer_name` by contains text. `search` searches sale
name, buyer text, and item code. Date filters use `posting_date`.

## Permissions

The API relies on existing DocType permissions and checks each operation:

- list/detail: read permission;
- create/update: create/write permission through insert/save;
- submit: submit permission and Draft state;
- cancel: cancel permission and Submitted state;
- lookups: permission-aware bounded reads.

Capability flags are presentation hints and must not be treated as authorization.

## Frontend implementation status

P04-FE05 remains **NOT RESUMED** by this backend contract package.
