import unittest

import frappe

from cardboard_management.cardboard_management.api import without_transport_metadata
from cardboard_management.cardboard_management.api import expenses, operational_settings, sales, supplier_payments, suppliers


class TestRpcTransportMetadata(unittest.TestCase):
    def test_only_cmd_is_removed(self):
        self.assertEqual(
            without_transport_metadata({"cmd": "app.method", "supplier_name": "UAT Supplier 01", "unknown": "keep"}),
            {"supplier_name": "UAT Supplier 01", "unknown": "keep"},
        )

    def test_strict_create_update_boundaries_preserve_unknown_field_rejection(self):
        self.assertEqual(sales._coerce_values({"cmd": "app.method", "buyer_name": "Buyer"}), {"buyer_name": "Buyer"})
        self.assertEqual(supplier_payments._editable_values({"cmd": "app.method", "amount": 100}), {"amount": 100})
        self.assertEqual(expenses._values({"cmd": "app.method", "expense_category": "Expense", "payment_source": "Cash", "amount": 100}), {"expense_account": "Expense", "payment_account": "Cash", "amount": 100})

        for action in (
            lambda: sales._coerce_values({"unknown": "reject"}),
            lambda: supplier_payments._editable_values({"unknown": "reject"}),
            lambda: expenses._values({"unknown": "reject"}),
        ):
            with self.assertRaises(frappe.ValidationError):
                action()

    def test_operational_settings_update_uses_the_shared_transport_boundary(self):
        source = open(operational_settings.__file__, encoding="utf-8").read()
        self.assertIn("values=without_transport_metadata(values)", source)

    def test_supplier_create_boundary_accepts_cmd_but_rejects_unknown_fields(self):
        values = {"cmd": "app.method", "supplier_name": "UAT Supplier 01", "supplier_type": "Company"}
        payload = suppliers._validated_create_values(values)
        self.assertNotIn("cmd", payload)
        with self.assertRaises(frappe.ValidationError):
            suppliers._validated_create_values({**values, "unknown": "reject"})
