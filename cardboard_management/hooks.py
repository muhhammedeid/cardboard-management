app_name = "cardboard_management"
app_title = "Cardboard Management"
app_publisher = "Mohamed Eid"
app_description = "Business-specific customization for a local cardboard recycling and trading ERP"
app_email = "muhamedeiddev@gmail.com"
app_license = "mit"

# ERPNext is the ERP engine; Frappe is the framework.
required_apps = ["erpnext"]

# Standard ERPNext schema extensions owned by this custom app.
after_install = "cardboard_management.setup.ensure_purchase_invoice_integration_schema"
after_migrate = "cardboard_management.setup.ensure_purchase_invoice_integration_schema"

# App-owned navigation fixtures. They never assign roles or profiles to users.
fixtures = [
    {"doctype": "Role", "filters": [["name", "=", "Cardboard Operator"]]},
    {"doctype": "Module Profile", "filters": [["name", "=", "Cardboard Operator"]]},
]

# Role-aware User defaults use the native default_workspace field; no client redirects.
doc_events = {
    "User": {"on_update": "cardboard_management.setup.ensure_cardboard_operator_default_workspace"},
}

# App-owned Desk presentation assets (route-scoped in JavaScript/CSS).
app_include_css = [
    "/assets/cardboard_management/css/cardboard_management.css",
    "/assets/cardboard_management/css/cardboard_ui.css",
]
app_include_js = [
    "/assets/cardboard_management/js/cardboard_management.js",
    "/assets/cardboard_management/js/cardboard_ui.js",
]
