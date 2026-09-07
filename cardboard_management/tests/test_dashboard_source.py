"""Database-free contracts for standard dashboard widget source files."""
import json
import unittest
from pathlib import Path

APP_MODULE = Path(__file__).resolve().parents[1] / "cardboard_management"

NUMBER_CARDS = {
    "today's_supplies_weight": "cardboard_management.dashboard.today_supplies_weight",
    "today's_purchase_amount": "cardboard_management.dashboard.today_purchase_amount",
    "today's_supplier_payments": "cardboard_management.dashboard.today_supplier_payments",
    "today's_expenses": "cardboard_management.dashboard.today_expenses",
    "current_stock_weight": "cardboard_management.dashboard.current_stock_weight",
    "supplier_outstanding": "cardboard_management.dashboard.supplier_outstanding",
    "this_month_purchased_weight": "cardboard_management.dashboard.this_month_purchased_weight",
    "this_month_purchase_cost": "cardboard_management.dashboard.this_month_purchase_cost",
    "this_month_expenses": "cardboard_management.dashboard.this_month_expenses",
    "this_month_paid_to_suppliers": "cardboard_management.dashboard.this_month_paid_to_suppliers",
}
CHARTS = {
    "daily_supplied_weight": "Cardboard Daily Supplied Weight",
    "purchases_by_cardboard_type": "Cardboard Purchases by Type",
    "top_suppliers": "Cardboard Top Suppliers",
    "supplier_outstanding": "Cardboard Supplier Outstanding",
}


class TestDashboardWidgetSources(unittest.TestCase):
    def test_number_cards_are_standard_app_owned_custom_cards(self):
        root = APP_MODULE / "number_card"
        for slug, method in NUMBER_CARDS.items():
            path = root / slug / f"{slug}.json"
            self.assertTrue(path.is_file(), path)
            card = json.loads(path.read_text())
            self.assertEqual(card["doctype"], "Number Card")
            self.assertEqual(card["type"], "Custom")
            self.assertEqual(card["method"], method)
            self.assertEqual(card["module"], "Cardboard Management")
            self.assertEqual(card["is_standard"], 1)
            self.assertEqual(card["is_public"], 1)

    def test_dashboard_charts_use_app_owned_custom_sources(self):
        chart_root = APP_MODULE / "dashboard_chart"
        source_root = APP_MODULE / "dashboard_chart_source"
        for slug, source_name in CHARTS.items():
            chart_path = chart_root / slug / f"{slug}.json"
            self.assertTrue(chart_path.is_file(), chart_path)
            chart = json.loads(chart_path.read_text())
            self.assertEqual(chart["doctype"], "Dashboard Chart")
            self.assertEqual(chart["chart_type"], "Custom")
            self.assertEqual(chart["source"], source_name)
            self.assertEqual(chart["module"], "Cardboard Management")
            self.assertEqual(chart["is_standard"], 1)
            self.assertEqual(chart["is_public"], 1)

            source_slug = source_name.lower().replace(" ", "_")
            source_dir = source_root / source_slug
            source_path = source_dir / f"{source_slug}.json"
            self.assertTrue(source_path.is_file(), source_path)
            source = json.loads(source_path.read_text())
            self.assertEqual(source["doctype"], "Dashboard Chart Source")
            self.assertEqual(source["name"], source_name)
            self.assertEqual(source["module"], "Cardboard Management")
            self.assertTrue((source_dir / f"{source_slug}.py").is_file())
            self.assertTrue((source_dir / f"{source_slug}.js").is_file())

    def test_app_owned_dashboard_query_fields_are_indexed(self):
        expectations = {
            "cardboard_supply/cardboard_supply.json": {"posting_date", "supplier", "item", "warehouse"},
            "quick_expense/quick_expense.json": {"posting_date", "company"},
        }
        doctype_root = APP_MODULE / "doctype"
        for relative_path, expected_fields in expectations.items():
            data = json.loads((doctype_root / relative_path).read_text(encoding="utf-8"))
            indexed = {
                field["fieldname"]
                for field in data["fields"]
                if field.get("search_index")
            }
            self.assertTrue(expected_fields <= indexed)


if __name__ == "__main__":
    unittest.main()
