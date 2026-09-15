import unittest
from pathlib import Path


class TestSalesContractSource(unittest.TestCase):
	root = Path(__file__).resolve().parents[1]
	api = root / "cardboard_management" / "api" / "sales.py"
	contract = root.parent / "docs" / "api-contracts" / "sales-contract.md"

	def test_api_exports_required_operations_and_security_markers(self):
		source = self.api.read_text(encoding="utf-8")
		for method in (
			"list_sales",
			"get_sale",
			"lookup_buyers",
			"lookup_items",
			"create_sale",
			"update_sale",
			"submit_sale",
			"cancel_sale",
			"get_capabilities",
		):
			with self.subTest(method=method):
				self.assertIn(f"def {method}", source)
		for marker in (
			"@frappe.whitelist()",
			"EDITABLE_FIELDS",
			"MAX_PAGE_SIZE",
			"SORT_FIELDS",
			"doc.check_permission(\"read\")",
			"doc.check_permission(\"write\")",
			"doc.check_permission(\"submit\")",
			"doc.check_permission(\"cancel\")",
			"CardboardSale.INSUFFICIENT_STOCK_MESSAGE",
			'"insufficient_stock"',
			'"sale_error"',
			"lookup_cardboard_items",
			"frappe.get_list",
		):
			with self.subTest(marker=marker):
				self.assertIn(marker, source)
		self.assertNotIn("frappe.db.sql(", source)
		self.assertNotIn("make_stock_entry", source)
		self.assertNotIn("Stock Ledger Entry", source)
		self.assertNotIn("Sales Invoice", source)
		self.assertNotIn("Payment Entry", source)

	def test_contract_document_describes_frontend_contract_and_boundaries(self):
		text = self.contract.read_text(encoding="utf-8")
		for marker in (
			"list_sales",
			"get_sale",
			"lookup_buyers",
			"lookup_items",
			"create_sale",
			"update_sale",
			"submit_sale",
			"cancel_sale",
			"get_capabilities",
			"buyer_name",
			"insufficient_stock",
			"must not calculate stock",
			"NOT RESUMED",
		):
			with self.subTest(marker=marker):
				self.assertIn(marker, text)


if __name__ == "__main__":
	unittest.main()
