"""Database-free contracts for JE reference-type compatibility hardening."""
import unittest

from cardboard_management.setup import merge_reference_type_options


class TestJournalEntryReferenceTypeOptions(unittest.TestCase):
    def test_preserves_base_existing_and_future_options_once(self):
        merged = merge_reference_type_options(
            "\nSales Invoice\nFuture Upstream Reference\n",
            "\nSales Invoice\nQuick Expense\nLegacy Extension\n",
            "Quick Expense",
        )

        self.assertEqual(
            merged,
            "\nSales Invoice\nFuture Upstream Reference\nQuick Expense\nLegacy Extension\n",
        )
        self.assertEqual(merged.count("Quick Expense"), 1)

    def test_is_idempotent(self):
        first = merge_reference_type_options("\nPayment Entry\n", "Quick Expense")
        self.assertEqual(
            merge_reference_type_options(first, "Quick Expense"),
            first,
        )


if __name__ == "__main__":
    unittest.main()
