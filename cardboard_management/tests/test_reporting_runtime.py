"""Runtime behavior contracts for P03-C04 reporting services."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate
from frappe.utils.nestedset import get_descendants_of

from cardboard_management import reporting


class TestReportingReadModels(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.context = reporting.get_inventory_context()
        cls.items = cls.context["items"]
        cls.item = cls.items[0].name if cls.items else None
        cls.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
        cls.alternate_warehouse = frappe.db.get_value(
            "Warehouse",
            {
                "company": cls.context.company,
                "name": ["!=", cls.context.warehouse],
                "disabled": 0,
                "is_group": 0,
            },
            "name",
        )
        if not cls.item or not cls.supplier or not cls.alternate_warehouse:
            raise unittest.SkipTest("reporting fixtures require item, supplier, and alternate warehouse")

    @staticmethod
    def _raw_doc(doctype, name, values, docstatus=1):
        document = frappe.get_doc({"doctype": doctype, "name": name, **values})
        document.flags.ignore_validate = True
        document.flags.ignore_permissions = True
        document.db_insert()
        frappe.db.set_value(doctype, name, "docstatus", docstatus, update_modified=False)
        return name

    def _insert_supply(self, suffix, warehouse=None, item=None, quantity=1, docstatus=1):
        name = f"_P03C04 Supply {suffix} {frappe.generate_hash(length=8)}"
        return self._raw_doc(
            "Cardboard Supply",
            name,
            {
                "posting_date": nowdate(),
                "supplier": self.supplier,
                "item": item or self.item,
                "warehouse": warehouse or self.context.warehouse,
                "gross_weight": quantity,
                "tare_weight": 0,
                "net_weight": quantity,
                "discount_type": "No Discount",
                "discount_value": 0,
                "discount_weight": 0,
                "payable_weight": quantity,
                "rate_per_kg": 2,
                "total_amount": quantity * 2,
            },
            docstatus,
        )

    def _insert_sale(self, suffix, warehouse=None, item=None, quantity=1, docstatus=1, buyer_name=None):
        name = f"_P03C04 Sale {suffix} {frappe.generate_hash(length=8)}"
        return self._raw_doc(
            "Cardboard Sale",
            name,
            {
                "posting_date": nowdate(),
                "item": item or self.item,
                "quantity": quantity,
                "rate_per_kg": 3,
                "total_amount": quantity * 3,
                "buyer_name": buyer_name or "P03-C04 Buyer",
                "company": self.context.company,
                "warehouse": warehouse or self.context.warehouse,
            },
            docstatus,
        )

    def _make_non_cardboard_item(self):
        scoped_groups = [
            self.context.cardboard_item_group,
            *get_descendants_of("Item Group", self.context.cardboard_item_group),
        ]
        item_group = frappe.db.get_value(
            "Item Group", {"name": ["not in", scoped_groups], "is_group": 0}, "name"
        )
        if not item_group:
            self.skipTest("site has no non-cardboard leaf Item Group")
        item_code = f"_P03C04 Non Cardboard {frappe.generate_hash(length=8)}"
        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_code,
                "item_group": item_group,
                "stock_uom": "Kg",
                "is_stock_item": 1,
                "is_purchase_item": 1,
            }
        ).insert(ignore_permissions=True)
        return item.name

    def test_operations_summary_aggregates_range_and_scope(self):
        before = reporting.get_operations_summary(from_date=nowdate(), to_date=nowdate())
        non_cardboard_item = self._make_non_cardboard_item()
        self._insert_supply("scoped", quantity=7)
        self._insert_supply("warehouse", warehouse=self.alternate_warehouse, quantity=11)
        self._insert_supply("item-group", item=non_cardboard_item, quantity=13)
        self._insert_sale("scoped", quantity=3)
        self._insert_sale("warehouse", warehouse=self.alternate_warehouse, quantity=17)
        self._insert_sale("item-group", item=non_cardboard_item, quantity=19)
        after = reporting.get_operations_summary(from_date=nowdate(), to_date=nowdate())

        self.assertEqual(flt(after["supplies"]["quantity"]) - flt(before["supplies"]["quantity"]), 7)
        self.assertEqual(flt(after["supplies"]["value"]) - flt(before["supplies"]["value"]), 14)
        self.assertEqual(flt(after["sales"]["quantity"]) - flt(before["sales"]["quantity"]), 3)
        self.assertEqual(flt(after["sales"]["value"]) - flt(before["sales"]["value"]), 9)
        self.assertEqual(flt(after["inventory_movement"]["inbound_quantity"]) - flt(before["inventory_movement"]["inbound_quantity"]), 7)
        self.assertEqual(flt(after["inventory_movement"]["outbound_quantity"]) - flt(before["inventory_movement"]["outbound_quantity"]), 3)
        self.assertEqual(after["scope"]["warehouse"], self.context.warehouse)
        self.assertEqual(after["scope"]["company"], self.context.company)

    def test_sales_summary_supports_item_buyer_and_status_filters(self):
        before_draft = reporting.get_sales_summary(from_date=nowdate(), to_date=nowdate(), status="draft")
        before_cancelled = reporting.get_sales_summary(from_date=nowdate(), to_date=nowdate(), status="cancelled")
        self._insert_sale("submitted", quantity=5, buyer_name="P03-C04 Alpha Buyer")
        self._insert_sale("draft", quantity=7, docstatus=0, buyer_name="P03-C04 Draft Buyer")
        self._insert_sale("cancelled", quantity=9, docstatus=2, buyer_name="P03-C04 Cancelled Buyer")

        submitted = reporting.get_sales_summary(
            from_date=nowdate(), to_date=nowdate(), cardboard_item=self.item,
            buyer_text="Alpha Buyer", status="submitted"
        )
        draft = reporting.get_sales_summary(from_date=nowdate(), to_date=nowdate(), status="draft")
        cancelled = reporting.get_sales_summary(from_date=nowdate(), to_date=nowdate(), status="cancelled")
        self.assertEqual(submitted["sale_count"], 1)
        self.assertEqual(flt(submitted["total_quantity"]), 5)
        self.assertEqual(flt(submitted["total_informational_value"]), 15)
        self.assertEqual(draft["sale_count"] - before_draft["sale_count"], 1)
        self.assertEqual(cancelled["sale_count"] - before_cancelled["sale_count"], 1)
        self.assertEqual(submitted["status"], "submitted")

    def test_supplier_summary_uses_current_erpnext_outstanding_semantics(self):
        result = reporting.get_supplier_summary(
            self.supplier, from_date="2020-01-01", to_date=nowdate()
        )
        self.assertEqual(result["supplier"]["name"], self.supplier)
        self.assertIsInstance(result["supply_history"], list)
        self.assertIsInstance(result["payment_history"], list)
        self.assertGreaterEqual(flt(result["supplier_payments"]), 0)
        self.assertGreaterEqual(flt(result["outstanding"]), 0)
        self.assertEqual(result["outstanding_semantics"], "current_erpnext_purchase_invoice_outstanding")
        for row in result["supply_history"]:
            self.assertEqual(row["item"], self.item)

    def test_supplier_summary_isolated_by_supplier(self):
        other = frappe.db.get_value(
            "Supplier", {"disabled": 0, "name": ["!=", self.supplier]}, "name"
        )
        if not other:
            self.skipTest("site has only one enabled supplier")
        first = reporting.get_supplier_summary(self.supplier, from_date="2020-01-01", to_date=nowdate())
        second = reporting.get_supplier_summary(other, from_date="2020-01-01", to_date=nowdate())
        self.assertNotEqual(first["supplier"]["name"], second["supplier"]["name"])
        self.assertTrue(all(row["supply"] not in {x["supply"] for x in second["supply_history"]} for row in first["supply_history"]))

    def test_expense_summary_uses_submitted_native_journal_entries(self):
        expense_account = frappe.db.get_value(
            "Account", {"company": self.context.company, "root_type": "Expense", "is_group": 0, "disabled": 0}, "name"
        )
        payment_account = frappe.db.get_value(
            "Account", {"company": self.context.company, "account_type": ["in", ["Cash", "Bank"]], "is_group": 0, "disabled": 0}, "name"
        )
        if not expense_account or not payment_account:
            self.skipTest("site lacks expense and cash/bank accounts")
        before = reporting.get_expense_summary(from_date=nowdate(), to_date=nowdate())
        original_user = frappe.session.user
        frappe.set_user("Administrator")
        try:
            expense = frappe.get_doc(
                {
                    "doctype": "Quick Expense",
                    "posting_date": nowdate(),
                    "company": self.context.company,
                    "expense_account": expense_account,
                    "payment_account": payment_account,
                    "amount": 23,
                    "description": "P03-C04 reporting fixture",
                }
            ).insert(ignore_permissions=True)
            expense.submit()
        finally:
            frappe.set_user(original_user)
        after = reporting.get_expense_summary(from_date=nowdate(), to_date=nowdate())
        self.assertEqual(after["expense_count"] - before["expense_count"], 1)
        self.assertEqual(flt(after["total_expense_amount"]) - flt(before["total_expense_amount"]), 23)
        self.assertTrue(any(row["account"] == expense_account and flt(row["amount"]) >= 23 for row in after["by_account"]))

    def test_inventory_movement_is_separate_and_item_filterable(self):
        self._insert_supply("movement", quantity=8)
        self._insert_sale("movement", quantity=2)
        result = reporting.get_inventory_movement(
            from_date=nowdate(), to_date=nowdate(), cardboard_item=self.item
        )
        self.assertEqual(flt(result["inbound_quantity"]), 8)
        self.assertEqual(flt(result["outbound_quantity"]), 2)
        self.assertEqual(flt(result["net_quantity"]), 6)
        self.assertTrue(result["by_date"])
        self.assertTrue(result["by_item"])
        self.assertEqual(result["by_item"][0]["item"], self.item)

    def test_invalid_ranges_items_and_scope_overrides_are_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            reporting.get_inventory_movement(from_date=nowdate(), to_date="2026-01-01")
        with self.assertRaises(frappe.ValidationError):
            reporting.get_sales_summary(cardboard_item="_outside_reporting_scope_")
        with self.assertRaises(TypeError):
            reporting.get_operations_summary(company=self.context.company)
        with self.assertRaises(TypeError):
            reporting.get_inventory_movement(warehouse=self.context.warehouse)
