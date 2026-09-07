"""Idempotent, app-owned schema extensions for standard ERPNext doctypes.

No ERPNext/Frappe core files are modified; every extension lands as a Custom Field
or Property Setter owned by the Cardboard Management module and is re-ensured by the
after_install / after_migrate hooks.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

RATE_PRECISION = 9

# ERPNext's stock Journal Entry Account.reference_type option list (frappe v15),
# extended with app-owned doctypes so Quick Expense rows can carry a backlink.
JE_ACCOUNT_REFERENCE_TYPES = (
	"\nSales Invoice\nPurchase Invoice\nJournal Entry\nSales Order\nPurchase Order\n"
	"Expense Claim\nAsset\nLoan\nPayroll Entry\nEmployee Advance\n"
	"Exchange Rate Revaluation\nInvoice Discounting\nFees\n"
	"Full and Final Statement\nPayment Entry\nBank Transaction\nQuick Expense\n"
)


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
	"""Extend Journal Entry Account.reference_type options with Quick Expense.

	ERPNext hard-codes the allowed reference doctypes as a Select list on the child
	table. A Property Setter owned by this module is the standard, idempotent,
	uninstallable way to extend those options without editing ERPNext core. The stock
	ERPNext option list is kept intact and only appended to.
	"""
	filters = {
		"doc_type": "Journal Entry Account",
		"field_name": "reference_type",
		"property": "options",
	}
	existing = frappe.db.get_value("Property Setter", filters, ["name", "value"], as_dict=True)
	if existing:
		if "Quick Expense" not in (existing.value or ""):
			frappe.db.set_value("Property Setter", existing.name, "value", JE_ACCOUNT_REFERENCE_TYPES)
			frappe.clear_cache(doctype="Journal Entry Account")
		return
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		"Journal Entry Account",
		"reference_type",
		"options",
		JE_ACCOUNT_REFERENCE_TYPES,
		"Text",
		validate_fields_for_doctype=False,
	)
	frappe.clear_cache(doctype="Journal Entry Account")
