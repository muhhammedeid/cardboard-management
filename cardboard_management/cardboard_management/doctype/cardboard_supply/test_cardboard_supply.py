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
			"rate_per_kg": 2.75,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_calculates_net_weight_and_total_amount(self):
		supply = self.make_supply(net_weight=999, total_amount=999)

		supply.validate()

		self.assertEqual(supply.net_weight, 1000)
		self.assertEqual(supply.total_amount, 2750)

	def test_valid_supply_can_be_saved_and_submitted(self):
		supply = self.make_supply().insert()

		self.assertRegex(supply.name, rf"^CS-{getdate(supply.posting_date).year}-\d{{5}}$")
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

	def test_rejects_negative_rate_per_kg(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Rate per Kg cannot be negative"):
			self.make_supply(rate_per_kg=-0.01).validate()

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
		self.assertFalse(any(field.fieldtype == "Table" for field in meta.fields))
