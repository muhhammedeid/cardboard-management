import unittest
from pathlib import Path


class TestExpenseContractSource(unittest.TestCase):
	root = Path(__file__).resolve().parents[1]
	api = root / "cardboard_management" / "api" / "expenses.py"
	contract = root.parent / "docs" / "api-contracts" / "expense-contract.md"

	def test_operational_expense_api_exists_without_journal_entry_mutation(self):
		source = self.api.read_text(encoding="utf-8")
		for method in ("list_expenses", "get_expense", "lookup_expense_categories", "lookup_expense_payment_sources", "get_new_expense_schema", "create_expense", "update_expense", "submit_expense", "cancel_expense", "get_expense_capabilities"):
			self.assertIn(f"def {method}", source)
		self.assertIn("EDITABLE_FIELDS", source)
		self.assertNotIn('frappe.get_doc("Journal Entry"', source)
		self.assertIn("doc.submit()", source)
		self.assertIn("doc.cancel()", source)

	def test_documented_payment_source_and_reporting_boundary(self):
		content = self.contract.read_text(encoding="utf-8")
		self.assertIn("payment_source", content)
		self.assertIn("reporting.get_expense_summary", content)


if __name__ == "__main__":
	unittest.main()
