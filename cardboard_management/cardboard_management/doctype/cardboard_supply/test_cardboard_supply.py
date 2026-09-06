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

		cls.item = frappe.db.get_value("Item", {"disabled": 0}, "name")
		cls.warehouse = frappe.db.get_value("Warehouse", {"disabled": 0, "is_group": 0}, "name")
		if not cls.item or not cls.warehouse:
			raise AssertionError("Cardboard Supply tests require one enabled Item and non-group Warehouse")

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

	def test_zero_tare_and_zero_rate_are_valid(self):
		supply = self.make_supply(gross_weight=100, tare_weight=0, rate_per_kg=0).insert()

		self.assertEqual(supply.net_weight, 100)
		self.assertEqual(supply.total_amount, 0)

	def test_submit_creates_no_erp_transactions(self):
		doctypes = ("Purchase Invoice", "Purchase Receipt", "Stock Ledger Entry", "GL Entry")
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
		self.assertEqual(meta.get_field("posting_date").default, "Today")
		self.assertEqual(meta.get_field("discount_type").default, "No Discount")
		self.assertEqual(
			meta.get_field("discount_value").depends_on,
			"eval:doc.discount_type != 'No Discount'",
		)
		self.assertFalse(any(field.fieldtype == "Table" for field in meta.fields))
