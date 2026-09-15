import unittest
from pathlib import Path


class TestSupplierPaymentContractSource(unittest.TestCase):
	root = Path(__file__).resolve().parents[1]
	api = root / "cardboard_management" / "api" / "supplier_payments.py"
	contract = root.parent / "docs" / "api-contracts" / "supplier-payment-contract.md"

	def test_api_exports_safe_payment_boundary(self):
		source = self.api.read_text(encoding="utf-8")
		for method in (
			"list_supplier_payments", "get_supplier_payment", "lookup_suppliers",
			"lookup_modes_of_payment", "get_new_supplier_payment_schema",
			"get_supplier_payment_context", "create_supplier_payment",
			"update_supplier_payment", "submit_supplier_payment",
			"cancel_supplier_payment", "get_supplier_payment_capabilities",
		):
			self.assertIn(f"def {method}", source)
		self.assertIn("EDITABLE_FIELDS", source)
		self.assertNotIn("frappe.get_doc(\"Payment Entry\"", source)
		self.assertIn("doc.submit()", source)
		self.assertIn("doc.cancel()", source)

	def test_contract_covers_required_frontend_semantics(self):
		content = self.contract.read_text(encoding="utf-8")
		for marker in ("Payment Entry", "default_mode_of_payment", "expected_remaining_outstanding", "invalid_mode_of_payment"):
			self.assertIn(marker, content)


if __name__ == "__main__":
	unittest.main()
