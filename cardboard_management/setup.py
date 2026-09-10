"""Idempotent, app-owned schema extensions for standard ERPNext doctypes.

No ERPNext/Frappe core files are modified; every extension lands as a Custom Field
or Property Setter owned by the Cardboard Management module and is re-ensured by the
after_install / after_migrate hooks.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

RATE_PRECISION = 9

REQUIRED_JE_ACCOUNT_REFERENCE_TYPE = "Quick Expense"

OPERATOR_ROLE = "Cardboard Operator"
OPERATOR_WORKSPACE = "Cardboard Management"
OPERATOR_PERMISSIONS = {
	"Cardboard Supply": {"read", "write", "create", "submit"},
	"Quick Expense": {"read", "write", "create", "submit"},
	"Cardboard Supplier Payment": {"read", "write", "create", "submit"},
	"Cardboard Sale": {"read", "write", "create", "submit"},
	"Cardboard Dashboard Settings": {"read", "write"},
	"Supplier": {"read", "write", "create"},
	# Read-only dependencies required by Supplier account resolution and report links.
	"Account": {"read"},
	"Currency": {"read"},
	"Supplier Group": {"read"},
	"Party Type": {"read"},
	"Journal Entry": {"read"},
	"Payment Ledger Entry": {"read"},
	"Company": {"read"},
	"Item": {"read"},
	"Item Group": {"read"},
	"UOM": {"read"},
	"Warehouse Type": {"read"},
	"Warehouse": {"read"},
	"Stock Ledger Entry": {"read", "report"},
	"Purchase Invoice": {"read", "report"},
}
OPERATOR_REPORTS = ("Stock Balance", "Accounts Payable", "Purchase Register")
OPERATOR_PERMISSION_FIELDS = (
	"read",
	"write",
	"create",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"import",
	"share",
	"print",
	"email",
	"if_owner",
)


def merge_reference_type_options(*option_sources):
	"""Merge Select option sources without discarding upstream extensions.

	The leading/trailing newline is the standard Frappe Select representation.
	Order is stable: stock options first, then any existing Property Setter values,
	then Cardboard's required option.
	"""
	options = []
	for source in option_sources:
		for option in (source or "").splitlines():
			option = option.strip()
			if option and option not in options:
				options.append(option)
	return "\n" + "\n".join(options) + "\n"


def ensure_purchase_invoice_integration_schema():
	create_custom_fields(
		{
			"Purchase Invoice": [
				{
					"fieldname": "custom_cardboard_supply",
					"label": "Cardboard Supply",
					"fieldtype": "Link",
					"options": "Cardboard Supply",
					"insert_after": "remarks",
					"read_only": 1,
					"no_copy": 1,
					"unique": 1,
					"in_standard_filter": 1,
					"module": "Cardboard Management",
				}
			]
		},
		update=True,
	)
	_ensure_purchase_invoice_rate_precision()
	_ensure_journal_entry_account_reference_type()
	_ensure_cardboard_operator_permissions()
	ensure_cardboard_operator_defaults()


def _ensure_purchase_invoice_rate_precision():
	filters = {
		"doc_type": "Purchase Invoice Item",
		"field_name": "rate",
		"property": "precision",
	}
	property_setter = frappe.db.get_value("Property Setter", filters, ["name", "value"], as_dict=True)
	if not property_setter:
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		make_property_setter(
			"Purchase Invoice Item",
			"rate",
			"precision",
			str(RATE_PRECISION),
			"Int",
			validate_fields_for_doctype=False,
		)
	elif int(property_setter.value or 0) != RATE_PRECISION:
		frappe.db.set_value("Property Setter", property_setter.name, "value", str(RATE_PRECISION))
	frappe.clear_cache(doctype="Purchase Invoice Item")


def _ensure_journal_entry_account_reference_type():
	"""Preserve stock/future options and append the app-owned Quick Expense type."""
	filters = {
		"doc_type": "Journal Entry Account",
		"field_name": "reference_type",
		"property": "options",
	}
	doctype = frappe.get_doc("DocType", "Journal Entry Account")
	stock_field = next((field for field in doctype.fields if field.fieldname == "reference_type"), None)
	stock_options = stock_field.options if stock_field else ""
	existing = frappe.db.get_value("Property Setter", filters, ["name", "value"], as_dict=True)
	options = merge_reference_type_options(
		stock_options,
		existing.value if existing else "",
		REQUIRED_JE_ACCOUNT_REFERENCE_TYPE,
	)
	if existing:
		if (existing.value or "") != options:
			frappe.db.set_value("Property Setter", existing.name, "value", options)
			frappe.clear_cache(doctype="Journal Entry Account")
		return
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		"Journal Entry Account",
		"reference_type",
		"options",
		options,
		"Text",
		validate_fields_for_doctype=False,
	)
	frappe.clear_cache(doctype="Journal Entry Account")


def _ensure_cardboard_operator_permissions():
	"""Converge app-owned operator rows to the exact least-privilege policy."""
	from frappe.permissions import add_permission, update_permission_property

	for doctype, permissions in OPERATOR_PERMISSIONS.items():
		rows = frappe.get_all(
			"Custom DocPerm",
			filters={"parent": doctype, "role": OPERATOR_ROLE, "permlevel": 0, "if_owner": 0},
			pluck="name",
		)
		if not rows:
			add_permission(doctype, OPERATOR_ROLE)
		for permission in OPERATOR_PERMISSION_FIELDS:
			update_permission_property(
				doctype,
				OPERATOR_ROLE,
				0,
				permission,
				1 if permission in permissions else 0,
				validate=False,
			)

	for report in OPERATOR_REPORTS:
		custom_role_name = frappe.db.get_value("Custom Role", {"report": report}, "name")
		if custom_role_name:
			custom_role = frappe.get_doc("Custom Role", custom_role_name)
			if OPERATOR_ROLE not in {row.role for row in custom_role.roles}:
				custom_role.append("roles", {"role": OPERATOR_ROLE})
				custom_role.save(ignore_permissions=True)
			continue
		frappe.get_doc(
			{"doctype": "Custom Role", "report": report, "roles": [{"role": OPERATOR_ROLE}]}
		).insert(ignore_permissions=True)

	frappe.clear_cache()


def ensure_cardboard_operator_default_workspace(doc, method=None):
	"""Use Frappe's native User.default_workspace; never redirect Administrators."""
	if doc.name == "Administrator" or OPERATOR_ROLE not in {row.role for row in doc.get("roles", [])}:
		return
	if doc.default_workspace != OPERATOR_WORKSPACE:
		frappe.db.set_value("User", doc.name, "default_workspace", OPERATOR_WORKSPACE, update_modified=False)
		frappe.clear_cache(user=doc.name)


def ensure_cardboard_operator_defaults():
	for user in frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": OPERATOR_ROLE},
		pluck="parent",
	):
		ensure_cardboard_operator_default_workspace(frappe.get_doc("User", user))
