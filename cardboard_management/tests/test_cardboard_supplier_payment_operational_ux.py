"""Database-free operational-UX contract for Cardboard Supplier Payment (P03-R02).

The wrapper stays a thin submittable shell: business fields only on the surface,
integration fields hidden/read-only, permissions limited to the standard Accounts
roles, and every generated-Payment-Entry rule owned by the server controller.
"""
import csv
import json
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]  # module root: .../cardboard_management/cardboard_management
DOCTYPE_DIR = APP / "cardboard_management" / "doctype" / "cardboard_supplier_payment"
FORM_JSON = DOCTYPE_DIR / "cardboard_supplier_payment.json"
FORM_JS = DOCTYPE_DIR / "cardboard_supplier_payment.js"
CONTROLLER = DOCTYPE_DIR / "cardboard_supplier_payment.py"
JS_ASSET = APP / "public" / "js" / "cardboard_management.js"
WORKSPACE = (APP / "cardboard_management" / "workspace" / "cardboard_management" /
             "cardboard_management.json")


def field_by_name(doctype, fieldname):
    return next((f for f in doctype["fields"] if f["fieldname"] == fieldname), None)


class TestCardboardSupplierPaymentOperationalUx(unittest.TestCase):
    def setUp(self):
        self.assertTrue(FORM_JSON.is_file(), "Ship the wrapper doctype JSON")
        self.doctype = json.loads(FORM_JSON.read_text(encoding="utf-8"))
        self.js = FORM_JS.read_text(encoding="utf-8")
        self.controller = CONTROLLER.read_text(encoding="utf-8")

    def test_autoname_and_submittable_shell(self):
        self.assertEqual(self.doctype["autoname"], "CSP-.YYYY.-.#####")
        self.assertEqual(self.doctype["is_submittable"], 1)
        self.assertEqual(self.doctype["module"], "Cardboard Management")
        # setup.py must stay at its P03-R01 baseline: the wrapper is a
        # first-class app DocType, never a Custom Field on Payment Entry, and
        # JE_ACCOUNT_REFERENCE_TYPES is untouched.
        setup_text = (APP / "setup.py").read_text(encoding="utf-8")
        self.assertNotIn("Cardboard Supplier Payment", setup_text)
        self.assertNotIn("custom_cardboard_supplier_payment", setup_text)
        self.assertIn("REQUIRED_JE_ACCOUNT_REFERENCE_TYPE", setup_text)
        self.assertNotIn("Cardboard Supplier Payment", setup_text)

    def test_permissions_use_only_standard_accounts_roles(self):
        roles = [p["role"] for p in self.doctype["permissions"]]
        self.assertEqual(sorted(roles), ["Accounts Manager", "Accounts User"])
        for permission in self.doctype["permissions"]:
            self.assertEqual(permission["create"], 1)
            self.assertEqual(permission["submit"], 1)
            self.assertEqual(permission["cancel"], 1)
            self.assertEqual(permission["write"], 1)
            self.assertEqual(permission["amend"], 1)

    def test_operational_fields_are_business_only(self):
        order = self.doctype["field_order"]
        expected = ["supplier", "amount", "mode_of_payment", "posting_date",
                    "reference_no", "reference_date", "notes"]
        self.assertEqual(sorted(expected, key=order.index), expected)
        for fieldname in ("supplier", "amount", "mode_of_payment", "posting_date"):
            self.assertEqual(field_by_name(self.doctype, fieldname).get("reqd"), 1)
        supplier = field_by_name(self.doctype, "supplier")
        self.assertEqual(supplier["options"], "Supplier")
        self.assertEqual(field_by_name(self.doctype, "mode_of_payment")["options"],
                         "Mode of Payment")
        self.assertEqual(field_by_name(self.doctype, "posting_date").get("default"), "Today")
        self.assertEqual(field_by_name(self.doctype, "amount")["fieldtype"], "Currency")

    def test_generic_payment_entry_fields_never_surface(self):
        forbidden_generic = {"paid_from", "paid_to", "paid_amount", "received_amount",
                             "party_type", "party", "party_name", "party_account",
                             "references", "total_allocated_amount", "unallocated_amount",
                             "base_paid_amount", "base_received_amount", "source_exchange_rate",
                             "target_exchange_rate", "difference_amount"}
        present = {f["fieldname"] for f in self.doctype["fields"]}
        self.assertEqual(forbidden_generic & present, set())
        # company is an allowed server-resolved integration field (hidden) - never
        # an editable operational field.
        self.assertEqual(field_by_name(self.doctype, "company").get("hidden"), 1)

    def test_integration_fields_are_read_only_and_hidden_by_default(self):
        integration = {"company", "payment_entry", "payment_status",
                       "current_supplier_outstanding", "expected_remaining_outstanding"}
        present = {f["fieldname"] for f in self.doctype["fields"]}
        self.assertTrue(integration <= present)
        for fieldname in ("payment_entry", "payment_status", "current_supplier_outstanding",
                          "expected_remaining_outstanding"):
            field = field_by_name(self.doctype, fieldname)
            self.assertEqual(field["read_only"], 1, fieldname)
        self.assertEqual(field_by_name(self.doctype, "payment_entry")["options"],
                         "Payment Entry")
        for fieldname in ("company", "payment_status", "current_supplier_outstanding",
                          "expected_remaining_outstanding"):
            self.assertEqual(field_by_name(self.doctype, fieldname)["hidden"], 1, fieldname)
        # Display state is computed, never stored: the three summary fields are
        # virtual (no DB column), so ERPNext remains the only balance authority.
        for fieldname in ("payment_status", "current_supplier_outstanding",
                          "expected_remaining_outstanding"):
            self.assertEqual(field_by_name(self.doctype, fieldname)["is_virtual"], 1, fieldname)

    def test_secondary_reference_fields_optional_and_collapsible(self):
        for fieldname in ("reference_no", "reference_date", "notes"):
            self.assertIsNone(field_by_name(self.doctype, fieldname).get("reqd"))
        self.assertEqual(field_by_name(self.doctype, "integration_section").get("collapsible"), 1)

    def test_doctype_js_stays_thin_native_lifecycle(self):
        for forbidden in ("frappe.call", "make_payment_entry", "outstanding_amount",
                          "GL Entry", "Payment Ledger Entry", "frappe.db.set_value",
                          "insert()"):
            self.assertNotIn(forbidden, self.js)
        # The supported primary-action label must appear translated-ready and the
        # click must ride the native save+submit lifecycle (never manual calls).
        self.assertIn("Save and Submit Payment", self.js)
        self.assertIn("frm.savesubmit", self.js)
        self.assertNotIn("frappe.xcall", self.js)

    def test_public_asset_relabels_only_this_doctype(self):
        source = JS_ASSET.read_text(encoding="utf-8")
        self.assertIn('"Cardboard Supplier Payment"', source)
        self.assertIn('set_primary_action(PAYMENT_SUBMIT_LABEL', source)
        self.assertIn('const PAYMENT_SUBMIT_LABEL = __("Save and Submit Payment")', source)
        self.assertIn('frm.savesubmit', source)

    def test_workspace_quick_action_targets_wrapper_and_list_stays_native(self):
        workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        quick = next(s for s in workspace["shortcuts"] if s["label"] == "New Supplier Payment")
        listing = next(s for s in workspace["shortcuts"] if s["label"] == "Payments")
        self.assertEqual(quick["link_to"], "Cardboard Supplier Payment")
        self.assertEqual(quick["doc_view"], "New")
        self.assertEqual(listing["link_to"], "Payment Entry")

    def test_controller_uses_native_generation_and_never_writes_ledger(self):
        self.assertIn("get_payment_entry(", self.controller)
        self.assertIn("get_bank_cash_account(", self.controller)
        # FIFO query over submitted open Purchase Invoices.
        self.assertIn("Purchase Invoice", self.controller)
        self.assertRegex(self.controller, r"order_by\s*=?\s*.*posting_date")
        for forbidden in (
            "frappe.db.set_value(\"Purchase Invoice\"",
            "frappe.db.set_value('Purchase Invoice'",
            "db_set(\"outstanding_amount\"",
            "make_gl_entries",
            "update_outstanding",
        ):
            self.assertNotIn(forbidden, self.controller)
        self.assertIn("frappe.db.sql(", self.controller)
        self.assertIn("for update", self.controller)
        # The only ledger-adjacent list is the native ignore_linked_doctypes
        # cancellation pattern - verified as the ERPNext controller precedent.
        self.assertIn("ignore_linked_doctypes", self.controller)

    def test_controller_resolves_company_from_settings_config(self):
        # Company is configuration-driven from Cardboard Dashboard Settings,
        # never guessed from the supplier or company defaults.
        self.assertIn("Cardboard Dashboard Settings", self.controller)
        self.assertIn("get_single_value", self.controller)
        self.assertIn(
            "Configure Company in Cardboard Dashboard Settings before recording supplier payments",
            self.controller,
        )
        self.assertNotIn("Cannot resolve a single company", self.controller)

    def test_controller_rejects_and_maps_correctly(self):
        for marker in (
            "No outstanding invoices exist for this supplier",
            "Amount must be greater than zero",
            "Amount exceeds the total outstanding",
            "This supplier is disabled",
            "No enabled Mode of Payment Account is mapped",
            "does not match the payment request",
            "has no linked Payment Entry",
        ):
            self.assertIn(marker, self.controller)
        # Native PE must be the only writer; no client mapping of accounts.
        self.assertNotIn("credit_to", self.controller)
        self.assertNotIn("Creditors", self.controller)

    def test_controller_cancels_linked_entry_safely(self):
        # The wrapper cancel path must exist, validate the mapping first, tolerate
        # an externally cancelled entry, and only then cancel natively.
        self.assertIn("def cancel_payment_entry", self.controller)
        cancel_body = self.controller.split("def cancel_payment_entry", 1)[1].split(
            "\n\tdef ", 1)[0]
        self.assertIn("_validate_payment_entry_mapping(payment_entry)", cancel_body)
        self.assertLess(
            cancel_body.index("_validate_payment_entry_mapping"),
            cancel_body.index("payment_entry.cancel()"),
        )
        self.assertIn('ignore_linked_doctypes = ("Cardboard Supplier Payment",)', cancel_body)
        self.assertIn("if payment_entry.docstatus == 2:\n\t\t\treturn", cancel_body)


if __name__ == "__main__":
    unittest.main()
