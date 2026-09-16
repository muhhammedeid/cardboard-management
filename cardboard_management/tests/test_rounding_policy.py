"""P05-UAT-FIX04 rounding policy: whole Kg, money nearest 5 EGP, HALP-UP everywhere."""

import unittest
from decimal import Decimal

from cardboard_management.rounding import round_half_up, round_kg, round_money_to_5


class TestWeightRounding(unittest.TestCase):
    def test_half_up_cases(self):
        cases = (("86.4", 86), ("86.5", 87), ("86.6", 87), ("50.4", 50), ("50.5", 51))
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(round_kg(raw), expected)

    def test_never_bankers(self):
        # bankers would return 86 for 86.5; HALF-UP must return 87
        self.assertEqual(round_half_up("86.5"), 87)
        self.assertEqual(round_half_up("87.5"), 88)

    def test_percentage_discount_example(self):
        net = 2880
        raw = Decimal(str(net)) * Decimal("3") / Decimal("100")
        self.assertEqual(raw, Decimal("86.4"))
        discount_weight = round_kg(raw)
        self.assertEqual(discount_weight, 86)
        self.assertEqual(net - discount_weight, 2794)

    def test_money_nearest_five(self):
        cases = ((14257, 14255), (14258, 14260), (19558, 19560), ("14257.5", 14260))
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(round_money_to_5(raw), expected)

    def test_full_regression_example(self):
        gross, tare = 6300, 3420
        net = round_kg(gross - tare)
        self.assertEqual(net, 2880)
        discount = round_kg(net * 3 / 100)
        self.assertEqual(discount, 86)
        payable = net - discount
        self.assertEqual(payable, 2794)
        total = round_money_to_5(payable * 7)
        self.assertEqual(total, 19560)


class TestControllerSourceContract(unittest.TestCase):
    """The controller must compute through the canonical helpers, in order."""

    def test_controller_uses_canonical_helpers_in_order(self):
        from pathlib import Path

        source = Path(
            "/home/twenty/frappe/cardboard-bench/apps/cardboard_management/cardboard_management/cardboard_management/doctype/cardboard_supply/cardboard_supply.py"
        ).read_text(encoding="utf-8")
        self.assertIn("round_kg(flt(self.gross_weight) - flt(self.tare_weight))", source)
        self.assertIn("round_kg(self.net_weight * discount_value / 100)", source)
        self.assertIn("round_kg(self.net_weight - self.discount_weight)", source)
        self.assertIn("round_money_to_5(flt(self.payable_weight) * flt(self.rate_per_kg))", source)
        # no direct precision flt testimony on the money path anymore
        self.assertNotIn('self.total_amount = flt(', source)
