import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CardboardSupply(Document):
	VALID_DISCOUNT_TYPES = ("No Discount", "Kg", "Percentage")

	def validate(self):
		self.validate_weights_and_rate()
		self.calculate_net_weight()
		self.validate_discount()
		self.calculate_discount_and_payable_weight()
		self.calculate_total_amount()

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

	def calculate_net_weight(self):
		self.net_weight = flt(
			flt(self.gross_weight) - flt(self.tare_weight), self.precision("net_weight")
		)
		if self.net_weight <= 0:
			frappe.throw(_("Net Weight must be greater than zero"))

	def validate_discount(self):
		self.discount_type = self.discount_type or "No Discount"
		discount_value = flt(self.discount_value)

		if self.discount_type not in self.VALID_DISCOUNT_TYPES:
			frappe.throw(_("Invalid Discount Type: {0}").format(frappe.bold(self.discount_type)))
		if discount_value < 0:
			frappe.throw(_("Discount Value cannot be negative"))
		if self.discount_type == "Kg" and discount_value >= self.net_weight:
			frappe.throw(_("Kg Discount must be less than Net Weight"))
		if self.discount_type == "Percentage" and discount_value >= 100:
			frappe.throw(_("Percentage Discount must be less than 100"))

	def calculate_discount_and_payable_weight(self):
		discount_value = flt(self.discount_value)
		if self.discount_type == "No Discount":
			self.discount_value = 0
			self.discount_weight = 0
		elif self.discount_type == "Kg":
			self.discount_weight = flt(discount_value, self.precision("discount_weight"))
		else:
			self.discount_weight = flt(
				self.net_weight * discount_value / 100, self.precision("discount_weight")
			)

		self.payable_weight = flt(
			self.net_weight - self.discount_weight, self.precision("payable_weight")
		)
		if self.payable_weight <= 0:
			frappe.throw(_("Payable Weight must be greater than zero"))

	def calculate_total_amount(self):
		self.total_amount = flt(
			self.payable_weight * flt(self.rate_per_kg), self.precision("total_amount")
		)
