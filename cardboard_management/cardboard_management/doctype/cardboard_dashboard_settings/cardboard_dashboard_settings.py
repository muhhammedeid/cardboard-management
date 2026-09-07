import frappe
from frappe import _
from frappe.model.document import Document


class CardboardDashboardSettings(Document):
	def validate(self):
		if not frappe.db.exists("Company", self.company):
			frappe.throw(_("Select a valid Company"))
		if not frappe.db.exists("Item Group", self.cardboard_item_group):
			frappe.throw(_("Select a valid Cardboard Item Group"))
