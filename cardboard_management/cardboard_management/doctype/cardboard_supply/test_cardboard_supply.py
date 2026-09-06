from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, nowdate

from cardboard_management.cardboard_management.doctype.cardboard_supply.cardboard_supply import CardboardSupply


class TestCardboardSupply(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.supplier = "_Test Cardboard Supply Supplier"
		supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		if not supplier_group:
			raise AssertionError("Cardboard Supply tests require one non-group Supplier Group")
		if not frappe.db.exists("Supplier", cls.supplier):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": cls.supplier,
					"supplier_group": supplier_group,
					"supplier_type": "Company",
				}
			).insert()

		cls.item = frappe.db.get_value(
			"Item", {"disabled": 0, "is_stock_item": 1, "stock_uom": "Kg"}, "name"
		)
		cls.warehouse = frappe.db.get_value(
			"Warehouse", {"disabled": 0, "is_group": 0, "company": ("is", "set")}, "name"
		)
		if not cls.item or not cls.warehouse:
			raise AssertionError("Cardboard Supply tests require one enabled Kg stock Item and valid Warehouse")

	def make_supply(self, **overrides):
		values = {
			"doctype": "Cardboard Supply",
			"posting_date": nowdate(),
			"supplier": self.supplier,
			"item": self.item,
			"warehouse": self.warehouse,
			"gross_weight": 1250,
			"tare_weight": 250,
			"discount_type": "No Discount",
			"discount_value": 0,
			"rate_per_kg": 2.75,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def get_cash_or_bank_account(self, company):
		account = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"is_group": 0,
				"disabled": 0,
				"account_type": ("in", ("Cash", "Bank")),
			},
			"name",
		)
		if not account:
			raise AssertionError("Cardboard Supply payment tests require one enabled Cash or Bank account")
		return account

	def test_no_discount_preserves_physical_net_weight(self):
		supply = self.make_supply(discount_value=100)
		supply.validate()

		self.assertEqual(supply.net_weight, 1000)
		self.assertEqual(supply.discount_value, 0)
		self.assertEqual(supply.discount_weight, 0)
		self.assertEqual(supply.payable_weight, 1000)
		self.assertEqual(supply.total_amount, 2750)

	def test_kg_discount_reduces_only_payable_weight(self):
		supply = self.make_supply(discount_type="Kg", discount_value=100)
		supply.validate()

		self.assertEqual(supply.net_weight, 1000)
		self.assertEqual(supply.discount_weight, 100)
		self.assertEqual(supply.payable_weight, 900)
		self.assertEqual(supply.total_amount, 2475)

	def test_percentage_discount_reduces_only_payable_weight(self):
		supply = self.make_supply(discount_type="Percentage", discount_value=10)
		supply.validate()

		self.assertEqual(supply.net_weight, 1000)
		self.assertEqual(supply.discount_weight, 100)
		self.assertEqual(supply.payable_weight, 900)
		self.assertEqual(supply.total_amount, 2475)

	def test_zero_discount_is_valid_for_kg_and_percentage(self):
		for discount_type in ("Kg", "Percentage"):
			with self.subTest(discount_type=discount_type):
				supply = self.make_supply(discount_type=discount_type, discount_value=0)
				supply.validate()
				self.assertEqual(supply.discount_weight, 0)
				self.assertEqual(supply.payable_weight, 1000)
				self.assertEqual(supply.total_amount, 2750)

	def test_server_overwrites_all_client_supplied_derived_values(self):
		supply = self.make_supply(
			discount_type="Percentage",
			discount_value=10,
			net_weight=999,
			discount_weight=999,
			payable_weight=999,
			total_amount=999,
		)
		supply.validate()

		self.assertEqual(supply.net_weight, 1000)
		self.assertEqual(supply.discount_weight, 100)
		self.assertEqual(supply.payable_weight, 900)
		self.assertEqual(supply.total_amount, 2475)

	def test_valid_supply_can_be_saved_and_submitted(self):
		supply = self.make_supply(discount_type="Percentage", discount_value=10).insert()

		self.assertRegex(supply.name, rf"^CS-{getdate(supply.posting_date).year}-\d{{5}}$")
		self.assertEqual(supply.net_weight, 1000)
		self.assertEqual(supply.payable_weight, 900)
		self.assertEqual(supply.total_amount, 2475)
		supply.submit()

		self.assertEqual(supply.docstatus, 1)

	def test_submit_creates_submitted_purchase_invoice_with_physical_stock_qty(self):
		supply = self.make_supply(
			gross_weight=1150,
			tare_weight=250,
			discount_type="Kg",
			discount_value=50,
			rate_per_kg=6.5,
		).insert()
		supply.submit()

		self.assertTrue(supply.purchase_invoice)
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		self.assertEqual(purchase_invoice.docstatus, 1)
		self.assertEqual(purchase_invoice.update_stock, 1)
		self.assertEqual(len(purchase_invoice.items), 1)
		self.assertEqual(purchase_invoice.items[0].qty, 900)
		self.assertEqual(purchase_invoice.items[0].stock_qty, 900)
		self.assertAlmostEqual(purchase_invoice.items[0].rate, 5525 / 900, places=9)
		self.assertEqual(purchase_invoice.items[0].amount, 5525)
		self.assertEqual(purchase_invoice.grand_total, 5525)
		self.assertEqual(purchase_invoice.supplier, supply.supplier)
		self.assertEqual(purchase_invoice.posting_date, getdate(supply.posting_date))
		self.assertEqual(
			purchase_invoice.company,
			frappe.db.get_value("Warehouse", supply.warehouse, "company"),
		)
		self.assertEqual(purchase_invoice.items[0].item_code, supply.item)
		self.assertEqual(purchase_invoice.items[0].warehouse, supply.warehouse)
		self.assertEqual(purchase_invoice.items[0].uom, "Kg")
		self.assertEqual(purchase_invoice.custom_cardboard_supply, supply.name)
		self.assertIn(supply.name, purchase_invoice.remarks)

	def test_unpaid_supply_derives_full_purchase_invoice_outstanding(self):
		supply = self.make_supply().insert()
		supply.submit()
		supply.reload()
		supply.onload()
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)

		self.assertEqual(supply.purchase_invoice_outstanding, purchase_invoice.grand_total)
		self.assertEqual(supply.payment_status, "Unpaid")

	def test_record_payment_builds_standard_unsubmitted_payment_entry(self):
		supply = self.make_supply().insert()
		supply.submit()
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		cash_or_bank_account = self.get_cash_or_bank_account(purchase_invoice.company)

		payment_entry = supply.make_payment_entry(cash_or_bank_account)

		self.assertEqual(payment_entry.doctype, "Payment Entry")
		self.assertEqual(payment_entry.docstatus, 0)
		self.assertTrue(payment_entry.is_new())
		self.assertEqual(payment_entry.payment_type, "Pay")
		self.assertEqual(payment_entry.party_type, "Supplier")
		self.assertEqual(payment_entry.party, supply.supplier)
		self.assertEqual(payment_entry.company, purchase_invoice.company)
		self.assertEqual(getdate(payment_entry.posting_date), getdate(nowdate()))
		self.assertEqual(payment_entry.paid_from, cash_or_bank_account)
		self.assertEqual(payment_entry.paid_to, purchase_invoice.credit_to)
		self.assertEqual(len(payment_entry.references), 1)
		reference = payment_entry.references[0]
		self.assertEqual(reference.reference_doctype, "Purchase Invoice")
		self.assertEqual(reference.reference_name, purchase_invoice.name)
		self.assertEqual(reference.outstanding_amount, purchase_invoice.outstanding_amount)
		self.assertEqual(reference.allocated_amount, purchase_invoice.outstanding_amount)

	def submit_payment(self, supply, amount=None):
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		account = self.get_cash_or_bank_account(purchase_invoice.company)
		payment_entry = supply.make_payment_entry(account)
		if amount is not None:
			payment_entry.paid_amount = amount
			payment_entry.received_amount = amount
			payment_entry.references[0].allocated_amount = amount
		payment_entry.insert()
		payment_entry.submit()
		return payment_entry

	def test_full_payment_clears_outstanding_and_derives_paid_status(self):
		supply = self.make_supply().insert()
		supply.submit()

		payment_entry = self.submit_payment(supply)
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		supply.reload()
		supply.onload()

		self.assertEqual(payment_entry.docstatus, 1)
		self.assertEqual(purchase_invoice.outstanding_amount, 0)
		self.assertEqual(supply.purchase_invoice_outstanding, 0)
		self.assertEqual(supply.payment_status, "Paid")

	def test_partial_payment_reduces_outstanding_and_derives_partial_status(self):
		supply = self.make_supply(gross_weight=1150, tare_weight=250, discount_type="Kg", discount_value=50, rate_per_kg=6.5).insert()
		supply.submit()

		self.submit_payment(supply, 2000)
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		supply.reload()
		supply.onload()

		self.assertEqual(purchase_invoice.grand_total, 5525)
		self.assertEqual(purchase_invoice.outstanding_amount, 3525)
		self.assertEqual(supply.purchase_invoice_outstanding, 3525)
		self.assertEqual(supply.payment_status, "Partially Paid")

	def test_payment_entry_rejects_allocation_above_current_outstanding(self):
		supply = self.make_supply().insert()
		supply.submit()
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		account = self.get_cash_or_bank_account(purchase_invoice.company)
		payment_entry = supply.make_payment_entry(account)
		overpayment = purchase_invoice.outstanding_amount + 1
		payment_entry.paid_amount = overpayment
		payment_entry.received_amount = overpayment
		payment_entry.references[0].allocated_amount = overpayment

		with self.assertRaisesRegex(frappe.ValidationError, "Allocated Amount cannot be greater"):
			payment_entry.insert()

	def test_payment_cannot_be_initiated_for_cancelled_purchase_invoice(self):
		supply = self.make_supply().insert()
		supply.submit()
		purchase_invoice_name = supply.purchase_invoice
		frappe.db.set_value("Purchase Invoice", purchase_invoice_name, "docstatus", 2, update_modified=False)
		try:
			with self.assertRaisesRegex(frappe.ValidationError, "must be submitted and not cancelled"):
				supply.make_payment_entry(self.get_cash_or_bank_account(frappe.db.get_value("Warehouse", supply.warehouse, "company")))
		finally:
			frappe.db.set_value("Purchase Invoice", purchase_invoice_name, "docstatus", 1, update_modified=False)

	def test_payment_cannot_be_initiated_for_fully_paid_purchase_invoice(self):
		supply = self.make_supply().insert()
		supply.submit()
		self.submit_payment(supply)

		with self.assertRaisesRegex(frappe.ValidationError, "already fully paid"):
			supply.make_payment_entry(self.get_cash_or_bank_account(frappe.db.get_value("Warehouse", supply.warehouse, "company")))

	def test_payment_initiation_uses_authoritative_saved_supply_values(self):
		supply = self.make_supply().insert()
		supply.submit()
		purchase_invoice_name = supply.purchase_invoice
		company = frappe.db.get_value("Purchase Invoice", purchase_invoice_name, "company")
		supply.purchase_invoice = "ATTACKER-INVOICE"
		supply.supplier = "ATTACKER-SUPPLIER"

		payment_entry = supply.make_payment_entry(self.get_cash_or_bank_account(company))

		self.assertEqual(payment_entry.party, self.supplier)
		self.assertEqual(payment_entry.references[0].reference_name, purchase_invoice_name)

	def test_payment_initiation_rejects_supplier_mismatch(self):
		supply = self.make_supply().insert()
		supply.submit()
		other_supplier = "_Test Cardboard Supply Other Supplier"
		if not frappe.db.exists("Supplier", other_supplier):
			supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
			frappe.get_doc({"doctype": "Supplier", "supplier_name": other_supplier, "supplier_group": supplier_group, "supplier_type": "Company"}).insert()
		frappe.db.set_value("Purchase Invoice", supply.purchase_invoice, "supplier", other_supplier, update_modified=False)
		try:
			with self.assertRaisesRegex(frappe.ValidationError, "supplier does not match"):
				supply.make_payment_entry(self.get_cash_or_bank_account(frappe.db.get_value("Warehouse", supply.warehouse, "company")))
		finally:
			frappe.db.set_value("Purchase Invoice", supply.purchase_invoice, "supplier", supply.supplier, update_modified=False)

	def test_payment_cancellation_restores_outstanding_and_unpaid_status(self):
		supply = self.make_supply().insert()
		supply.submit()
		payment_entry = self.submit_payment(supply)

		payment_entry.cancel()
		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		supply.reload()
		supply.onload()

		self.assertEqual(payment_entry.docstatus, 2)
		self.assertEqual(purchase_invoice.outstanding_amount, purchase_invoice.grand_total)
		self.assertEqual(supply.purchase_invoice_outstanding, purchase_invoice.grand_total)
		self.assertEqual(supply.payment_status, "Unpaid")

	def test_payment_entry_uses_only_standard_gl_posting(self):
		supply = self.make_supply().insert()
		supply.submit()
		payment_entry = self.submit_payment(supply, 100)
		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Payment Entry", "voucher_no": payment_entry.name, "is_cancelled": 0},
			fields=["voucher_type", "voucher_no"],
		)

		self.assertTrue(gl_entries)
		self.assertTrue(all(row.voucher_type == "Payment Entry" and row.voucher_no == payment_entry.name for row in gl_entries))

	def test_payment_initiation_validates_supply_link_and_account(self):
		draft_supply = self.make_supply().insert()
		with self.assertRaisesRegex(frappe.ValidationError, "must be submitted"):
			draft_supply.make_payment_entry(self.get_cash_or_bank_account(frappe.db.get_value("Warehouse", draft_supply.warehouse, "company")))

		supply = self.make_supply().insert()
		supply.submit()
		with self.assertRaisesRegex(frappe.ValidationError, "Select an enabled Cash or Bank account"):
			supply.make_payment_entry(frappe.db.get_value("Purchase Invoice", supply.purchase_invoice, "credit_to"))

	def test_zero_tare_and_zero_rate_are_valid(self):
		supply = self.make_supply(gross_weight=100, tare_weight=0, rate_per_kg=0).insert()

		self.assertEqual(supply.net_weight, 100)
		self.assertEqual(supply.total_amount, 0)

	def test_submit_does_not_create_separate_receipt_or_stock_entry(self):
		doctypes = ("Purchase Receipt", "Stock Entry")
		counts_before = {doctype: frappe.db.count(doctype) for doctype in doctypes}

		self.make_supply().insert().submit()

		self.assertEqual({doctype: frappe.db.count(doctype) for doctype in doctypes}, counts_before)

	def test_rejects_non_positive_gross_weight(self):
		for gross_weight in (0, -1):
			with self.subTest(gross_weight=gross_weight):
				with self.assertRaisesRegex(frappe.ValidationError, "Gross Weight must be greater than zero"):
					self.make_supply(gross_weight=gross_weight).validate()

	def test_rejects_negative_tare_weight(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Tare Weight cannot be negative"):
			self.make_supply(tare_weight=-1).validate()

	def test_rejects_tare_weight_not_less_than_gross_weight(self):
		for tare_weight in (1250, 1251):
			with self.subTest(tare_weight=tare_weight):
				with self.assertRaisesRegex(frappe.ValidationError, "Tare Weight must be less than Gross Weight"):
					self.make_supply(tare_weight=tare_weight).validate()

	def test_rejects_negative_discount_value(self):
		for discount_type in ("No Discount", "Kg", "Percentage"):
			with self.subTest(discount_type=discount_type):
				with self.assertRaisesRegex(frappe.ValidationError, "Discount Value cannot be negative"):
					self.make_supply(discount_type=discount_type, discount_value=-1).validate()

	def test_rejects_kg_discount_not_less_than_net_weight(self):
		for discount_value in (1000, 1001):
			with self.subTest(discount_value=discount_value):
				with self.assertRaisesRegex(
					frappe.ValidationError, "Kg Discount must be less than Net Weight"
				):
					self.make_supply(discount_type="Kg", discount_value=discount_value).validate()

	def test_rejects_percentage_discount_at_or_above_100(self):
		for discount_value in (100, 101):
			with self.subTest(discount_value=discount_value):
				with self.assertRaisesRegex(
					frappe.ValidationError, "Percentage Discount must be less than 100"
				):
					self.make_supply(discount_type="Percentage", discount_value=discount_value).validate()

	def test_rejects_negative_rate_per_kg(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rate per Kg cannot be negative"):
			self.make_supply(rate_per_kg=-0.01).validate()

	def test_stock_ledger_and_supplier_payable_use_different_weight_semantics(self):
		supply = self.make_supply(
			gross_weight=1150,
			tare_weight=250,
			discount_type="Kg",
			discount_value=50,
			rate_per_kg=6.5,
		).insert()
		supply.submit()

		stock_quantity = frappe.db.sql(
			"""select coalesce(sum(actual_qty), 0)
			from `tabStock Ledger Entry`
			where voucher_type = %s and voucher_no = %s""",
			("Purchase Invoice", supply.purchase_invoice),
		)[0][0]
		payable_entries = frappe.get_all(
			"GL Entry",
			filters={
				"voucher_type": "Purchase Invoice",
				"voucher_no": supply.purchase_invoice,
				"party_type": "Supplier",
				"party": supply.supplier,
				"is_cancelled": 0,
			},
			fields=["credit", "debit"],
		)

		self.assertEqual(stock_quantity, 900)
		self.assertEqual(sum(row.credit - row.debit for row in payable_entries), 5525)

	def test_all_discount_modes_receive_physical_net_weight_into_stock(self):
		for discount_type, discount_value in (
			("No Discount", 0),
			("Kg", 100),
			("Percentage", 10),
		):
			with self.subTest(discount_type=discount_type):
				supply = self.make_supply(
					discount_type=discount_type,
					discount_value=discount_value,
				).insert()
				supply.submit()
				stock_quantity = frappe.db.sql(
					"""select coalesce(sum(actual_qty), 0)
					from `tabStock Ledger Entry`
					where voucher_type = %s and voucher_no = %s""",
					("Purchase Invoice", supply.purchase_invoice),
				)[0][0]
				self.assertEqual(stock_quantity, supply.net_weight)

	def test_purchase_invoice_creation_is_idempotent(self):
		supply = self.make_supply().insert()
		supply.submit()
		linked_name = supply.purchase_invoice

		first_retry = supply.create_purchase_invoice()
		frappe.db.set_value("Cardboard Supply", supply.name, "purchase_invoice", None)
		supply.purchase_invoice = None
		second_retry = supply.create_purchase_invoice()

		self.assertEqual(first_retry.name, linked_name)
		self.assertEqual(second_retry.name, linked_name)
		self.assertEqual(
			frappe.db.count("Purchase Invoice", {"custom_cardboard_supply": supply.name}),
			1,
		)

	def test_retry_rejects_a_tampered_linked_purchase_invoice(self):
		supply = self.make_supply().insert()
		supply.submit()
		item_row = frappe.db.get_value(
			"Purchase Invoice Item",
			{"parent": supply.purchase_invoice},
			"name",
		)
		frappe.db.set_value("Purchase Invoice Item", item_row, "qty", 1, update_modified=False)

		with self.assertRaisesRegex(frappe.ValidationError, "does not match Cardboard Supply"):
			supply.create_purchase_invoice()

	def test_draft_supply_cannot_create_purchase_invoice(self):
		supply = self.make_supply().insert()
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Cardboard Supply must be submitted",
		):
			supply.create_purchase_invoice()

	def test_invalid_warehouse_company_relation_is_rejected_safely(self):
		original_company = frappe.db.get_value("Warehouse", self.warehouse, "company")
		try:
			frappe.db.set_value("Warehouse", self.warehouse, "company", None, update_modified=False)
			with self.assertRaisesRegex(frappe.ValidationError, "Warehouse must belong to a valid Company"):
				self.make_supply().insert().submit()
		finally:
			frappe.db.set_value(
				"Warehouse", self.warehouse, "company", original_company, update_modified=False
			)

	def test_non_stock_item_is_rejected(self):
		item_code = "_Test Cardboard Supply Non Stock Item"
		if not frappe.db.exists("Item", item_code):
			item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": item_group,
					"stock_uom": "Kg",
					"is_stock_item": 0,
					"is_purchase_item": 1,
				}
			).insert()

		with self.assertRaisesRegex(frappe.ValidationError, "Item must maintain stock"):
			self.make_supply(item=item_code).insert().submit()

	def test_item_with_incompatible_stock_uom_is_rejected(self):
		item_code = "_Test Cardboard Supply Non Kg Item"
		if not frappe.db.exists("Item", item_code):
			item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": item_group,
					"stock_uom": "Nos",
					"is_stock_item": 1,
					"is_purchase_item": 1,
				}
			).insert()

		with self.assertRaisesRegex(frappe.ValidationError, "Item Stock UOM must be Kg"):
			self.make_supply(item=item_code).insert().submit()

	def test_disabled_supplier_is_rejected(self):
		try:
			frappe.db.set_value("Supplier", self.supplier, "disabled", 1, update_modified=False)
			with self.assertRaisesRegex(frappe.ValidationError, "Supplier must exist and be enabled"):
				self.make_supply().insert().submit()
		finally:
			frappe.db.set_value("Supplier", self.supplier, "disabled", 0, update_modified=False)

	def test_cancellation_cancels_invoice_and_reverses_stock_and_payable(self):
		bin_filters = {"item_code": self.item, "warehouse": self.warehouse}
		quantity_before = frappe.db.get_value("Bin", bin_filters, "actual_qty") or 0
		supply = self.make_supply(
			gross_weight=1150,
			tare_weight=250,
			discount_type="Percentage",
			discount_value=100 / 9,
			rate_per_kg=6.5,
		).insert()
		supply.submit()
		linked_name = supply.purchase_invoice
		self.assertEqual(
			frappe.db.get_value("Bin", bin_filters, "actual_qty") - quantity_before,
			900,
		)

		supply.cancel()

		self.assertEqual(frappe.db.get_value("Purchase Invoice", linked_name, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Bin", bin_filters, "actual_qty") or 0, quantity_before)
		self.assertEqual(
			frappe.db.count(
				"GL Entry",
				{
					"voucher_type": "Purchase Invoice",
					"voucher_no": linked_name,
					"party_type": "Supplier",
					"party": supply.supplier,
					"is_cancelled": 0,
				},
			),
			0,
		)

	def test_zero_total_supply_can_submit_with_zero_valuation(self):
		supply = self.make_supply(rate_per_kg=0).insert()
		supply.submit()

		purchase_invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
		self.assertEqual(purchase_invoice.grand_total, 0)
		self.assertEqual(purchase_invoice.items[0].qty, supply.net_weight)
		self.assertEqual(purchase_invoice.items[0].allow_zero_valuation_rate, 1)

	def test_client_exposes_record_payment_for_outstanding_submitted_supply(self):
		client_script = Path(__file__).with_name("cardboard_supply.js").read_text()

		self.assertIn('__("Record Payment")', client_script)
		self.assertIn('frm.call("make_payment_entry"', client_script)
		self.assertIn('frappe.model.sync', client_script)
		self.assertIn('frappe.set_route("Form", payment_entry.doctype, payment_entry.name)', client_script)
		self.assertIn('account_type: ["in", ["Cash", "Bank"]]', client_script)
		self.assertIn('frm.doc.purchase_invoice_outstanding > 0', client_script)

	def test_client_exposes_device_neutral_scale_capture_extension_points(self):
		client_script = Path(__file__).with_name("cardboard_supply.js").read_text()

		self.assertIn('frm.toggle_display("discount_value"', client_script)
		self.assertIn('__("Capture Gross Weight")', client_script)
		self.assertIn('__("Capture Tare Weight")', client_script)
		self.assertIn("cardboard_management.scale_reader", client_script)
		for device_specific_term in ("COM1", "/dev/tty", "baudRate", "tcp://"):
			with self.subTest(device_specific_term=device_specific_term):
				self.assertNotIn(device_specific_term, client_script)

	def test_schema_matches_the_supply_data_model(self):
		meta = frappe.get_meta("Cardboard Supply")

		self.assertTrue(meta.is_submittable)
		self.assertEqual(meta.autoname, "CS-.YYYY.-.#####")
		expected_fields = {
			"posting_date": ("Date", None, True, False),
			"supplier": ("Link", "Supplier", True, False),
			"item": ("Link", "Item", True, False),
			"warehouse": ("Link", "Warehouse", True, False),
			"gross_weight": ("Float", None, True, False),
			"tare_weight": ("Float", None, True, False),
			"net_weight": ("Float", None, False, True),
			"discount_type": ("Select", "No Discount\nKg\nPercentage", False, False),
			"discount_value": ("Float", None, False, False),
			"discount_weight": ("Float", None, False, True),
			"payable_weight": ("Float", None, False, True),
			"rate_per_kg": ("Currency", None, True, False),
			"total_amount": ("Currency", None, False, True),
			"purchase_invoice": ("Link", "Purchase Invoice", False, True),
			"purchase_invoice_outstanding": ("Currency", None, False, True),
			"payment_status": ("Data", None, False, True),
			"vehicle_no": ("Data", None, False, False),
			"driver_name": ("Data", None, False, False),
			"weight_ticket": ("Attach", None, False, False),
			"supplier_receipt": ("Attach", None, False, False),
			"notes": ("Small Text", None, False, False),
		}
		for fieldname, (fieldtype, options, required, read_only) in expected_fields.items():
			with self.subTest(fieldname=fieldname):
				field = meta.get_field(fieldname)
				self.assertEqual(field.fieldtype, fieldtype)
				self.assertEqual(field.options, options)
				self.assertEqual(bool(field.reqd), required)
				self.assertEqual(bool(field.read_only), read_only)
		self.assertTrue(meta.get_field("purchase_invoice_outstanding").is_virtual)
		self.assertTrue(meta.get_field("payment_status").is_virtual)
		self.assertEqual(meta.get_field("posting_date").default, "Today")
		self.assertEqual(meta.get_field("discount_type").default, "No Discount")
		self.assertEqual(
			meta.get_field("discount_value").depends_on,
			"eval:doc.discount_type != 'No Discount'",
		)
		self.assertFalse(any(field.fieldtype == "Table" for field in meta.fields))

		purchase_invoice_field = frappe.get_meta("Purchase Invoice").get_field(
			"custom_cardboard_supply"
		)
		self.assertEqual(purchase_invoice_field.fieldtype, "Link")
		self.assertEqual(purchase_invoice_field.options, "Cardboard Supply")
		self.assertTrue(purchase_invoice_field.read_only)
		self.assertTrue(purchase_invoice_field.unique)
		self.assertEqual(
			frappe.get_meta("Purchase Invoice Item").get_field("rate").precision,
			9,
		)

	def test_payment_summary_does_not_expose_mismatched_invoice(self):
		supply = self.make_supply().insert().submit()
		other = self.make_supply().insert().submit()
		supply.purchase_invoice = other.purchase_invoice
		supply.onload()
		self.assertIsNone(supply.payment_status)
		self.assertIsNone(supply.purchase_invoice_outstanding)

	def test_payment_summary_serializes_virtual_values_without_persistence(self):
		supply = self.make_supply().insert().submit()
		supply.onload()
		self.assertEqual(supply.as_dict().payment_status, "Unpaid")
		self.assertEqual(supply.as_dict().purchase_invoice_outstanding, supply.total_amount)
		self.assertNotIn("payment_status", supply.get_valid_dict(ignore_virtual=True))
		self.assertNotIn("purchase_invoice_outstanding", supply.get_valid_dict(ignore_virtual=True))
