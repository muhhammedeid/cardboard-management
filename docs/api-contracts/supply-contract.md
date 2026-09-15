# Cardboard Supply frontend contract

All methods are app-owned Frappe whitelisted methods under
`cardboard_management.api.supply`. The Vue adapter must call these methods and
must not use generic Frappe resource endpoints for Supply workflow operations.
Session authentication and Frappe permissions apply to every method.

## Response envelope

Successful calls return their documented value in Frappe's normal `message`
field. List calls return `{data, page, page_size, total, has_more}`.

On failure, the adapter should read `supply_error` from the response when
present:

```ts
type SupplyError = {
  code: 'validation_error' | 'permission_denied' | 'not_found' |
    'invalid_state' | 'configuration_error' | 'scale_error' |
    'invalid_field' | 'unexpected_error';
  message: string;
  field?: string;
}
```

The backend still enforces permissions, lifecycle, and DocType validation;
capability flags are presentation hints only.

## DTOs

```ts
type SupplyListItem = {
  name: string; posting_date: string; supplier: string; supplier_name: string;
  item: string; item_name: string; payable_weight: number; total_amount: number;
  status: 'Draft' | 'Submitted' | 'Cancelled'; docstatus: 0 | 1 | 2;
}

type SupplyCapabilities = {
  can_edit: boolean; can_submit: boolean; can_cancel: boolean;
  can_capture_gross: boolean; can_capture_tare: boolean; can_print: boolean;
}

type SupplyDetail = SupplyListItem & {
  warehouse: string; gross_weight: number; tare_weight: number; net_weight: number;
  discount_type: 'No Discount' | 'Kg' | 'Percentage'; discount_value: number;
  discount_weight: number; display_payable_weight: number; rate_per_kg: number;
  purchase_invoice?: string; payment_status?: string;
  purchase_invoice_outstanding?: number; invoice_total?: number;
  invoice_paid_amount?: number; integration_status?: string;
  vehicle_no?: string; driver_name?: string; weight_ticket?: string;
  supplier_receipt?: string; notes?: string; capabilities: SupplyCapabilities;
}
```

## Methods

| Method | Arguments | Returns | Notes |
|---|---|---|---|
| `list_supplies` | `date_from`, `date_to`, `supplier`, `item`, `status`, `search`, `page`, `page_size`, `sort` | paged `SupplyListItem[]` | Server filtering/pagination; page size capped at 100. Sort field is allowlisted. |
| `get_supply` | `name` | `SupplyDetail` | Read permission required. Derived/payment values are authoritative. |
| `lookup_suppliers` | `search`, `page_size` | `{data: {name, supplier_name}[]}` | Enabled suppliers only; bounded. |
| `lookup_items` | `search`, `page_size` | `{data: {name, item_name, item_group, stock_uom}[]}` | Enabled stock items in configured Cardboard Item Group descendants; bounded. |
| `create_supply` | editable fields below | `SupplyDetail` | Warehouse comes from Cardboard Dashboard Settings. DocType validation runs on insert. |
| `update_supply` | `name`, editable fields below | `SupplyDetail` | Draft only; arbitrary field mutation is rejected. |
| `submit_supply` | `name` | `SupplyDetail` | Uses native `doc.submit()` and existing invoice/stock/accounting integration. |
| `cancel_supply` | `name` | `SupplyDetail` | Uses native `doc.cancel()` and existing reversal behavior. |
| `capture_gross_weight` | `name`, `weight` optional | `{field, weight, supply}` | Draft/write permission required. A registered scale adapter supplies the normalized Kg value; missing value returns `scale_error`. |
| `capture_tare_weight` | `name`, `weight` optional | `{field, weight, supply}` | Same rules as gross capture. |
| `get_capabilities` | `name` | `{name, capabilities}` | Server-calculated action availability; never trust flags for authorization. |
| `get_print_action` | `name` | `{name, format, url}` | Read permission required; reuses `Cardboard Supply Ticket` print format. |

Editable create/update fields are: `posting_date`, `supplier`, `item`,
`gross_weight`, `tare_weight`, `rate_per_kg`, `discount_type`,
`discount_value`, `vehicle_no`, `driver_name`, `weight_ticket`,
`supplier_receipt`, and `notes`. `warehouse`, company, invoice, derived
weights, totals, payment status, and integration fields are backend-owned.

The frontend must not calculate net weight, discount weight, payable weight,
total amount, payment status, invoice outstanding, submit/cancel side effects,
or print markup.
