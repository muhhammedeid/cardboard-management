import json
import unittest
from pathlib import Path


class TestSupplyContractSource(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]
    api = root / "cardboard_management" / "api" / "supply.py"
    contract = root.parent / "docs" / "api-contracts" / "supply-contract.md"

    def test_contract_exposes_all_operations_and_security_boundaries(self):
        source = self.api.read_text()
        for method in (
            "list_supplies", "get_supply", "lookup_suppliers", "lookup_items",
            "create_supply", "update_supply", "submit_supply", "cancel_supply",
            "capture_gross_weight", "capture_tare_weight", "get_capabilities",
            "get_print_action",
        ):
            self.assertIn(f"def {method}", source)
        for marker in (
            "@frappe.whitelist()", "doc.check_permission(\"read\")",
            "doc.check_permission(\"write\")", "doc.check_permission(\"submit\")",
            "doc.check_permission(\"cancel\")", "EDITABLE_FIELDS",
            "MAX_PAGE_SIZE", "Cardboard Supply Ticket", "get_descendants_of",
            'settings.default_warehouse',
        ):
            self.assertIn(marker, source)
        self.assertNotIn("frappe.db.sql(", source)

    def test_contract_document_is_present_and_forbids_frontend_calculations(self):
        text = self.contract.read_text()
        for marker in (
            "list_supplies", "get_supply", "lookup_suppliers", "lookup_items",
            "create_supply", "update_supply", "submit_supply", "cancel_supply",
            "capture_gross_weight", "capture_tare_weight", "get_capabilities",
            "get_print_action", "validation_error", "permission_denied",
            "Cardboard Supply Ticket", "must not calculate",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
