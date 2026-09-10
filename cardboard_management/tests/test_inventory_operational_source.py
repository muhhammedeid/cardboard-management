"""Database-free contracts for P03-W07 operational inventory dashboard."""
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
            "selected_date",
            "activity",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("CARDBOARD-A", source)
        self.assertNotIn("CARDBOARD-B", source)
        for forbidden in ("Stock Ledger", "Sales Invoice", "GL Entry"):
            self.assertNotIn(forbidden, source)

    def test_inventory_backend_supports_historical_date_semantics(self):
        source = (APP / "inventory.py").read_text(encoding="utf-8")
        # Historical selection is an end-of-day snapshot: the Stock Balance window
        # must end on the selected date, and future dates must be rejected.
        self.assertIn("to_date", source)
        self.assertIn("getdate(selected_date)", source)
        self.assertIn("nowdate()", source)

    def test_inventory_backend_returns_daily_supply_and_sale_activity(self):
        source = (APP / "inventory.py").read_text(encoding="utf-8")
        for marker in (
            "Cardboard Supply",
            "Cardboard Sale",
            "net_weight",
            "quantity",
            "supplies",
            "sales",
            "docstatus",
        ):
            self.assertIn(marker, source)

    def test_app_owned_page_is_arabic_operational_and_all_is_default(self):
        page = json.loads((PAGE / "inventory_operational_view.json").read_text(encoding="utf-8"))
        self.assertEqual(page["doctype"], "Page")
        self.assertEqual(page["page_name"], "inventory-operational-view")
        self.assertEqual(page["roles"], [{"role": "Cardboard Operator"}])

        source = (PAGE / "inventory_operational_view.js").read_text(encoding="utf-8")
        for marker in (
            "المخزون",
            "متابعة المخزون وحركة التوريد والبيع",
            "كل الأنواع",
            "تحديث",
            "عرض التفاصيل",
            "ج.م",
            "التاريخ",
            "اليوم",
            "+ تسجيل بيع",
            "Cardboard Sale",
            "إجمالي المخزون",
            "قيمة المخزون",
            "توريدات اليوم",
            "مبيعات اليوم",
            "حركة اليوم",
            "عرض توريدات اليوم",
            "عرض مبيعات اليوم",
            "selected_date",
        ):
            self.assertIn(marker, source)
        self.assertIn("selected_item: null", source)
        self.assertIn("get_inventory_overview", source)
        self.assertNotIn("Stock Ledger", source)

    def test_inventory_page_has_compact_context_cards_and_bidi_safe_values(self):
        source = (PAGE / "inventory_operational_view.js").read_text(encoding="utf-8")
        css = (APP / "public" / "css" / "cardboard_management.css").read_text(encoding="utf-8")
        for marker in (
            "cm-inventory-context-badges",
            "cm-inventory-context-badge",
            "cm-inventory-card-header",
            "cm-inventory-uom",
            "cm-inventory-kpi-label",
            "cm-inventory-kpi-value",
            "cm-inventory-kpi",
            "bdi",
        ):
            self.assertIn(marker, source)
        for marker in (
            ".cm-inventory-context-badges",
            ".cm-inventory-context-badge",
            ".cm-inventory-card",
            ".cm-inventory-activity",
            ".cm-inventory-kpi",
            "max-width: 70rem",
            "unicode-bidi: isolate",
        ):
            self.assertIn(marker, css)

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

    def test_operator_can_record_sales_without_native_stock_access(self):
        source = (APP / "setup.py").read_text(encoding="utf-8")
        self.assertIn('"Cardboard Sale": {"read", "write", "create", "submit"}', source)
        self.assertNotIn('"Stock Entry"', source)
        self.assertNotIn('"Sales Order"', source)
        self.assertNotIn('"Sales Invoice"', source)
        self.assertNotIn('"Delivery Note"', source)


if __name__ == "__main__":
    unittest.main()
