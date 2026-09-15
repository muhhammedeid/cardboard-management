# Expense frontend contract

App-owned methods: `list_expenses`, `get_expense`, `lookup_expense_categories`, `lookup_expense_payment_sources`, `get_new_expense_schema`, `create_expense`, `update_expense`, `submit_expense`, `cancel_expense`, `get_expense_capabilities`.

Quick Expense uses `expense_category` (an enabled leaf Expense Account) and `payment_source` (an enabled leaf Cash/Bank Account). These are safe frontend abstractions; account internals, company, Journal Entry and GL data never appear. Inputs are posting date, category, amount, payment source, payment mode, party, description, attachment, reference number/date. Company, accounting document and accounting status are server-owned.

List filters: from/to date, expense category, status, search, page/page_size and sort. Detail returns operational fields and accounting status only. Draft records alone update; submit/cancel delegate to Quick Expense lifecycle so the native Journal Entry remains server-owned. `reporting.get_expense_summary` remains the aggregate reporting API.

Errors use `expense_error` with validation, permission_denied, not_found, invalid_lifecycle, configuration_error, accounting_native_posting_failure, or unexpected_error. All reads/lookups are permission-checked and bounded.
