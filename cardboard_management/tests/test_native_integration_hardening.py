"""Runtime contracts for P03-C02 native mapping and idempotency hardening."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from erpnext.stock.utils import get_stock_balance


class TestCardboardSaleNativeHardening(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings = frappe.get_cached_doc("Cardboard Dashboard Settings")
        cls.company = settings.company
        cls.warehouse = settings.default_warehouse
        cls.item = frappe.db.get_value(
            "Item",
            {"item_group": ["in", [settings.cardboard_item_group]], "is_stock_item": 1, "disabled": 0},
            "name",
        )
        if not cls.item:
            cls.item = frappe.db.get_value(
                "Item", {"is_stock_item": 1, "disabled": 0, "stock_uom": "Kg"}, "name"
            )
        if not cls.item or not cls.warehouse:
            raise unittest.SkipTest("P03-C02 sale fixtures are unavailable")

    def make_sale(self, quantity=1):
        return frappe.get_doc(
            {
                "doctype": "Cardboard Sale",
                "posting_date": nowdate(),
                "item": self.item,
                "quantity": quantity,
                "rate_per_kg": 1,
                "company": self.company,
                "warehouse": self.warehouse,
            }
        )

    def test_retry_reuses_linked_stock_entry_before_stock_check(self):
        available = flt(get_stock_balance(self.item, self.warehouse, nowdate()))
        if available <= 0:
            self.skipTest("Sale retry test requires available stock")

        sale = self.make_sale(quantity=available).insert()
        try:
            sale.submit()
            sale.reload()
            stock_entry_name = sale.stock_entry
            self.assertTrue(stock_entry_name)

            retry = frappe.get_doc("Cardboard Sale", sale.name)
            retry.docstatus = 0
            retry.on_submit()
            retry.reload()

            self.assertEqual(retry.stock_entry, stock_entry_name)
            self.assertEqual(
                frappe.db.count("Stock Entry", {"name": stock_entry_name}),
                1,
            )
        finally:
            sale.reload()
            if sale.docstatus == 1:
                sale.cancel()

    def test_tampered_stock_entry_mapping_rejects_submit_retry_and_cancel(self):
        sale = self.make_sale(quantity=1).insert()
        sale.submit()
        sale.reload()
        stock_entry_name = sale.stock_entry
        original_purpose = frappe.db.get_value("Stock Entry", stock_entry_name, "purpose")
        try:
            frappe.db.set_value("Stock Entry", stock_entry_name, "purpose", "Material Receipt", update_modified=False)
            retry = frappe.get_doc("Cardboard Sale", sale.name)
            retry.docstatus = 0
            with self.assertRaisesRegex(frappe.ValidationError, "does not match the sale"):
                retry.on_submit()
            with self.assertRaisesRegex(frappe.ValidationError, "does not match the sale"):
                sale.cancel()
        finally:
            frappe.db.set_value("Stock Entry", stock_entry_name, "purpose", original_purpose, update_modified=False)


class TestSupplierPaymentNativeHardening(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.db.get_single_value("Cardboard Dashboard Settings", "company")
        cls.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
        cls.item = frappe.db.get_value("Item", {"disabled": 0, "is_stock_item": 1}, "name")
        cls.warehouse = frappe.db.get_value(
            "Warehouse", {"company": cls.company, "disabled": 0, "is_group": 0}, "name"
        )
        cls.mode_of_payment = None
        for mode in frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name"):
            if frappe.get_all(
                "Mode of Payment Account",
                filters={"parent": mode, "company": cls.company},
                pluck="default_account",
            ):
                cls.mode_of_payment = mode
                break
        if not all((cls.company, cls.supplier, cls.item, cls.warehouse, cls.mode_of_payment)):
            raise unittest.SkipTest("P03-C02 payment fixtures are unavailable")

    def make_invoice(self, supplier=None):
        invoice = frappe.get_doc(
            {
                "doctype": "Purchase Invoice",
                "supplier": supplier or self.supplier,
                "company": self.company,
                "posting_date": nowdate(),
                "set_posting_time": 1,
                "items": [
                    {
                        "item_code": self.item,
                        "qty": 10,
                        "rate": 10,
                        "warehouse": self.warehouse,
                    }
                ],
            }
        )
        invoice.insert()
        invoice.submit()
        return invoice

    def make_payment(self, supplier=None, amount=10):
        return frappe.get_doc(
            {
                "doctype": "Cardboard Supplier Payment",
                "posting_date": nowdate(),
                "supplier": supplier or self.supplier,
                "amount": amount,
                "mode_of_payment": self.mode_of_payment,
            }
        )

    def test_retry_reuses_valid_payment_entry_without_duplication(self):
        invoice = self.make_invoice()
        payment = self.make_payment(amount=10).insert()
        payment.submit()
        payment.reload()
        entry_name = payment.payment_entry

        retry = frappe.get_doc("Cardboard Supplier Payment", payment.name)
        retry.docstatus = 0
        retry.on_submit()
        retry.reload()

        self.assertEqual(retry.payment_entry, entry_name)
        self.assertEqual(frappe.db.count("Payment Entry", {"name": entry_name}), 1)
        invoice.reload()
        self.assertEqual(flt(invoice.outstanding_amount), flt(invoice.grand_total) - 10)

    def test_tampered_payment_entry_reference_rejects_retry_and_cancel(self):
        supplier_b = frappe.get_doc(
            {
                "doctype": "Supplier",
                "supplier_name": f"_P03C02 Supplier {frappe.generate_hash(length=8)}",
                "supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
            }
        ).insert()
        self.make_invoice()
        other_invoice = self.make_invoice(supplier=supplier_b.name)
        payment = self.make_payment(amount=10).insert()
        payment.submit()
        payment.reload()
        reference_name = frappe.db.get_value(
            "Payment Entry Reference", {"parent": payment.payment_entry}, "name"
        )
        frappe.db.set_value("Payment Entry Reference", reference_name, "reference_name", other_invoice.name, update_modified=False)

        retry = frappe.get_doc("Cardboard Supplier Payment", payment.name)
        retry.docstatus = 0
        with self.assertRaisesRegex(frappe.ValidationError, "does not match the payment request"):
            retry.on_submit()
        with self.assertRaisesRegex(frappe.ValidationError, "does not match the payment request"):
            payment.cancel()


class TestQuickExpenseNativeHardening(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.db.get_single_value("Cardboard Dashboard Settings", "company")
        cls.expense_account = frappe.db.get_value(
            "Account", {"company": cls.company, "root_type": "Expense", "is_group": 0, "disabled": 0}, "name"
        )
        cls.payment_account = frappe.db.get_value(
            "Account",
            {
                "company": cls.company,
                "account_type": ["in", ["Cash", "Bank"]],
                "is_group": 0,
                "disabled": 0,
            },
            "name",
        )
        if not all((cls.company, cls.expense_account, cls.payment_account)):
            raise unittest.SkipTest("P03-C02 expense fixtures are unavailable")

    def make_expense(self, amount=25):
        return frappe.get_doc(
            {
                "doctype": "Quick Expense",
                "posting_date": nowdate(),
                "company": self.company,
                "expense_account": self.expense_account,
                "amount": amount,
                "payment_account": self.payment_account,
            }
        )

    def test_retry_reuses_valid_journal_entry_without_duplication(self):
        expense = self.make_expense().insert()
        expense.submit()
        expense.reload()
        journal_name = expense.accounting_document

        retry = frappe.get_doc("Quick Expense", expense.name)
        retry.create_journal_entry()
        retry.reload()

        self.assertEqual(retry.accounting_document, journal_name)
        self.assertEqual(frappe.db.count("Journal Entry", {"name": journal_name}), 1)

    def test_tampered_journal_entry_reference_rejects_retry_and_cancel(self):
        expense = self.make_expense().insert()
        expense.submit()
        expense.reload()
        row_name = frappe.db.get_value(
            "Journal Entry Account", {"parent": expense.accounting_document, "account": self.expense_account}, "name"
        )
        frappe.db.set_value("Journal Entry Account", row_name, "reference_name", "P03-C02-OTHER", update_modified=False)

        retry = frappe.get_doc("Quick Expense", expense.name)
        with self.assertRaisesRegex(frappe.ValidationError, "Linked Journal Entry"):
            retry.create_journal_entry()
        with self.assertRaisesRegex(frappe.ValidationError, "Linked Journal Entry"):
            expense.cancel()
