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
