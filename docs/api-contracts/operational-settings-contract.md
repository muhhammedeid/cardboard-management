# Operational settings frontend contract

`Cardboard Dashboard Settings` is exposed only through app-owned methods: `get_operational_settings`, `update_operational_settings`, `get_operational_settings_capabilities`, `lookup_companies`, `lookup_warehouses`, `lookup_cardboard_item_groups`, `lookup_supplier_groups`, and `lookup_modes_of_payment`.

The only editable fields are `company`, `default_warehouse`, `cardboard_item_group`, `default_supplier_group`, and `default_mode_of_payment`. Update uses the Settings Document `save()`, so its existing validation remains authoritative for company existence, warehouse Company/leaf/enabled state, supplier-group leaf state, and mapped enabled payment mode. No generic Single DocType mutation is permitted.

Lookups are server-side, bounded to 100, and permission-checked. Warehouse candidates are enabled leaves scoped to a Company; supplier groups are leaves; payment modes reuse the Supplier Payment bounded mapped-mode logic. Responses contain identifiers and display names only. Errors appear in `operational_settings_error` with validation, permission_denied, invalid company/warehouse/item/supplier group/mode, configuration dependency, or unexpected error. Capabilities are presentation hints only.
