"""Database-free UX contract for Quick Expense (P03-W02)."""
import json
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
DOCTYPE_DIR = APP / "cardboard_management" / "doctype" / "quick_expense"
FORM_JSON = DOCTYPE_DIR / "quick_expense.json"
FORM_JS = DOCTYPE_DIR / "quick_expense.js"


def field_by_name(doctype, fieldname):
    return next(field for field in doctype["fields"] if field["fieldname"] == fieldname)


class TestQuickExpenseOperationalUx(unittest.TestCase):
    def setUp(self):
        self.doctype = json.loads(FORM_JSON.read_text(encoding="utf-8"))
        self.js = FORM_JS.read_text(encoding="utf-8")

    def test_primary_flow_uses_real_required_fields_in_operational_order(self):
        order = self.doctype["field_order"]
        expected = ["posting_date", "company", "expense_account", "amount", "payment_account",
                    "payment_mode", "supplier_or_party", "description", "attachment"]
        self.assertEqual(sorted(expected, key=order.index), expected)
        for fieldname in ("posting_date", "company", "expense_account", "amount", "payment_account"):
            self.assertEqual(field_by_name(self.doctype, fieldname).get("reqd"), 1)

    def test_secondary_reference_and_accounting_sections_are_collapsible(self):
        self.assertEqual(field_by_name(self.doctype, "reference_section").get("collapsible"), 1)
        self.assertEqual(field_by_name(self.doctype, "integration_section").get("collapsible"), 1)
        self.assertFalse(field_by_name(self.doctype, "details_section").get("collapsible"))
        self.assertFalse(field_by_name(self.doctype, "amount_section").get("collapsible"))
        self.assertFalse(field_by_name(self.doctype, "payment_section").get("collapsible"))

    def test_standard_lifecycle_and_accounting_links_remain_visible(self):
        self.assertEqual(self.doctype["is_submittable"], 1)
        permission = self.doctype["permissions"][0]
        for action in ("create", "write", "submit", "cancel", "amend"):
            self.assertEqual(permission.get(action), 1)
        accounting_document = field_by_name(self.doctype, "accounting_document")
        self.assertEqual(accounting_document["options"], "Journal Entry")
        self.assertEqual(accounting_document["read_only"], 1)
        self.assertEqual(field_by_name(self.doctype, "accounting_status")["read_only"], 1)

    def test_client_script_contains_no_manual_ledger_or_balance_logic(self):
        for forbidden in ("GL Entry", "Payment Ledger Entry", "debit", "credit", "outstanding_amount"):
            self.assertNotIn(forbidden, self.js)
        self.assertIn('method: "make_journal_entry"', self.js)
        self.assertNotIn("frappe.db.set_value", self.js)


if __name__ == "__main__":
    unittest.main()
