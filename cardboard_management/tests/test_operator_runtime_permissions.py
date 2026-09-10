"""Runtime permission contracts for the Cardboard Operator role."""

import frappe
from frappe.desk.query_report import generate_report_result, get_report_doc
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.accounts.party import get_party_account


OPERATOR_ROLE = "Cardboard Operator"
COMPANY = "El Nos"
WAREHOUSE = "Main Warehouse - RN"
ITEM = "CARDBOARD-A"


class TestOperatorRuntimePermissions(FrappeTestCase):
    def setUp(self):
        self.original_user = frappe.session.user
        self.operator = frappe.get_all(
            "Has Role",
            filters={"parenttype": "User", "role": OPERATOR_ROLE, "parent": ["!=", "Administrator"]},
            pluck="parent",
            limit_page_length=1,
        )[0]
        self.supplier = frappe.get_all("Supplier", pluck="name", limit_page_length=1)[0]
        frappe.set_user(self.operator)

    def tearDown(self):
        frappe.set_user(self.original_user)

    def run_report(self, report_name, filters):
        return generate_report_result(get_report_doc(report_name), filters)["result"]

    def test_operator_can_read_supplier_list_and_resolve_payable_account(self):
        suppliers = frappe.get_list("Supplier", fields=["name", "supplier_name"], limit_page_length=20)
        self.assertTrue(suppliers)
        self.assertTrue(get_party_account("Supplier", self.supplier, COMPANY))

    def test_operator_can_run_accounts_payable(self):
        self.assertIsInstance(
            self.run_report(
                "Accounts Payable",
                {"company": COMPANY, "party_type": "Supplier", "report_date": nowdate(), "range": "30, 60, 90, 120"},
            ),
            list,
        )

    def test_operator_can_run_purchase_register(self):
        self.assertIsInstance(
            self.run_report(
                "Purchase Register",
                {"company": COMPANY, "from_date": "2026-01-01", "to_date": nowdate()},
            ),
            list,
        )

    def test_operator_can_run_stock_balance_for_existing_ledger_entry(self):
        rows = self.run_report(
            "Stock Balance",
            {
                "company": COMPANY,
                "warehouse": WAREHOUSE,
                "item_code": [ITEM],
                "from_date": "2026-01-01",
                "to_date": nowdate(),
            },
        )
        self.assertTrue(any(row.get("item_code") == ITEM and row.get("warehouse") == WAREHOUSE for row in rows))

    def test_operator_can_read_accounts_payable_party_type_filter(self):
        self.assertIsInstance(frappe.get_list("Party Type", fields=["name"], limit_page_length=20), list)

    def test_operator_can_read_stock_balance_warehouse_type_filter(self):
        self.assertIsInstance(frappe.get_list("Warehouse Type", fields=["name"], limit_page_length=20), list)

    def test_operator_cannot_run_stock_ledger(self):
        with self.assertRaises(frappe.PermissionError):
            self.run_report(
                "Stock Ledger",
                {"company": COMPANY, "warehouse": WAREHOUSE, "from_date": "2026-01-01", "to_date": nowdate()},
            )

    def test_operator_cannot_access_forbidden_erp_documents(self):
        for doctype in (
            "Stock Entry",
            "Payment Entry",
            "Sales Invoice",
            "Delivery Note",
            "Sales Order",
        ):
            self.assertFalse(frappe.has_permission(doctype, "read"), doctype)
            self.assertFalse(frappe.has_permission(doctype, "create"), doctype)
            self.assertFalse(frappe.has_permission(doctype, "write"), doctype)
        for ptype in ("create", "write"):
            self.assertFalse(frappe.has_permission("Journal Entry", ptype), f"Journal Entry:{ptype}")

    def test_operator_has_intended_custom_doctype_actions(self):
        for doctype in (
            "Cardboard Supply",
            "Cardboard Sale",
            "Cardboard Supplier Payment",
            "Quick Expense",
        ):
            for ptype in ("read", "create", "write", "submit"):
                self.assertTrue(frappe.has_permission(doctype, ptype), f"{doctype}:{ptype}")
        for ptype in ("read", "write"):
            self.assertTrue(frappe.has_permission("Supplier", ptype), f"Supplier:{ptype}")
        self.assertTrue(frappe.has_permission("Cardboard Dashboard Settings", "read"))
        self.assertTrue(frappe.has_permission("Cardboard Dashboard Settings", "write"))

    def test_setup_permission_convergence_is_repeatable(self):
        from cardboard_management.setup import _ensure_cardboard_operator_permissions

        _ensure_cardboard_operator_permissions()
        first = frappe.get_all(
            "Custom DocPerm",
            filters={"role": OPERATOR_ROLE},
            fields=["parent", "read", "write", "create", "submit", "cancel", "report"],
            order_by="parent asc",
        )
        _ensure_cardboard_operator_permissions()
        second = frappe.get_all(
            "Custom DocPerm",
            filters={"role": OPERATOR_ROLE},
            fields=["parent", "read", "write", "create", "submit", "cancel", "report"],
            order_by="parent asc",
        )
        self.assertEqual(first, second)
        for row in second:
            self.assertEqual(
                frappe.db.count("Custom DocPerm", {"parent": row.parent, "role": OPERATOR_ROLE, "permlevel": 0}),
                1,
            )
        self.assertEqual(frappe.db.count("Custom Role", {"report": "Stock Ledger"}), 0)

    def test_administrator_remains_unrestricted(self):
        frappe.set_user("Administrator")
        for doctype in ("Stock Entry", "Payment Entry", "Journal Entry", "Sales Invoice"):
            self.assertTrue(frappe.has_permission(doctype, "read"), doctype)
            self.assertTrue(frappe.has_permission(doctype, "create"), doctype)
            self.assertTrue(frappe.has_permission(doctype, "write"), doctype)
        frappe.set_user(self.operator)

    def test_administrator_default_workspace_remains_unset(self):
        self.assertFalse(frappe.db.get_value("User", "Administrator", "default_workspace"))
