import unittest
from pathlib import Path


class TestSupplierContractSource(unittest.TestCase):
	root = Path(__file__).resolve().parents[1]
	api = root / "cardboard_management" / "api" / "suppliers.py"
	contract = root.parent / "docs" / "api-contracts" / "supplier-contract.md"
	settings_json = root / "cardboard_management" / "doctype" / "cardboard_dashboard_settings" / "cardboard_dashboard_settings.json"
	settings_controller = root / "cardboard_management" / "doctype" / "cardboard_dashboard_settings" / "cardboard_dashboard_settings.py"

	def test_api_has_master_operations_and_does_not_duplicate_reporting(self):
		source = self.api.read_text(encoding="utf-8")
		for method in ("list_suppliers", "get_supplier", "get_new_supplier_schema", "create_supplier", "get_capabilities"):
			self.assertIn(f"def {method}", source)
		for marker in (
			"CREATE_FIELDS", "MAX_PAGE_SIZE", "default_supplier_group", "frappe.get_list",
			"doc.check_permission(\"read\")", '"duplicate_supplier"', '"supplier_error"',
			"frappe.log_error", "_clear_error()",
		):
			self.assertIn(marker, source)
		for forbidden in (
			"get_supplier_summary", "get_supplier_statement", "Payment Ledger Entry",
			"Purchase Invoice", "frappe.db.sql(",
		):
			self.assertNotIn(forbidden, source)

	def test_settings_define_and_validate_canonical_default_supplier_group(self):
		self.assertIn('"fieldname": "default_supplier_group"', self.settings_json.read_text(encoding="utf-8"))
		controller = self.settings_controller.read_text(encoding="utf-8")
		self.assertIn("validate_default_supplier_group", controller)
		self.assertIn("Supplier Group", controller)
		self.assertIn("is_group", controller)

	def test_contract_documents_schema_and_reporting_separation(self):
		text = self.contract.read_text(encoding="utf-8")
		for marker in (
			"list_suppliers", "get_supplier", "get_new_supplier_schema", "create_supplier",
			"default_supplier_group", "duplicate_supplier", "update is **deferred**",
			"get_supplier_summary", "get_supplier_statement", "NOT RESUMED",
		):
			self.assertIn(marker, text)


if __name__ == "__main__":
	unittest.main()
