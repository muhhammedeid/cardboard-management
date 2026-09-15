# Supplier frontend contract

All methods are app-owned Frappe whitelisted methods under
`cardboard_management.cardboard_management.api.suppliers`. This is a Supplier
**master** boundary only. Financial and history data remains in:

- `cardboard_management.reporting.get_supplier_summary`
- `cardboard_management.reporting.get_supplier_statement`

The frontend must never derive outstanding, supplied amount, paid amount, or a
statement from Supplier master data or local arrays.

## Frozen master fields

The underlying ERPNext `Supplier` DocType is authoritative. The contract exposes
only approved identity/contact fields:

```ts
type SupplierListItem = {
  name: string;
  supplier_name: string;
  supplier_group?: string;
  disabled: boolean;
};

type SupplierDetail = SupplierListItem & {
  supplier_type: 'Company' | 'Individual' | 'Partnership';
  mobile_no?: string;
  email_id?: string;
  primary_address?: string;
  tax_id?: string;
  supplier_details?: string;
  capabilities: SupplierCapabilities;
};

type SupplierCapabilities = {
  can_read: boolean;
  can_create: boolean;
  can_edit: false;
};
```

`mobile_no`, `email_id`, and `primary_address` are read-only ERPNext contact
representations. This contract does not create contacts or addresses.

## Creation schema

```ts
type CreateSupplierRequest = {
  supplier_name: string; // required
  supplier_type?: 'Company' | 'Individual' | 'Partnership'; // default Company
  tax_id?: string;
  supplier_details?: string;
};
```

Server-managed/read-only fields include `name`, `supplier_group`, `disabled`,
contact/address fields, accounts, currencies, payment terms, and Company or
accounting configuration. The frontend must not send those fields.

`Cardboard Dashboard Settings.default_supplier_group` is required and is
validated as a leaf `Supplier Group`. The server resolves it on creation; no
Supplier Group is hardcoded in the frontend or API.

Supplier update is **deferred**: no update endpoint is exposed because safe
master/contact editing would require a separate approved operational schema.

## Methods

| Method | Arguments | Returns | Notes |
|---|---|---|---|
| `list_suppliers` | `page`, `page_size`, `search`, `status`, `sort` | `{data, page, page_size, total, has_more}` | Server pagination capped at 100. Search checks ID/name and supplier name. `status`: `enabled`/`active` or `disabled`/`inactive`. Default sort: `supplier_name asc`. |
| `get_supplier` | `name` | `SupplierDetail` | Master identity/contact detail only; does not include financial/history data. |
| `get_new_supplier_schema` | none | approved required/optional/read-only/system-managed fields plus default group | Use to build the creation form without inspecting ERPNext metadata. |
| `create_supplier` | `CreateSupplierRequest` | `SupplierDetail` | Resolves configured default Supplier Group server-side and delegates validation/naming to ERPNext. |
| `get_capabilities` | optional `name` | `{capabilities}` or `{name, capabilities}` | Server-authoritative UI hints. |

## Errors

A failed method may return `supplier_error` in Frappe's response:

```ts
type SupplierError = {
  code: 'validation' | 'duplicate_supplier' | 'permission_denied' |
    'not_found' | 'configuration_error' | 'unexpected_error';
  message: string;
  field?: string;
};
```

The API logs unexpected failures server-side and returns a generic client-safe
message; it does not expose tracebacks.

## Permissions

Existing ERPNext Supplier permissions are authoritative. Every public operation
checks the corresponding Supplier permission. Capability flags are UI guidance,
not authorization.

## Frontend implementation

P04-FE06 remains **NOT RESUMED** by this backend contract package.
