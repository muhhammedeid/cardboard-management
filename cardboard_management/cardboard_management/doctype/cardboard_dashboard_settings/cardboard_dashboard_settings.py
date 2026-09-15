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
		self.validate_default_supplier_group()
		self.validate_default_mode_of_payment()

	def validate_default_mode_of_payment(self):
		if not self.default_mode_of_payment:
			return
		from cardboard_management.cardboard_management.doctype.cardboard_supplier_payment.cardboard_supplier_payment import (
			get_mapped_payment_account,
		)

		if not frappe.db.get_value("Mode of Payment", self.default_mode_of_payment, "enabled"):
			frappe.throw(_("Default Mode of Payment must be enabled"))
		get_mapped_payment_account(self.default_mode_of_payment, self.company)

	def validate_default_supplier_group(self):
		supplier_group = frappe.db.get_value(
			"Supplier Group", self.default_supplier_group, ["name", "is_group"], as_dict=True
		)
		if not supplier_group:
			frappe.throw(_("Select a valid Default Supplier Group"))
		if supplier_group.is_group:
			frappe.throw(_("Default Supplier Group must not be a group supplier group"))

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
