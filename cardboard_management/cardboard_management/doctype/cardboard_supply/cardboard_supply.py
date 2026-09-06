import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CardboardSupply(Document):
	def validate(self):
		self.validate_weights_and_rate()
		self.calculate_totals()

	def validate_weights_and_rate(self):
		gross_weight = flt(self.gross_weight)
		tare_weight = flt(self.tare_weight)
		rate_per_kg = flt(self.rate_per_kg)

		if gross_weight <= 0:
			frappe.throw(_("Gross Weight must be greater than zero"))
		if tare_weight < 0:
			frappe.throw(_("Tare Weight cannot be negative"))
		if tare_weight >= gross_weight:
			frappe.throw(_("Tare Weight must be less than Gross Weight"))
		if rate_per_kg < 0:
			frappe.throw(_("Rate per Kg cannot be negative"))

	def calculate_totals(self):
		self.net_weight = flt(
			flt(self.gross_weight) - flt(self.tare_weight), self.precision("net_weight")
		)
		if self.net_weight <= 0:
			frappe.throw(_("Net Weight must be greater than zero"))

		self.total_amount = flt(
			self.net_weight * flt(self.rate_per_kg), self.precision("total_amount")
		)
