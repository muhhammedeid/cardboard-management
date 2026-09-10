import frappe
from frappe import _
from frappe.model.document import Document


class CardboardDashboardSettings(Document):
	def validate(self):
		if not frappe.db.exists("Company", self.company):
			frappe.throw(_("Select a valid Company"))
		if not frappe.db.exists("Item Group", self.cardboard_item_group):
			frappe.throw(_("Select a valid Cardboard Item Group"))
		self.validate_default_warehouse()

	def validate_default_warehouse(self):
		if not self.default_warehouse:
			return
		warehouse = frappe.db.get_value(
			"Warehouse",
			self.default_warehouse,
			["name", "company", "disabled", "is_group"],
			as_dict=True,
		)
		if not warehouse:
			frappe.throw(_("Select a valid Default Warehouse"))
		if warehouse.disabled:
			frappe.throw(_("Default Warehouse must be enabled"))
		if warehouse.is_group:
			frappe.throw(_("Default Warehouse must not be a group warehouse"))
		if warehouse.company != self.company:
			frappe.throw(_("Default Warehouse must belong to the selected Company"))
