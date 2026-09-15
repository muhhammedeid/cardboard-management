import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate
from frappe.utils.nestedset import get_descendants_of

from cardboard_management.cardboard_management.api import sales as api


class TestSalesContract(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		settings = frappe.get_cached_doc("Cardboard Dashboard Settings")
		groups = [settings.cardboard_item_group]
		groups.extend(get_descendants_of("Item Group", settings.cardboard_item_group))
		cls.item = frappe.db.get_value(
			"Item",
			{"item_group": ["in", groups], "disabled": 0, "is_stock_item": 1, "stock_uom": "Kg"},
			"name",
		)
		cls.warehouse = settings.default_warehouse
		if not cls.item or not cls.warehouse:
			raise AssertionError("Sales contract tests require configured cardboard item and warehouse")

	def setUp(self):
		frappe.local.response.pop("sale_error", None)

	def make_values(self, **overrides):
		values = {
			"posting_date": nowdate(),
			"item": self.item,
			"quantity": 1,
			"rate_per_kg": 3,
			"buyer_name": f"P04-BCR02 Buyer {frappe.generate_hash(length=6)}",
			"notes": "contract test",
		}
		values.update(overrides)
		return values

	def available_stock(self):
		from erpnext.stock.utils import get_stock_balance

		return flt(get_stock_balance(self.item, self.warehouse, nowdate()))

	def test_create_update_detail_list_filters_search_order_and_capabilities(self):
		buyer = f"P04-BCR02 Alpha {frappe.generate_hash(length=6)}"
		created = api.create_sale(**self.make_values(buyer_name=buyer, quantity=2, rate_per_kg=4))
		self.assertEqual(created["company"], frappe.get_cached_doc("Cardboard Dashboard Settings").company)
		self.assertEqual(created["warehouse"], self.warehouse)
		self.assertEqual(created["total_amount"], 8)
		self.assertEqual(created["informational_value"], 8)
		self.assertTrue(created["capabilities"]["can_edit"])
		self.assertTrue(created["capabilities"]["can_submit"])

		updated = api.update_sale(created["name"], quantity=3, rate_per_kg=5, notes="updated")
		self.assertEqual(updated["quantity"], 3)
		self.assertEqual(updated["total_amount"], 15)
		detail = api.get_sale(created["name"])
		self.assertEqual(detail["name"], created["name"])
		self.assertEqual(api.get_capabilities(created["name"])["capabilities"], detail["capabilities"])

		for kwargs in (
			{"buyer": "Alpha"},
			{"item": self.item},
			{"status": "Draft"},
			{"search": created["name"]},
			{"from_date": nowdate(), "to_date": nowdate()},
		):
			with self.subTest(kwargs=kwargs):
				listed = api.list_sales(page=1, page_size=10, **kwargs)
				self.assertTrue(any(row["name"] == created["name"] for row in listed["data"]))
				self.assertLessEqual(len(listed["data"]), 10)
		paged = api.list_sales(page=1, page_size=1)
		self.assertEqual(len(paged["data"]), 1)
		self.assertIn("has_more", paged)

	def test_buyer_lookup_uses_existing_text_values_and_is_bounded(self):
		buyer = f"P04-BCR02 Lookup {frappe.generate_hash(length=6)}"
		api.create_sale(**self.make_values(buyer_name=buyer))
		lookup = api.lookup_buyers(search="Lookup", page_size=1000)
		self.assertLessEqual(len(lookup["data"]), api.MAX_PAGE_SIZE)
		self.assertTrue(any(row["buyer_name"] == buyer for row in lookup["data"]))

	def test_item_lookup_reuses_cardboard_scope(self):
		items = api.lookup_items(page_size=1000)
		self.assertLessEqual(len(items["data"]), api.MAX_PAGE_SIZE)
		self.assertTrue(any(row["name"] == self.item for row in items["data"]))
		self.assertTrue(all(row["stock_uom"] == "Kg" for row in items["data"]))

	def test_submit_cancel_and_invalid_lifecycle(self):
		if self.available_stock() < 1:
			self.skipTest("Sales submit contract requires at least 1 Kg available stock")
		created = api.create_sale(**self.make_values(quantity=1, rate_per_kg=2))
		submitted = api.submit_sale(created["name"])
		self.assertEqual(submitted["docstatus"], 1)
		self.assertTrue(submitted["stock_entry"])
		self.assertFalse(submitted["capabilities"]["can_edit"])
		with self.assertRaises(frappe.ValidationError):
			api.update_sale(created["name"], notes="no")
		cancelled = api.cancel_sale(created["name"])
		self.assertEqual(cancelled["docstatus"], 2)
		with self.assertRaises(frappe.ValidationError):
			api.cancel_sale(created["name"])
		self.assertEqual(frappe.local.response["sale_error"]["code"], "invalid_state")

	def test_insufficient_stock_is_normalized(self):
		created = api.create_sale(**self.make_values(quantity=self.available_stock() + 1000000))
		with self.assertRaises(frappe.ValidationError):
			api.submit_sale(created["name"])
		self.assertEqual(frappe.local.response["sale_error"]["code"], "insufficient_stock")
		self.assertEqual(frappe.local.response["sale_error"]["field"], "quantity")

	def test_permission_denial_is_normalized(self):
		created = api.create_sale(**self.make_values())
		original_user = frappe.session.user
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				api.get_sale(created["name"])
			self.assertEqual(frappe.local.response["sale_error"]["code"], "permission_denied")
		finally:
			frappe.set_user(original_user)

	def test_validation_and_field_allowlist_errors_are_normalized(self):
		with self.assertRaises(frappe.ValidationError):
			api.create_sale(**self.make_values(quantity=0))
		self.assertEqual(frappe.local.response["sale_error"]["code"], "validation")
		with self.assertRaises(frappe.ValidationError):
			api.create_sale(**self.make_values(company="ATTACK"))
		self.assertEqual(frappe.local.response["sale_error"]["code"], "validation")

	def test_form_action_points_to_existing_desk_form(self):
		created = api.create_sale(**self.make_values())
		action = api.get_form_action(created["name"])
		self.assertIn("/app/cardboard-sale/", action["url"])
