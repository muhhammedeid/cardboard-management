"""Database-free contract for Cardboard-only Egyptian Pound presentation."""
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
JS = APP / "public" / "js" / "cardboard_management.js"


class TestCurrencyPresentation(unittest.TestCase):
    def test_operational_routes_normalize_only_the_known_egp_symbol(self):
        source = JS.read_text(encoding="utf-8")
        self.assertIn('const MALFORMED_EGP_SYMBOL = "£ or ج.م"', source)
        self.assertIn('const OPERATIONAL_EGP_SYMBOL = "ج.م"', source)
        self.assertIn("normalize_operational_currency_text", source)
        self.assertIn("classList.contains(SURFACE_CLASS)", source)
        self.assertIn("TreeWalker", source)
        self.assertNotIn("window.format_currency =", source)
        self.assertNotIn("frappe.currency_symbols", source)


if __name__ == "__main__":
    unittest.main()
