import unittest
from pathlib import Path


class TestOperationalSettingsContractSource(unittest.TestCase):
	root = Path(__file__).resolve().parents[1]
	api = root / "cardboard_management" / "api" / "operational_settings.py"
	contract = root.parent / "docs" / "api-contracts" / "operational-settings-contract.md"

	def test_settings_api_has_allowlisted_read_update_and_lookups(self):
		source = self.api.read_text(encoding="utf-8")
		for method in ("get_operational_settings", "update_operational_settings", "get_operational_settings_capabilities", "lookup_companies", "lookup_warehouses", "lookup_cardboard_item_groups", "lookup_supplier_groups", "lookup_modes_of_payment"):
			self.assertIn(f"def {method}", source)
		self.assertIn("EDITABLE_FIELDS", source)
		self.assertIn("settings.save()", source)

	def test_contract_documents_controller_validation_reuse(self):
		content = self.contract.read_text(encoding="utf-8")
		self.assertIn("Cardboard Dashboard Settings", content)
		self.assertIn("validation", content)


if __name__ == "__main__":
	unittest.main()
