"""Source contracts for the P03-C04 reporting read services."""

import ast
import unittest
from pathlib import Path


REPORTING = Path(__file__).resolve().parents[1] / "reporting.py"


class TestReportingSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = REPORTING.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_public_services_exist(self):
        names = {
            node.name
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(
            {
                "get_operations_summary",
                "get_sales_summary",
                "get_supplier_summary",
                "get_supplier_statement",
                "get_expense_summary",
                "get_inventory_movement",
            } <= names
        )

    def test_public_services_do_not_accept_scope_overrides(self):
        public = {
            "get_operations_summary",
            "get_sales_summary",
            "get_supplier_summary",
            "get_supplier_statement",
            "get_expense_summary",
            "get_inventory_movement",
        }
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in public:
                arguments = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
                self.assertNotIn("company", arguments, node.name)
                self.assertNotIn("warehouse", arguments, node.name)
                self.assertNotIn("item_group", arguments, node.name)

    def test_contract_uses_settings_context_and_submitted_scope(self):
        self.assertIn("get_inventory_context", self.source)
        self.assertIn("STATUS_VALUES", self.source)
        self.assertIn('"submitted": 1', self.source)
        self.assertIn("_date_range", self.source)
        self.assertIn("item.item_group in", self.source)
        self.assertIn("supply.warehouse = %s", self.source)
        self.assertIn("sale.warehouse = %s", self.source)

    def test_financial_semantics_are_explicit(self):
        self.assertIn("total_informational_value", self.source)
        self.assertIn("current_erpnext_purchase_invoice_outstanding", self.source)
        self.assertIn("native_journal.docstatus = 1", self.source)
        self.assertNotIn("gross_margin", self.source.lower())
        self.assertNotIn("profitability", self.source.lower())

    def test_native_documents_are_not_returned_as_report_records(self):
        self.assertIn('"payment_history"', self.source)
        self.assertIn('"supply_history"', self.source)
        self.assertNotIn('"payment_entry": row.', self.source)
        self.assertNotIn('"journal_entry": row.', self.source)
        self.assertNotIn('"stock_entry": row.', self.source)


if __name__ == "__main__":
    unittest.main()
