import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate


class CardboardSupply(Document):
	VALID_DISCOUNT_TYPES = ("No Discount", "Kg", "Percentage")

	def validate(self):
		self.validate_weights_and_rate()
		self.calculate_net_weight()
		self.validate_discount()
		self.calculate_discount_and_payable_weight()
		self.calculate_total_amount()

	def on_submit(self):
		self.create_purchase_invoice()

	def before_cancel(self):
		self.cancel_purchase_invoice()

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

	def create_purchase_invoice(self):
		if self.docstatus != 1:
			frappe.throw(_("Cardboard Supply must be submitted before creating a Purchase Invoice"))

		self._lock_for_integration()
		existing = self._get_linked_purchase_invoice()
		if existing:
			return self._complete_existing_purchase_invoice(existing)

		context = self._get_integration_context()
		purchase_invoice = self._build_purchase_invoice(context)
		purchase_invoice.insert()
		self._validate_purchase_invoice_mapping(purchase_invoice, context)
		purchase_invoice.submit()
		self._validate_purchase_invoice_mapping(purchase_invoice, context)
		self._set_purchase_invoice_link(purchase_invoice.name)
		return purchase_invoice

	def cancel_purchase_invoice(self):
		linked_name = self.purchase_invoice or frappe.db.get_value(
			"Purchase Invoice", {"custom_cardboard_supply": self.name}, "name"
		)
		if not linked_name:
			return

		purchase_invoice = frappe.get_doc("Purchase Invoice", linked_name)
		if purchase_invoice.custom_cardboard_supply != self.name:
			frappe.throw(_("Linked Purchase Invoice does not belong to this Cardboard Supply"))
		if purchase_invoice.docstatus == 1:
			# Temporarily remove the forward link so Frappe can cancel the PI first.
			# The transaction restores it even if PI cancellation raises.
			self.purchase_invoice = None
			self.db_set("purchase_invoice", None, update_modified=False)
			try:
				purchase_invoice.cancel()
			finally:
				self.purchase_invoice = linked_name
				self.db_set("purchase_invoice", linked_name, update_modified=False)
		elif purchase_invoice.docstatus == 0:
			frappe.throw(_("Linked Purchase Invoice must be submitted or cancelled before cancelling Cardboard Supply"))

	def _lock_for_integration(self):
		frappe.db.sql(
			"select name from `tabCardboard Supply` where name = %s for update",
			(self.name,),
		)
		self.purchase_invoice = frappe.db.get_value("Cardboard Supply", self.name, "purchase_invoice")

	def _get_linked_purchase_invoice(self):
		if self.purchase_invoice:
			if not frappe.db.exists("Purchase Invoice", self.purchase_invoice):
				frappe.throw(_("Linked Purchase Invoice {0} does not exist").format(frappe.bold(self.purchase_invoice)))
			return frappe.get_doc("Purchase Invoice", self.purchase_invoice)

		existing_name = frappe.db.get_value(
			"Purchase Invoice", {"custom_cardboard_supply": self.name}, "name"
		)
		return frappe.get_doc("Purchase Invoice", existing_name) if existing_name else None

	def _complete_existing_purchase_invoice(self, purchase_invoice):
		if purchase_invoice.custom_cardboard_supply != self.name:
			frappe.throw(_("Linked Purchase Invoice does not belong to this Cardboard Supply"))
		if purchase_invoice.docstatus == 2:
			frappe.throw(_("Linked Purchase Invoice is cancelled; a duplicate will not be created"))

		context = self._get_integration_context()
		self._validate_purchase_invoice_mapping(purchase_invoice, context)
		if purchase_invoice.docstatus == 0:
			purchase_invoice.submit()
		self._validate_purchase_invoice_mapping(purchase_invoice, context)
		self._set_purchase_invoice_link(purchase_invoice.name)
		return purchase_invoice

	def _get_integration_context(self):
		if flt(self.net_weight) <= 0:
			frappe.throw(_("Net Weight must be greater than zero before Purchase Invoice creation"))
		if flt(self.total_amount) < 0:
			frappe.throw(_("Total Amount cannot be negative before Purchase Invoice creation"))

		supplier = frappe.db.get_value(
			"Supplier", self.supplier, ["name", "disabled"], as_dict=True
		)
		if not supplier or supplier.disabled:
			frappe.throw(_("Supplier must exist and be enabled"))

		item = frappe.db.get_value(
			"Item",
			self.item,
			["name", "disabled", "is_stock_item", "stock_uom"],
			as_dict=True,
		)
		if not item or item.disabled:
			frappe.throw(_("Item must exist and be enabled"))
		if not item.is_stock_item:
			frappe.throw(_("Item must maintain stock"))
		if item.stock_uom != "Kg":
			frappe.throw(_("Item Stock UOM must be Kg"))

		warehouse = frappe.db.get_value(
			"Warehouse",
			self.warehouse,
			["name", "company", "disabled", "is_group"],
			as_dict=True,
		)
		if not warehouse or warehouse.disabled or warehouse.is_group:
			frappe.throw(_("Warehouse must exist, be enabled, and not be a group"))
		if not warehouse.company or not frappe.db.exists("Company", warehouse.company):
			frappe.throw(_("Warehouse must belong to a valid Company"))

		currency = frappe.db.get_value("Company", warehouse.company, "default_currency")
		if not currency:
			frappe.throw(_("Warehouse Company must have a default currency"))

		return frappe._dict(
			company=warehouse.company,
			currency=currency,
			stock_uom=item.stock_uom,
		)

	def _build_purchase_invoice(self, context):
		purchase_invoice = frappe.new_doc("Purchase Invoice")
		purchase_invoice.update(
			{
				"supplier": self.supplier,
				"company": context.company,
				"posting_date": self.posting_date,
				"currency": context.currency,
				"conversion_rate": 1,
				"update_stock": 1,
				"ignore_pricing_rule": 1,
				"custom_cardboard_supply": self.name,
				"remarks": _("Created from Cardboard Supply {0}").format(self.name),
			}
		)
		item = purchase_invoice.append(
			"items",
			{
				"item_code": self.item,
				"warehouse": self.warehouse,
				"qty": self.net_weight,
				"uom": context.stock_uom,
				"stock_uom": context.stock_uom,
				"conversion_factor": 1,
				"allow_zero_valuation_rate": 1 if not flt(self.total_amount) else 0,
			},
		)
		effective_rate = flt(
			flt(self.total_amount) / flt(self.net_weight), item.precision("rate")
		)
		item.rate = effective_rate
		item.price_list_rate = effective_rate
		return purchase_invoice

	def _validate_purchase_invoice_mapping(self, purchase_invoice, context):
		if len(purchase_invoice.items) != 1:
			frappe.throw(_("Linked Purchase Invoice does not match Cardboard Supply"))

		item = purchase_invoice.items[0]
		expected_total = flt(self.total_amount, purchase_invoice.precision("grand_total"))
		expected_rate = flt(
			flt(self.total_amount) / flt(self.net_weight), item.precision("rate")
		)
		expected = {
			"supplier": self.supplier,
			"company": context.company,
			"posting_date": getdate(self.posting_date),
			"update_stock": 1,
			"custom_cardboard_supply": self.name,
			"item_code": self.item,
			"warehouse": self.warehouse,
			"uom": context.stock_uom,
		}
		actual = {
			"supplier": purchase_invoice.supplier,
			"company": purchase_invoice.company,
			"posting_date": getdate(purchase_invoice.posting_date),
			"update_stock": cint(purchase_invoice.update_stock),
			"custom_cardboard_supply": purchase_invoice.custom_cardboard_supply,
			"item_code": item.item_code,
			"warehouse": item.warehouse,
			"uom": item.uom,
		}
		quantities_match = (
			flt(item.qty, item.precision("qty"))
			== flt(self.net_weight, item.precision("qty"))
			and flt(item.stock_qty, item.precision("stock_qty"))
			== flt(self.net_weight, item.precision("stock_qty"))
		)
		financials_match = (
			flt(item.rate, item.precision("rate")) == expected_rate
			and flt(item.amount, item.precision("amount")) == expected_total
			and flt(purchase_invoice.grand_total, purchase_invoice.precision("grand_total"))
			== expected_total
		)
		if actual != expected or not quantities_match or not financials_match:
			frappe.throw(_("Linked Purchase Invoice does not match Cardboard Supply"))

	def _set_purchase_invoice_link(self, purchase_invoice_name):
		self.purchase_invoice = purchase_invoice_name
		self.db_set("purchase_invoice", purchase_invoice_name, update_modified=False)
