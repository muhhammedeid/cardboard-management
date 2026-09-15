import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from cardboard_management.cardboard_management.api import supplier_payments as api


class TestSupplierPaymentApi(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_single_value("Cardboard Dashboard Settings", "company")
		cls.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		cls.mode = frappe.db.get_single_value("Cardboard Dashboard Settings", "default_mode_of_payment")
		if not all((cls.company, cls.supplier, cls.mode)):
			raise unittest.SkipTest("Supplier payment API configuration is unavailable")

	def test_schema_and_lookups_are_bounded_and_safe(self):
		schema = api.get_new_supplier_payment_schema()
		self.assertEqual(schema["default_mode_of_payment"], self.mode)
		self.assertEqual(schema["required_fields"], ["supplier", "amount", "mode_of_payment", "posting_date"])
		self.assertNotIn("company", schema["editable_fields"])
		self.assertNotIn("paid_from", schema["server_owned_fields"])
		suppliers = api.lookup_suppliers(page_size=1)
		modes = api.lookup_modes_of_payment(page_size=1)
		self.assertLessEqual(len(suppliers["data"]), 1)
		self.assertLessEqual(len(modes["data"]), 1)
		self.assertEqual(set(modes["data"][0]), {"name"})

	def test_list_filters_and_detail_have_operational_fields_only(self):
		result = api.list_supplier_payments(page=1, page_size=1, status="Draft")
		self.assertLessEqual(len(result["data"]), 1)
		self.assertEqual(result["page_size"], 1)
		if result["data"]:
			self.assertNotIn("payment_entry", result["data"][0])
			detail = api.get_supplier_payment(result["data"][0]["name"])
			self.assertIn("payment_status", detail)
			self.assertIn("current_supplier_outstanding", detail)
			self.assertNotIn("payment_entry", detail)

	def test_draft_create_update_allowlist_and_lifecycle_guard(self):
		with self.assertRaises(frappe.ValidationError):
			api.create_supplier_payment(company=self.company)
		self.assertEqual(frappe.local.response.supplier_payment_error["code"], "validation")

	def test_context_and_capabilities_delegate_to_wrapper_authority(self):
		context = api.get_supplier_payment_context(self.supplier)
		self.assertEqual(context["company"], self.company)
		self.assertIn("current_supplier_outstanding", context)
		caps = api.get_supplier_payment_capabilities()
		self.assertIn("can_create", caps["capabilities"])

	def _make_purchase_invoice(self):
		item = frappe.db.get_value("Item", {"disabled": 0, "is_stock_item": 1}, "name")
		warehouse = frappe.db.get_value(
			"Warehouse", {"company": self.company, "disabled": 0, "is_group": 0}, "name"
		)
		if not item or not warehouse:
			self.skipTest("Purchase Invoice fixture is unavailable")
		invoice = frappe.get_doc({
			"doctype": "Purchase Invoice", "supplier": self.supplier, "company": self.company,
			"posting_date": nowdate(), "set_posting_time": 1,
			"items": [{"item_code": item, "qty": 2, "rate": 50, "warehouse": warehouse}],
		})
		invoice.insert()
		invoice.submit()
		return invoice

	def test_draft_lifecycle_delegates_native_payment_entry_submit_and_cancel(self):
		invoice = self._make_purchase_invoice()
		payment = api.create_supplier_payment(
			supplier=self.supplier, amount=25, mode_of_payment=self.mode,
			posting_date=nowdate(), reference_no="BCR04", notes="API lifecycle test",
		)
		self.assertEqual(payment["status"], "Draft")
		updated = api.update_supplier_payment(payment["name"], notes="updated")
		self.assertEqual(updated["notes"], "updated")
		submitted = api.submit_supplier_payment(payment["name"])
		self.assertEqual(submitted["status"], "Submitted")
		wrapper = frappe.get_doc("Cardboard Supplier Payment", payment["name"])
		self.assertTrue(wrapper.payment_entry)
		self.assertEqual(frappe.get_doc("Payment Entry", wrapper.payment_entry).docstatus, 1)
		with self.assertRaises(frappe.ValidationError):
			api.update_supplier_payment(payment["name"], notes="not allowed")
		self.assertEqual(frappe.local.response.supplier_payment_error["code"], "invalid_lifecycle")
		cancelled = api.cancel_supplier_payment(payment["name"])
		self.assertEqual(cancelled["status"], "Cancelled")
		self.assertEqual(frappe.get_doc("Payment Entry", wrapper.payment_entry).docstatus, 2)
		invoice.reload()
		self.assertGreater(invoice.outstanding_amount, 0)


if __name__ == "__main__":
	unittest.main()
