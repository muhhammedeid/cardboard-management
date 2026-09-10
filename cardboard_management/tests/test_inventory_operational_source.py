"""Database-free contracts for P03-W06 operational inventory."""
import json
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "cardboard_management"
SETTINGS = MODULE / "doctype" / "cardboard_dashboard_settings"
WORKSPACE = MODULE / "workspace" / "cardboard_management" / "cardboard_management.json"
PAGE = MODULE / "page" / "inventory_operational_view"


class TestInventoryOperationalSource(unittest.TestCase):
    def test_dashboard_settings_owns_optional_validated_default_warehouse(self):
        doctype = json.loads((SETTINGS / "cardboard_dashboard_settings.json").read_text(encoding="utf-8"))
        field = next(item for item in doctype["fields"] if item["fieldname"] == "default_warehouse")
        self.assertEqual(field["fieldtype"], "Link")
        self.assertEqual(field["options"], "Warehouse")
        self.assertFalse(field.get("reqd"))

        source = (SETTINGS / "cardboard_dashboard_settings.py").read_text(encoding="utf-8")
        for marker in (
            "validate_default_warehouse",
            "Warehouse",
            "self.default_warehouse",
            "warehouse.disabled",
            "warehouse.is_group",
            "warehouse.company != self.company",
        ):
            self.assertIn(marker, source)

    def test_inventory_backend_uses_configured_scope_and_stock_balance_authority(self):
        source = (APP / "inventory.py").read_text(encoding="utf-8")
        for marker in (
            "get_inventory_overview",
            "get_inventory_context",
            "default_warehouse",
            "cardboard_item_group",
            "stock_balance.execute",
            "item_code",
            "stock_value",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("CARDBOARD-A", source)
        self.assertNotIn("CARDBOARD-B", source)
        self.assertNotIn("Stock Ledger", source)

    def test_app_owned_page_is_arabic_operational_and_all_is_default(self):
        page = json.loads((PAGE / "inventory_operational_view.json").read_text(encoding="utf-8"))
        self.assertEqual(page["doctype"], "Page")
        self.assertEqual(page["page_name"], "inventory-operational-view")
        self.assertEqual(page["roles"], [{"role": "Cardboard Operator"}])

        source = (PAGE / "inventory_operational_view.js").read_text(encoding="utf-8")
        for marker in ("المخزون الحالي", "كل الأنواع", "تحديث", "عرض التفاصيل", "ج.م"):
            self.assertIn(marker, source)
        self.assertIn("selected_item: null", source)
        self.assertIn("get_inventory_overview", source)
        self.assertNotIn("Stock Ledger", source)

    def test_workspace_inventory_enters_operational_page_and_keeps_stock_balance_secondary(self):
        workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        shortcuts = {item["label"]: item for item in workspace["shortcuts"]}
        self.assertEqual(shortcuts["Inventory"]["type"], "Page")
        self.assertEqual(shortcuts["Inventory"]["link_to"], "inventory-operational-view")
        report_links = [item for item in workspace["links"] if item.get("link_type") == "Report"]
        self.assertIn("Stock Balance", [item["link_to"] for item in report_links])
        self.assertNotIn("Stock Ledger", json.dumps(workspace))

    def test_operator_has_settings_read_write_only(self):
        source = (APP / "setup.py").read_text(encoding="utf-8")
        self.assertIn('"Cardboard Dashboard Settings": {"read", "write"}', source)
        self.assertNotIn('"Cardboard Dashboard Settings": {"read", "write", "delete"}', source)


if __name__ == "__main__":
    unittest.main()
