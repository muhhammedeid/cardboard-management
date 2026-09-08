"""Database-free UX contract for the Cardboard Supply operational form (P03-W01)."""
import json
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
DOCTYPE_DIR = APP / "cardboard_management" / "doctype" / "cardboard_supply"
FORM_JSON = DOCTYPE_DIR / "cardboard_supply.json"
FORM_JS = DOCTYPE_DIR / "cardboard_supply.js"


def field_by_fieldname(doctype, fieldname):
    return next(field for field in doctype["fields"] if field["fieldname"] == fieldname)


class TestCardboardSupplyOperationalUx(unittest.TestCase):
    def setUp(self):
        self.doctype = json.loads(FORM_JSON.read_text(encoding="utf-8"))
        self.js = FORM_JS.read_text(encoding="utf-8")

    def test_client_side_does_not_duplicate_server_calculations(self):
        self.assertNotIn("calculate_totals", self.js)
        self.assertNotIn("flt(frm.doc.gross_weight) - flt(frm.doc.tare_weight)", self.js)
        self.assertNotIn("net_weight * flt(frm.doc.discount_value)", self.js)
        self.assertNotIn("payable_weight * flt(frm.doc.rate_per_kg)", self.js)

    def test_server_authoritative_lifecycle_affordances_are_preserved(self):
        for marker in (
            "add_scale_capture_actions",
            "add_record_payment_action",
            "add_integration_indicators",
            "toggle_discount_value",
        ):
            self.assertIn(marker, self.js)

    def test_layout_labels_operational_flow_and_collapses_secondary_sections(self):
        self.assertEqual(field_by_fieldname(self.doctype, "pricing_section")["label"], "Price and Total")
        self.assertEqual(
            field_by_fieldname(self.doctype, "integration_section")["label"], "Linked Purchase Invoice"
        )
        notes_section = field_by_fieldname(self.doctype, "notes_section")
        self.assertEqual(notes_section["label"], "Notes")
        self.assertEqual(notes_section["collapsible"], 1)
        self.assertEqual(field_by_fieldname(self.doctype, "display_payable_weight")["hidden"], 1)

    def test_no_real_field_is_removed_from_the_doctype(self):
        expected = {
            "posting_date", "supplier", "item", "warehouse",
            "gross_weight", "tare_weight", "net_weight",
            "discount_type", "discount_value", "discount_weight", "payable_weight",
            "display_payable_weight", "rate_per_kg", "total_amount",
            "purchase_invoice", "integration_status", "invoice_total",
            "invoice_paid_amount", "purchase_invoice_outstanding", "payment_status",
            "vehicle_no", "driver_name", "weight_ticket", "supplier_receipt", "notes",
        }
        fieldnames = {field["fieldname"] for field in self.doctype["fields"]}
        self.assertEqual(expected - fieldnames, set())


if __name__ == "__main__":
    unittest.main()
