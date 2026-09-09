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
    "New Cardboard Supply": "توريدة جديدة",
    "New Supplier Payment": "دفعة مورد",
    "Main Work Areas": "مناطق العمل الرئيسية",
}

# P03-R02: the operational supplier-payment surface must translate every
# user-facing label in ar.csv (source string -> exact Arabic target).
EXPECTED_PAYMENT_UX = {
    "Cardboard Supplier Payment": "دفعة المورد",
    "Payment Details": "بيانات الدفعة",
    "Supplier": "المورد",
    "Amount": "المبلغ",
    "Mode of Payment": "طريقة الدفع",
    "Payment References": "مراجع الدفع",
    "Save and Submit Payment": "حفظ واعتماد الدفعة",
    "Current Supplier Outstanding": "مستحقات المورد الحالية",
    "Expected Remaining Outstanding": "المستحق المتوقع بعد الدفعة",
    "Payment Entry": "سند دفع",
    "Payment Status": "حالة الدفع",
    "Payment Summary": "ملخص الدفعة",
    "Notes": "ملاحظات",
    "Reference No": "رقم المرجع",
    "Reference Date": "تاريخ المرجع",
    "No outstanding invoices exist for this supplier": "لا توجد فواتير مستحقة لهذا المورد",
    "Amount must be greater than zero": "يجب أن يكون المبلغ أكبر من صفر",
    "Amount exceeds the total outstanding": "المبلغ يتجاوز إجمالي المستحق",
    "Supplier is required": "المورد مطلوب",
    "Supplier {0} does not exist": "المورد {0} غير موجود",
    "Mode of Payment is required": "طريقة الدفع مطلوبة",
    "Mode of Payment {0} does not exist": "طريقة الدفع {0} غير موجودة",
    "Mode of Payment {0} is disabled": "طريقة الدفع {0} موقوفة",
    "This supplier is disabled": "هذا المورد موقوف",
    "Reference No is required when a Reference Date is set":
        "رقم المرجع مطلوب عند تحديد تاريخ المرجع",
    "No enabled Mode of Payment Account is mapped for {0} in company {1}":
        "لا توجد حسابات مفعلة مربوطة بطريقة الدفع {0} في شركة {1}",
    "Configure Company in Cardboard Dashboard Settings before recording supplier payments":
        "حدد الشركة في إعدادات لوحة المعلومات قبل تسجيل دفعات الموردين",
    "Company {0} in Cardboard Dashboard Settings does not exist":
        "الشركة {0} في إعدادات لوحة المعلومات غير موجودة",
    "Cardboard Supplier Payment {0} has no linked Payment Entry":
        "الدفعة {0} لا يرتبط بها سند دفع",
    "Generated Payment Entry {0} must be submitted before cancelling":
        "يجب اعتماد سند الدفع {0} قبل الإلغاء",
    "Generated Payment Entry {0} does not match the payment request":
        "سند الدفع {0} المُنشأ لا يطابق طلب الدفعة",
    "Generated Payment Entry {0} is cancelled; a duplicate will not be created":
        "سند الدفع {0} ملغي؛ لن يتم إنشاء نسخة مكررة",
    "Current Supplier Outstanding: {0}": "مستحقات المورد الحالية: {0}",
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
                       "Rate per Kg", "Total Amount", "Expense Account", "Journal Entry",
                       "New Supplier", "New Supplier Payment", "Supplier Name", "Payment Type",
                       "Expense Details", "Expense Category", "Payment Account", "Payment Mode",
                       "Party (Optional)", "Reference", "Attachment", "Accounting Integration",
                       "Date", "No Discount", "Kg", "Percentage"):
            self.assertIn(source, catalogue)
        # P03-R02 payment UX contract: all user-facing payment labels translated.
        self.assertEqual({key: catalogue[key] for key in EXPECTED_PAYMENT_UX}, EXPECTED_PAYMENT_UX)
        self.assertTrue(all(any("\u0600" <= char <= "\u06ff" for char in target)
                            for target in EXPECTED_PAYMENT_UX.values()))
        self.assertIn("Cardboard Supplier Payment", catalogue)
        self.assertEqual(catalogue["Save and Submit Payment"], "حفظ واعتماد الدفعة")

    def test_internal_workspace_targets_remain_english_and_no_report_is_added(self):
        workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        targets = [row.get("link_to", "") for row in workspace["shortcuts"] + workspace["links"]]
        self.assertTrue(all(not any("\u0600" <= char <= "\u06ff" for char in target)
                            for target in targets))
        self.assertFalse(any(path.name == "report" for path in APP.rglob("report")))


if __name__ == "__main__":
    unittest.main()
