import unittest
from unittest.mock import patch

import frappe

from cardboard_management import reporting


class TestSupplierStatementRuntime(unittest.TestCase):
    def summary(self, supplies=None, payments=None):
        return {
            'supplier': {'name': 'SUP-001', 'supplier_name': 'مورد'}, 'from_date': '2026-09-01', 'to_date': '2026-09-12',
            'scope': {}, 'supply_count': len(supplies or []), 'supplied_payable_weight': 0, 'supply_value': 0,
            'supplier_payments': 0, 'outstanding': 0, 'outstanding_semantics': 'current_erpnext_purchase_invoice_outstanding',
            'supply_history': supplies or [], 'payment_history': payments or [],
        }

    def test_supplier_and_date_filters_are_forwarded(self):
        with patch.object(reporting, 'get_supplier_summary', return_value=self.summary()) as summary:
            reporting.get_supplier_statement('SUP-001', '2026-09-01', '2026-09-12')
        summary.assert_called_once_with('SUP-001', '2026-09-01', '2026-09-12')

    def test_supplier_required_and_permission_errors_propagate(self):
        with self.assertRaises(TypeError): reporting.get_supplier_statement()
        with patch.object(reporting, 'get_supplier_summary', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError): reporting.get_supplier_statement('SUP-001')

    def test_supply_only_payment_only_and_mixed_timeline_are_typed_and_ordered(self):
        supplies = [{'posting_date': '2026-09-11', 'supply': 'SUPPLY-1', 'item_name': 'كرتون', 'payable_weight': 10, 'value': 20}]
        payments = [{'posting_date': '2026-09-12', 'payment': 'PAY-1', 'mode_of_payment': 'نقدي', 'amount': 10}]
        with patch.object(reporting, 'get_supplier_summary', return_value=self.summary(supplies, payments)):
            result = reporting.get_supplier_statement('SUP-001')
        self.assertEqual([entry['type'] for entry in result['entries']], ['payment', 'supply'])
        self.assertEqual(result['entries'][0]['name'], 'PAY-1')
        self.assertEqual(result['entries'][1]['quantity'], 10)
        self.assertNotIn('running_balance', result)

    def test_tie_order_is_deterministic_and_response_has_no_fabricated_balances(self):
        supplies = [{'posting_date': '2026-09-12', 'supply': 'B-SUPPLY', 'item_name': 'كرتون', 'payable_weight': 1, 'value': 2}]
        payments = [{'posting_date': '2026-09-12', 'payment': 'A-PAYMENT', 'mode_of_payment': 'نقدي', 'amount': 1}]
        with patch.object(reporting, 'get_supplier_summary', return_value=self.summary(supplies, payments)):
            result = reporting.get_supplier_statement('SUP-001')
        self.assertEqual([entry['name'] for entry in result['entries']], ['B-SUPPLY', 'A-PAYMENT'])
        self.assertEqual(set(result) >= {'supplier', 'from_date', 'to_date', 'outstanding', 'entries'}, True)
        self.assertTrue(all('running_balance' not in entry for entry in result['entries']))


if __name__ == '__main__':
    unittest.main()
