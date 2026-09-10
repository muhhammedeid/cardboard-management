"""Runtime contracts for P03-C01 transaction scope and date invariants."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate
from frappe.utils.nestedset import get_descendants_of


class TestTransactionScope(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = frappe.get_cached_doc("Cardboard Dashboard Settings")
        cls.company = cls.settings.company
        cls.warehouse = cls.settings.default_warehouse
        cls.item_groups = [
            cls.settings.cardboard_item_group,
            *get_descendants_of("Item Group", cls.settings.cardboard_item_group),
        ]
        cls.item = frappe.db.get_value(
            "Item",
            {
                "item_group": ["in", cls.item_groups],
                "is_stock_item": 1,
                "disabled": 0,
                "stock_uom": "Kg",
            },
            "name",
        )
        cls.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
        cls.mode_of_payment = frappe.db.get_value("Mode of Payment", {"enabled": 1}, "name")
        cls.expense_account = frappe.db.get_value(
            "Account",
            {"company": cls.company, "root_type": "Expense", "is_group": 0, "disabled": 0},
            "name",
        )
        cls.cash_account = frappe.db.get_value(
            "Account",
            {
                "company": cls.company,
                "account_type": ["in", ["Cash", "Bank"]],
                "is_group": 0,
                "disabled": 0,
            },
            "name",
        )
        if not all(
            (
                cls.company,
                cls.warehouse,
                cls.settings.cardboard_item_group,
                cls.item,
                cls.supplier,
                cls.mode_of_payment,
                cls.expense_account,
                cls.cash_account,
            )
        ):
            raise AssertionError("P03-C01 runtime fixtures are incomplete")

    def make_supply(self, **overrides):
        values = {
            "doctype": "Cardboard Supply",
            "posting_date": nowdate(),
            "supplier": self.supplier,
            "item": self.item,
            "warehouse": self.warehouse,
            "gross_weight": 100,
            "tare_weight": 10,
            "discount_type": "No Discount",
            "discount_value": 0,
            "rate_per_kg": 1,
        }
        values.update(overrides)
        return frappe.get_doc(values)

    def make_sale(self, **overrides):
        values = {
            "doctype": "Cardboard Sale",
            "posting_date": nowdate(),
            "item": self.item,
            "quantity": 1,
            "rate_per_kg": 1,
            "company": self.company,
            "warehouse": self.warehouse,
        }
        values.update(overrides)
        return frappe.get_doc(values)

    def make_payment(self, **overrides):
        values = {
            "doctype": "Cardboard Supplier Payment",
            "posting_date": nowdate(),
            "supplier": self.supplier,
            "amount": 1,
            "mode_of_payment": self.mode_of_payment,
        }
        values.update(overrides)
        return frappe.get_doc(values)

    def make_expense(self, **overrides):
        values = {
            "doctype": "Quick Expense",
            "posting_date": nowdate(),
            "company": self.company,
            "expense_account": self.expense_account,
            "amount": 1,
            "payment_account": self.cash_account,
        }
        values.update(overrides)
        return frappe.get_doc(values)

    def test_all_operational_transactions_reject_future_posting_dates(self):
        future = add_days(nowdate(), 1)
        documents = (
            self.make_supply(posting_date=future),
            self.make_sale(posting_date=future),
            self.make_payment(posting_date=future),
            self.make_expense(posting_date=future),
        )
        for document in documents:
            with self.subTest(doctype=document.doctype):
                with self.assertRaisesRegex(frappe.ValidationError, "future|المستقبل"):
                    document.validate()

    def test_supply_and_sale_reject_unconfigured_warehouse(self):
        for document in (
            self.make_supply(warehouse="P03-C01 Unconfigured Warehouse"),
            self.make_sale(warehouse="P03-C01 Unconfigured Warehouse"),
        ):
            with self.subTest(doctype=document.doctype):
                with self.assertRaisesRegex(frappe.ValidationError, "default warehouse|المخزن الافتراضي"):
                    document.validate()

    def test_sale_and_other_transactions_reject_company_outside_settings(self):
        sale = self.make_sale(company="P03-C01 Unconfigured Company")
        payment = self.make_payment(company="P03-C01 Unconfigured Company")
        expense = self.make_expense(company="P03-C01 Unconfigured Company")
        for document in (sale, payment, expense):
            with self.subTest(doctype=document.doctype):
                with self.assertRaisesRegex(frappe.ValidationError, "Company|الشركة"):
                    document.validate()

    def test_supply_and_sale_reject_item_outside_configured_group(self):
        item = frappe.db.get_value(
            "Item",
            {
                "item_group": ["not in", self.item_groups],
                "is_stock_item": 1,
                "disabled": 0,
                "stock_uom": "Kg",
            },
            "name",
        )
        if not item:
            self.skipTest("Site has no enabled non-cardboard Kg stock item")
        for document in (self.make_supply(item=item), self.make_sale(item=item)):
            with self.subTest(doctype=document.doctype):
                with self.assertRaisesRegex(frappe.ValidationError, "Cardboard Item Group|مجموعة أصناف الكرتون"):
                    document.validate()

    def test_supply_and_sale_reject_non_kg_items_when_available(self):
        item = frappe.db.get_value(
            "Item",
            {
                "item_group": ["in", self.item_groups],
                "is_stock_item": 1,
                "disabled": 0,
                "stock_uom": ["!=", "Kg"],
            },
            "name",
        )
        if not item:
            self.skipTest("Configured cardboard group has no non-Kg stock item")
        for document in (self.make_supply(item=item), self.make_sale(item=item)):
            with self.subTest(doctype=document.doctype):
                with self.assertRaisesRegex(frappe.ValidationError, "Stock UOM|وحدة"):
                    document.validate()
