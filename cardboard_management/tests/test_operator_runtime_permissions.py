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

    def test_operator_can_resolve_supplier_payable_account(self):
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

    def test_operator_cannot_modify_account_or_direct_erp_documents(self):
        for doctype in ("Account", "Payment Entry", "Purchase Invoice"):
            self.assertFalse(frappe.has_permission(doctype, "create"), doctype)
            self.assertFalse(frappe.has_permission(doctype, "write"), doctype)
        self.assertFalse(frappe.has_permission("Journal Entry", "create"))
        self.assertFalse(frappe.has_permission("Stock Entry", "create"))

    def test_administrator_default_workspace_remains_unset(self):
        self.assertFalse(frappe.db.get_value("User", "Administrator", "default_workspace"))
