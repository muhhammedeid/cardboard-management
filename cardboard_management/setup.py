import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


RATE_PRECISION = 9


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


def _ensure_purchase_invoice_rate_precision():
	filters = {
		"doc_type": "Purchase Invoice Item",
		"field_name": "rate",
		"property": "precision",
	}
	property_setter = frappe.db.get_value("Property Setter", filters, ["name", "value"], as_dict=True)
	if not property_setter:
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
