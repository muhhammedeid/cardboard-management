import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from cardboard_management.cardboard_management.doctype. \
	cardboard_supplier_payment.cardboard_supplier_payment import (
		CardboardSupplierPayment,
		get_mapped_payment_account,
		resolve_payment_company,
	)


class TestCardboardSupplierPayment(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_single_value("Cardboard Dashboard Settings", "company")
		assert cls.company, "Cardboard Dashboard Settings must define a company"
		cls.supplier = frappe.db.get_value(
			"Supplier", {"disabled": 0, "name": ("not like", "\\_%")}, "name"
		)
		cls.mode_of_payment = None
		for name in frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name"):
			if frappe.get_all(
				"Mode of Payment Account",
				filters={"parent": name, "company": cls.company},
				pluck="default_account",
			):
				cls.mode_of_payment = name
				break
		assert cls.supplier and cls.mode_of_payment

	def make_supplier(self):
		"""Fresh supplier per test: no pre-existing site data can interfere."""
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": f"_P03R02 {frappe.generate_hash(length=8)}",
				"supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
			}
		).insert()
		return supplier.name

	def make_payment(self, **overrides):
		values = {
			"doctype": "Cardboard Supplier Payment",
			"posting_date": nowdate(),
			"supplier": self.supplier,
			"amount": 250,
			"mode_of_payment": self.mode_of_payment,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def make_purchase_invoice(self, supplier=None, company=None, posting_date=None,
			qty=10, rate=100):
		supplier = supplier or self.supplier
		company = company or self.company
		item = frappe.db.get_value(
			"Item", {"disabled": 0, "is_stock_item": 1, "stock_uom": "Kg"}, "name"
		) or frappe.db.get_value("Item", {"disabled": 0}, "name")
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": company, "disabled": 0, "is_group": 0}, "name"
		)
		invoice = frappe.get_doc(
			dict(
				doctype="Purchase Invoice",
				supplier=supplier,
				company=company,
				posting_date=posting_date or nowdate(),
				set_posting_time=1,
				items=[dict(item_code=item, qty=qty, rate=rate, warehouse=warehouse)],
			)
		)
		invoice.insert()
		invoice.submit()
		return invoice

	def supplier_outstanding(self, supplier):
		return CardboardSupplierPayment._supplier_outstanding(supplier, self.company)

	def test_company_resolution_is_settings_driven(self):
		self.make_purchase_invoice()
		self.assertEqual(resolve_payment_company(), self.company)
		self.assertEqual(
			self.company,
			frappe.db.get_single_value("Cardboard Dashboard Settings", "company"),
		)

	def test_mapped_account_comes_from_mode_of_payment_configuration(self):
		self.make_purchase_invoice()
		account = get_mapped_payment_account(self.mode_of_payment, self.company)
		self.assertTrue(account, "Mode of Payment must map an account for the company")
		row = frappe.db.get_value(
			"Account", account,
			["company", "account_type", "is_group", "disabled", "account_currency"],
			as_dict=True,
		)
		self.assertEqual(row.company, self.company)
		self.assertIn(row.account_type, ("Cash", "Bank"))
		self.assertEqual(row.is_group, 0)
		self.assertEqual(row.disabled, 0)
		self.assertEqual(
			row.account_currency,
			frappe.get_cached_value("Company", self.company, "default_currency"),
		)
		with self.assertRaises(frappe.ValidationError):
			get_mapped_payment_account("Nonexistent Mode of Payment", self.company)

	def test_valid_payment_generates_submitted_native_entry(self):
		supplier = self.make_supplier()
		invoice = self.make_purchase_invoice(supplier=supplier, qty=10, rate=100)
		payment = self.make_payment(supplier=supplier, amount=400).insert()
		self.assertIsNone(payment.payment_entry)
		payment.submit()
		payment.reload()

		self.assertRegex(payment.name, r"^CSP-\d{4}-\d{5}$")
		self.assertTrue(payment.payment_entry)
		entry = frappe.get_doc("Payment Entry", payment.payment_entry)
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.payment_type, "Pay")
		self.assertEqual(entry.party_type, "Supplier")
		self.assertEqual(entry.party, supplier)
		self.assertEqual(entry.company, self.company)
		self.assertEqual(flt(entry.paid_amount), 400)
		self.assertEqual(flt(entry.received_amount), 400)
		self.assertEqual(entry.posting_date, payment.posting_date)
		self.assertEqual(entry.mode_of_payment, self.mode_of_payment)
		references = entry.references
		self.assertTrue(references)
		self.assertEqual({r.reference_doctype for r in references}, {"Purchase Invoice"})
		allocated = sum(flt(r.allocated_amount) for r in references)
		self.assertEqual(allocated, 400)
		self.assertEqual([r.reference_name for r in references], [invoice.name])
		self.assertTrue(
			entry.remarks.startswith(f"Cardboard Supplier Payment {payment.name}"),
			entry.remarks,
		)
		invoice.reload()
		self.assertEqual(flt(invoice.outstanding_amount), flt(invoice.grand_total) - 400)

	def test_fifo_allocation_oldest_invoice_first(self):
		supplier = self.make_supplier()
		old = self.make_purchase_invoice(supplier=supplier, posting_date="2026-01-01",
			qty=5, rate=100)
		new = self.make_purchase_invoice(supplier=supplier, posting_date=nowdate(),
			qty=7, rate=100)
		payment = self.make_payment(supplier=supplier, amount=800).insert()
		payment.submit()
		entry = frappe.get_doc("Payment Entry", payment.payment_entry)
		refs = {r.reference_name: flt(r.allocated_amount) for r in entry.references}
		self.assertEqual(refs.get(old.name), 500)
		self.assertEqual(refs.get(new.name), 300)
		old.reload()
		new.reload()
		self.assertEqual(flt(old.outstanding_amount), 0)
		self.assertEqual(flt(new.outstanding_amount), 400)

	def test_native_outstanding_effect_and_cancel_restoration(self):
		supplier = self.make_supplier()
		invoice = self.make_purchase_invoice(supplier=supplier, qty=10, rate=100)
		self.assertEqual(self.supplier_outstanding(supplier), flt(invoice.grand_total))
		payment = self.make_payment(supplier=supplier, amount=300).insert()
		payment.submit()
		invoice.reload()
		self.assertEqual(
			flt(invoice.outstanding_amount), flt(invoice.grand_total) - 300
		)
		self.assertEqual(payment.payment_status, "Submitted")
		entry = frappe.get_doc("Payment Entry", payment.payment_entry)
		payment.cancel()
		payment.reload()
		self.assertEqual(payment.payment_status, "Cancelled")
		entry.reload()
		self.assertEqual(entry.docstatus, 2)
		invoice.reload()
		self.assertEqual(flt(invoice.outstanding_amount), flt(invoice.grand_total))

	def test_cancel_validates_mapping_before_cancelling(self):
		supplier = self.make_supplier()
		self.make_purchase_invoice(supplier=supplier)
		payment = self.make_payment(supplier=supplier, amount=150).insert()
		payment.submit()
		# A wrapper must refuse to cancel a Payment Entry that no longer matches.
		frappe.db.set_value(
			"Cardboard Supplier Payment", payment.name, "payment_entry", None
		)
		with self.assertRaises(frappe.ValidationError):
			payment.cancel()

	def test_externally_cancelled_payment_entry_reports_cancelled(self):
		supplier = self.make_supplier()
		self.make_purchase_invoice(supplier=supplier)
		payment = self.make_payment(supplier=supplier, amount=120).insert()
		payment.submit()
		entry = frappe.get_doc("Payment Entry", payment.payment_entry)
		# Simulate an authorized external cancellation of the native entry: the
		# operator cancels it straight from the Payment Entry list view, where
		# no reverse link is known to the cancelling document.
		entry.flags.ignore_links = True
		entry.cancel()
		payment.reload()
		self.assertEqual(payment.payment_status, "Cancelled")

	def test_submit_is_idempotent_per_wrapper(self):
		supplier = self.make_supplier()
		self.make_purchase_invoice(supplier=supplier)
		payment = self.make_payment(supplier=supplier, amount=100).insert()
		payment.submit()
		entry_name = payment.payment_entry
		count_before = frappe.db.count("Payment Entry", {"party": supplier})
		# Simulate a concurrent submitter that loaded the wrapper before the
		# first submit committed: the row lock plus the existing link must
		# complete the existing entry instead of generating a duplicate.
		race_doc = frappe.get_doc("Cardboard Supplier Payment", payment.name)
		race_doc.docstatus = 0
		race_doc.on_submit()
		count_after = frappe.db.count("Payment Entry", {"party": supplier})
		self.assertEqual(count_before, count_after)
		payment.reload()
		self.assertEqual(payment.payment_entry, entry_name)

	def test_invalid_amounts_rejected_before_generation(self):
		supplier = self.make_supplier()
		self.make_purchase_invoice(supplier=supplier)
		for amount in (0, -10):
			with self.assertRaises(frappe.ValidationError):
				self.make_payment(supplier=supplier, amount=amount).validate()
		with self.assertRaises(frappe.ValidationError):
			payment = self.make_payment(supplier=supplier, amount=10 ** 9).insert()
			payment.submit()

	def test_no_outstanding_rejected(self):
		supplier = self.make_supplier()
		invoice = self.make_purchase_invoice(supplier=supplier, qty=1, rate=10)
		paid = self.make_payment(supplier=supplier, amount=10).insert()
		paid.submit()
		with self.assertRaises(frappe.ValidationError):
			self.make_payment(supplier=supplier, amount=10).insert()

	def test_disabled_supplier_rejected(self):
		supplier = self.make_supplier()
		self.make_purchase_invoice(supplier=supplier)
		frappe.db.set_value("Supplier", supplier, "disabled", 1)
		try:
			with self.assertRaises(frappe.ValidationError):
				self.make_payment(supplier=supplier, amount=100).validate()
		finally:
			frappe.db.set_value("Supplier", supplier, "disabled", 0)

	def test_unmapped_mode_of_payment_rejected(self):
		supplier = self.make_supplier()
		self.make_purchase_invoice(supplier=supplier)
		unmapped = None
		for name in frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name"):
			if not frappe.get_all(
				"Mode of Payment Account",
				filters={"parent": name, "company": self.company},
				pluck="default_account",
			):
				unmapped = name
				break
		if not unmapped:
			self.skipTest("No unmapped enabled Mode of Payment available on this site")
		# The account mapping is validated when the Payment Entry is generated,
		# so the wrapper is accepted as a draft but rejected on submit.
		payment = self.make_payment(supplier=supplier, mode_of_payment=unmapped,
			amount=100).insert()
		with self.assertRaises(frappe.ValidationError):
			payment.submit()

	def test_second_payment_against_remaining_outstanding(self):
		supplier = self.make_supplier()
		invoice = self.make_purchase_invoice(supplier=supplier, qty=10, rate=100)
		first = self.make_payment(supplier=supplier, amount=100).insert()
		first.submit()
		second = self.make_payment(supplier=supplier, amount=100).insert()
		second.submit()
		invoice.reload()
		self.assertEqual(flt(invoice.outstanding_amount), flt(invoice.grand_total) - 200)

	def test_permissions_surface_matches_accounts_roles(self):
		roles = {p.role for p in frappe.get_meta("Cardboard Supplier Payment").permissions}
		self.assertEqual(roles, {"Accounts User", "Accounts Manager", "Cardboard Operator"})
		pe_roles = {p.role for p in frappe.get_meta("Payment Entry").permissions}
		self.assertEqual(pe_roles, {"Accounts User", "Accounts Manager"})
