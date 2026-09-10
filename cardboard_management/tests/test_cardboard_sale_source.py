"""Database-free contracts for the P03-W07 Cardboard Sale wrapper."""
import json
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
DOCTYPE = APP / "cardboard_management" / "doctype" / "cardboard_sale"
SETUP = APP / "setup.py"


class TestCardboardSaleSource(unittest.TestCase):
    def test_doctype_is_a_minimal_submittable_operational_wrapper(self):
        doctype = json.loads((DOCTYPE / "cardboard_sale.json").read_text(encoding="utf-8"))
        self.assertEqual(doctype["doctype"], "DocType")
        self.assertEqual(doctype["module"], "Cardboard Management")
        self.assertEqual(doctype["autoname"], "SALE-.YYYY.-.#####")
        self.assertEqual(doctype["is_submittable"], 1)

        fields = {field["fieldname"]: field for field in doctype["fields"]}
        for fieldname in ("posting_date", "item", "quantity", "rate_per_kg"):
            self.assertEqual(fields[fieldname].get("reqd"), 1, fieldname)
        for fieldname in ("total_amount", "company", "stock_entry"):
            self.assertEqual(fields[fieldname].get("read_only"), 1, fieldname)
        self.assertEqual(fields["item"]["options"], "Item")
        self.assertEqual(fields["stock_entry"]["options"], "Stock Entry")
        self.assertEqual(fields["stock_entry"].get("no_copy"), 1)

        dumped = json.dumps(doctype)
        for forbidden in ("Sales Order", "Sales Invoice", "Delivery Note", "Quotation"):
            self.assertNotIn(forbidden, dumped)
        operator_roles = [row["role"] for row in doctype["permissions"]]
        self.assertNotIn("Cardboard Operator", operator_roles)
        self.assertIn("System Manager", operator_roles)

    def test_controller_resolves_settings_and_validates_operationally(self):
        source = (DOCTYPE / "cardboard_sale.py").read_text(encoding="utf-8")
        for marker in (
            "validate_item",
            "validate_quantity",
            "validate_settings",
            "cardboard_item_group",
            "default_warehouse",
            "الكمية المتاحة من هذا النوع لا تكفي لإتمام عملية البيع.",
        ):
            self.assertIn(marker, source)
        self.assertIn("flt(self.quantity) * flt(self.rate_per_kg)", source)

    def test_controller_uses_native_material_issue_stock_entry_idempotently(self):
        source = (DOCTYPE / "cardboard_sale.py").read_text(encoding="utf-8")
        for marker in (
            "make_stock_entry",
            "Material Issue",
            "_lock_for_integration",
            "_existing_stock_entry_name",
            "_validate_stock_entry_mapping",
            "cancel_stock_entry",
            "stock_entry",
        ):
            self.assertIn(marker, source)
        for forbidden in ("tabBin", "Stock Ledger Entry", "GL Entry", "Sales Invoice"):
            self.assertNotIn(forbidden, source)

    def test_sale_permissions_are_granted_through_setup_only(self):
        source = (SETUP / ".." / "setup.py").resolve().read_text(encoding="utf-8")
        self.assertIn('"Cardboard Sale": {"read", "write", "create", "submit"}', source)
        self.assertNotIn('"Cardboard Sale": {"read", "write", "create", "submit", "cancel"}', source)

    def test_arabic_catalogue_translates_operational_sale_labels(self):
        catalogue = (APP / "translations" / "ar.csv").read_text(encoding="utf-8")
        rows = {}
        for line in catalogue.splitlines():
            parts = line.split(",")
            if parts and parts[0]:
                rows[parts[0]] = parts[1] if len(parts) > 1 else ""
        for source_text in (
            "Cardboard Sale",
            "Quantity",
            "Rate per Kg",
            "Buyer Name",
            "Total Amount",
            "Stock Entry",
        ):
            self.assertIn(source_text, rows, source_text)
            self.assertTrue(rows[source_text], source_text)


if __name__ == "__main__":
    unittest.main()
