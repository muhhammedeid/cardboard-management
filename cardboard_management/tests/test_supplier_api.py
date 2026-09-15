import frappe
from frappe.tests.utils import FrappeTestCase

from cardboard_management.cardboard_management.api import suppliers as api


class TestSupplierContract(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.default_group = frappe.get_cached_doc("Cardboard Dashboard Settings").default_supplier_group
		if not cls.default_group:
			raise AssertionError("Supplier contract tests require Default Supplier Group")

	def setUp(self):
		frappe.local.response.pop("supplier_error", None)

	def make_values(self, **overrides):
		values = {
			"supplier_name": f"P04-BCR03 Supplier {frappe.generate_hash(length=8)}",
			"supplier_type": "Company",
			"tax_id": "TAX-TEST",
			"supplier_details": "Supplier contract test",
		}
		values.update(overrides)
		return values

	def test_schema_resolves_configured_default_supplier_group(self):
		schema = api.get_new_supplier_schema()
		self.assertEqual(schema["default_supplier_group"], self.default_group)
		self.assertEqual(schema["required_fields"], ["supplier_name"])
		self.assertIn("supplier_details", schema["optional_fields"])
		self.assertIn("accounts", schema["system_managed_fields"])

	def test_create_detail_and_capabilities(self):
		created = api.create_supplier(**self.make_values())
		self.assertEqual(created["supplier_group"], self.default_group)
		self.assertFalse(created["disabled"])
		self.assertEqual(created["supplier_details"], "Supplier contract test")
		self.assertTrue(created["capabilities"]["can_read"])
		self.assertTrue(created["capabilities"]["can_create"])
		# Editing a supplier is an offered capability now: it mirrors the write right.
		self.assertTrue(created["capabilities"]["can_edit"])
		detail = api.get_supplier(created["name"])
		self.assertEqual(detail["name"], created["name"])
		self.assertEqual(api.get_capabilities(created["name"])["capabilities"], detail["capabilities"])

	def test_update_edits_only_the_creation_fields(self):
		created = api.create_supplier(**self.make_values())
		name = created["name"]

		updated = api.update_supplier(
			name,
			supplier_name="Supplier Contract Test (edited)",
			supplier_type="Partnership",
			tax_id="123-456-789",
			supplier_details="Edited through update_supplier",
		)

		self.assertEqual(updated["name"], name)
		self.assertEqual(updated["supplier_name"], "Supplier Contract Test (edited)")
		self.assertEqual(updated["supplier_type"], "Partnership")
		self.assertEqual(updated["tax_id"], "123-456-789")
		stored = frappe.get_doc("Supplier", name)
		self.assertEqual(stored.supplier_details, "Edited through update_supplier")
		self.assertEqual(stored.supplier_type, "Partnership")

		with self.assertRaises(frappe.ValidationError):
			api.update_supplier(name, supplier_group="Administrative")
		self.assertEqual(frappe.local.response["supplier_error"]["code"], "validation")

		duplicate = api.create_supplier(**self.make_values(supplier_name="Supplier Contract Duplicate"))
		with self.assertRaises(frappe.ValidationError):
			api.update_supplier(name, supplier_name="Supplier Contract Duplicate")
		self.assertEqual(frappe.local.response["supplier_error"]["code"], "duplicate_supplier")
		self.assertEqual(
			frappe.db.get_value("Supplier", name, "supplier_name"), "Supplier Contract Test (edited)"
		)
		self.assertIsNotNone(duplicate["name"])

	def test_transport_cmd_is_not_treated_as_a_supplier_field(self):
		created = api.create_supplier(cmd="cardboard_management.cardboard_management.api.suppliers.create_supplier", **self.make_values())
		self.assertEqual(created["supplier_group"], self.default_group)
		with self.assertRaises(frappe.ValidationError):
			api.create_supplier(cmd="cardboard_management.cardboard_management.api.suppliers.create_supplier", **self.make_values(accounts=[]))
		self.assertEqual(frappe.local.response["supplier_error"]["code"], "validation")

	def test_list_search_status_and_pagination(self):
		created = api.create_supplier(**self.make_values())
		frappe.db.set_value("Supplier", created["name"], "disabled", 1, update_modified=False)
		listed = api.list_suppliers(search=created["name"], page=1, page_size=1)
		self.assertEqual(listed["total"], 1)
		self.assertEqual(listed["data"][0]["name"], created["name"])
		self.assertTrue(listed["data"][0]["disabled"])
		inactive = api.list_suppliers(status="inactive", page=1, page_size=100)
		self.assertTrue(any(row["name"] == created["name"] for row in inactive["data"]))
		active = api.list_suppliers(status="active", page=1, page_size=100)
		self.assertFalse(any(row["name"] == created["name"] for row in active["data"]))

	def test_duplicate_validation_and_field_allowlist(self):
		values = self.make_values()
		api.create_supplier(**values)
		with self.assertRaises(frappe.ValidationError):
			api.create_supplier(**values)
		self.assertEqual(frappe.local.response["supplier_error"]["code"], "duplicate_supplier")
		with self.assertRaises(frappe.ValidationError):
			api.create_supplier(**self.make_values(accounts=[]))
		self.assertEqual(frappe.local.response["supplier_error"]["code"], "validation")

	def test_not_found_and_permission_denial_are_normalized(self):
		with self.assertRaises(frappe.DoesNotExistError):
			api.get_supplier("MISSING-SUPPLIER")
		self.assertEqual(frappe.local.response["supplier_error"]["code"], "not_found")
		created = api.create_supplier(**self.make_values())
		original_user = frappe.session.user
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				api.get_supplier(created["name"])
			self.assertEqual(frappe.local.response["supplier_error"]["code"], "permission_denied")
		finally:
			frappe.set_user(original_user)
