"""Database-free contract for Cardboard-scoped Egyptian Pound presentation."""
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
JS = APP / "public" / "js" / "cardboard_management.js"


class TestCurrencyPresentation(unittest.TestCase):
    def test_workspace_normalization_remains_limited_to_the_cardboard_workspace(self):
        source = JS.read_text(encoding="utf-8")
        self.assertIn('const MALFORMED_EGP_SYMBOL = "£ or ج.م"', source)
        self.assertIn('const OPERATIONAL_EGP_SYMBOL = "ج.م"', source)
        self.assertIn("normalize_workspace_currency_text", source)
        self.assertIn('route[0] === "Workspaces"', source)
        self.assertNotIn("window.format_currency =", source)
        self.assertNotIn("window.get_currency_symbol =", source)
        self.assertNotIn("frappe.currency_symbols", source)

    def test_form_currency_uses_a_cardboard_docfield_formatter_not_dom_rewrites(self):
        source = JS.read_text(encoding="utf-8")
        self.assertIn("install_operational_currency_formatter", source)
        self.assertIn("frappe.form.formatters.Currency", source)
        self.assertIn("df.formatter = operational_currency_formatter", source)
        self.assertIn("frappe.meta.get_field_currency", source)
        self.assertIn('currency !== "EGP"', source)
        self.assertIn("frm.refresh_field(fieldname)", source)
        self.assertNotIn("[data-fieldtype=\"Currency\"]", source)

    def test_report_currency_composes_query_report_formatters_only_for_approved_reports(self):
        source = JS.read_text(encoding="utf-8")
        scope = source.split("OPERATIONAL_CURRENCY_REPORTS", 1)[1].split("]);", 1)[0]
        self.assertIn('"Stock Balance"', scope)
        self.assertIn('"Accounts Payable"', scope)
        self.assertIn('"Purchase Register"', scope)
        self.assertNotIn('"General Ledger"', scope)
        self.assertIn("install_operational_report_currency_formatter_hook", source)
        self.assertIn("QueryReport?.prototype", source)
        self.assertIn("get_report_settings.apply(this, args)", source)
        self.assertIn('column?.fieldtype === "Currency"', source)
        self.assertIn("native_formatter", source)
        self.assertNotIn("window.format_currency =", source)
        self.assertNotIn("window.get_currency_symbol =", source)

    def test_only_cardboard_form_doctypes_receive_the_formatter(self):
        source = JS.read_text(encoding="utf-8")
        scope = source.split("CURRENCY_NORMALIZED_DOCTYPES", 1)[1].split("]);", 1)[0]
        self.assertIn('"Cardboard Supply"', scope)
        self.assertIn('"Quick Expense"', scope)
        self.assertIn('"Cardboard Supplier Payment"', scope)
        self.assertNotIn('"Payment Entry"', scope)


if __name__ == "__main__":
    unittest.main()
