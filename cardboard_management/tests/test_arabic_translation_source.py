"""Database-free contracts for the Arabic translation foundation."""
import csv
import json
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
TRANSLATIONS = APP / "translations" / "ar.csv"
WORKSPACE = APP / "cardboard_management" / "workspace" / "cardboard_management" / "cardboard_management.json"

EXPECTED_NAVIGATION = {
    "Operational Home": "الرئيسية",
    "Supplies": "التوريدات",
    "Suppliers": "الموردون",
    "Payments": "المدفوعات",
    "Expenses": "المصروفات",
    "Inventory": "المخزون",
    "Reports": "التقارير",
    "Settings": "الإعدادات",
}


class TestArabicTranslationSource(unittest.TestCase):
    def test_arabic_catalogue_is_valid_and_contains_operational_navigation(self):
        self.assertTrue(TRANSLATIONS.is_file())
        with TRANSLATIONS.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))

        self.assertGreaterEqual(len(rows), 40)
        self.assertTrue(all(len(row) == 3 for row in rows))
        self.assertTrue(all(row[0].strip() and row[1].strip() and not row[2] for row in rows))
        sources = [row[0] for row in rows]
        self.assertEqual(len(sources), len(set(sources)))
        catalogue = {source: target for source, target, _context in rows}
        self.assertEqual({key: catalogue[key] for key in EXPECTED_NAVIGATION}, EXPECTED_NAVIGATION)
        self.assertTrue(all(any("\u0600" <= char <= "\u06ff" for char in target)
                            for target in EXPECTED_NAVIGATION.values()))
        for source in ("Cardboard Supply", "Quick Expense", "Gross Weight", "Net Weight",
                       "Rate per Kg", "Total Amount", "Expense Account", "Journal Entry"):
            self.assertIn(source, catalogue)

    def test_internal_workspace_targets_remain_english_and_no_report_is_added(self):
        workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        targets = [row.get("link_to", "") for row in workspace["shortcuts"] + workspace["links"]]
        self.assertTrue(all(not any("\u0600" <= char <= "\u06ff" for char in target)
                            for target in targets))
        self.assertFalse(any(path.name == "report" for path in APP.rglob("report")))


if __name__ == "__main__":
    unittest.main()
