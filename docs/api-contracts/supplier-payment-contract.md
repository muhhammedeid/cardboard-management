# Supplier Payment frontend contract

All methods are app-owned whitelisted methods under
`cardboard_management.cardboard_management.api.supplier_payments`. They wrap
`Cardboard Supplier Payment`; they never create, update, or cancel ERPNext
`Payment Entry` records directly.

## Methods

| Method | Arguments | Result |
| --- | --- | --- |
| `list_supplier_payments` | `from_date`, `to_date`, `supplier`, `mode_of_payment`, `status`, `search`, `page`, `page_size`, `sort` | paginated operational records |
| `get_supplier_payment` | `name` | payment detail |
| `lookup_suppliers` | `search`, `page_size` | enabled payment-eligible Supplier IDs/names |
| `lookup_modes_of_payment` | `search`, `page_size` | enabled modes with a valid configured Company mapping |
| `get_new_supplier_payment_schema` | none | editable fields, defaults, and capabilities |
| `get_supplier_payment_context` | `supplier` | authoritative Company and current supplier outstanding |
| `create_supplier_payment` | editable fields as kwargs | saved Draft detail |
| `update_supplier_payment` | `name`, editable fields as kwargs | saved Draft detail |
| `submit_supplier_payment` | `name` | submitted detail |
| `cancel_supplier_payment` | `name` | cancelled detail |
| `get_supplier_payment_capabilities` | optional `name` | presentation capability flags |

`page_size` is bounded to 1–100. List sort is allowlisted: `posting_date`,
`supplier`, `amount`, `mode_of_payment`, `status`, `creation`, `modified`, and
`name`. `status` is `Draft`, `Submitted`, or `Cancelled` (case-insensitive).

## DTOs

List records contain only `name`, `posting_date`, `supplier`, `supplier_name`,
`amount`, `mode_of_payment`, `status`, and `docstatus`.

Detail additionally contains `reference_no`, `reference_date`, `notes`,
`payment_status`, `current_supplier_outstanding`,
`expected_remaining_outstanding`, and `capabilities`. `payment_entry` is not a
frontend field.

## Draft schema and defaults

Editable inputs are:

- required: `supplier`, `amount`, `mode_of_payment`, `posting_date`
- optional: `reference_no`, `reference_date`, `notes`

Server-owned fields are `company`, `payment_entry`, `payment_status`,
`current_supplier_outstanding`, and `expected_remaining_outstanding`.

`default_posting_date` is server `nowdate()`. `default_mode_of_payment` comes
only from `Cardboard Dashboard Settings.default_mode_of_payment`; it is never
hardcoded. The lookup returns only enabled modes that have a valid native
Mode-of-Payment Account mapping for the configured Company. No account,
ledger, `paid_from`, or `paid_to` field is exposed.

## Lifecycle and accounting authority

Create and update persist Draft wrapper records only. Update is rejected unless
the wrapper is Draft. Submit delegates to the existing wrapper's `submit()`;
that authoritative logic creates and submits the linked native Payment Entry.
Cancel delegates to the wrapper's `cancel()`; its existing cancellation logic
cancels the linked native Payment Entry. Vue must not calculate outstanding,
remaining outstanding, allocations, account mappings, or reversals.

Document `status`: `Draft` (`docstatus=0`), `Submitted` (`1`), and `Cancelled`
(`2`). `payment_status` is wrapper integration state: `Not Generated` for a
Draft, `Submitted` for a submitted wrapper with a submitted linked Payment
Entry, and `Cancelled` when either the wrapper or its linked entry is
cancelled. `current_supplier_outstanding` and
`expected_remaining_outstanding` are computed by the existing backend and are
informational authoritative values only.

## Context and capabilities

Supplier context returns `{company, current_supplier_outstanding}`; Company
comes from settings and outstanding comes from the existing wrapper service.
Capability flags are presentation hints: `can_create` globally, and document
`can_read`, `can_edit`, `can_submit`, `can_cancel`. Every operation separately
enforces Frappe session authorization and lifecycle rules.

## Errors

Exceptions remain Frappe exceptions. The response includes
`frappe.local.response.supplier_payment_error` with `{code, message, field?}`
when applicable. Codes are `validation`, `permission_denied`, `not_found`,
`invalid_lifecycle`, `invalid_supplier`, `invalid_mode_of_payment`,
`configuration_error`, `accounting_payment_entry_failure`, and
`unexpected_error`. Unexpected errors are logged server-side; tracebacks are
not contract output.
