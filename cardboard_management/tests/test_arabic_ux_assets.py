"""Database-free contracts for route-scoped Arabic/RTL Desk assets."""
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
HOOKS = APP / "hooks.py"
CSS = APP / "public" / "css" / "cardboard_management.css"
JS = APP / "public" / "js" / "cardboard_management.js"


class TestArabicUxAssets(unittest.TestCase):
    def test_hooks_register_app_owned_assets_without_changing_core_hooks(self):
        hooks = HOOKS.read_text(encoding="utf-8")
        self.assertIn('required_apps = ["erpnext"]', hooks)
        self.assertIn('after_install = "cardboard_management.setup.ensure_purchase_invoice_integration_schema"', hooks)
        self.assertIn('after_migrate = "cardboard_management.setup.ensure_purchase_invoice_integration_schema"', hooks)
        self.assertIn('/assets/cardboard_management/css/cardboard_management.css', hooks)
        self.assertIn('/assets/cardboard_management/js/cardboard_management.js', hooks)

    def test_javascript_scope_is_an_explicit_app_only_allowlist(self):
        source = JS.read_text(encoding="utf-8")
        for allowed in ("Cardboard Management", "Cardboard Supply", "Quick Expense",
                        "Cardboard Dashboard Settings", "Supplier", "Payment Entry"):
            self.assertIn(allowed, source)
        for standard in ('"Item"', '"Warehouse"', '"Stock Balance"', '"Accounts Payable"'):
            self.assertNotIn(standard, source)
        self.assertIn('router?.on?.("change", apply_route_scope)', source)
        self.assertIn('document.addEventListener("DOMContentLoaded", schedule_register', source)
        self.assertIn('schedule_register();', source)
        self.assertIn('classList.toggle(SURFACE_CLASS, operational)', source)
        self.assertIn('classList.toggle(RTL_CLASS, operational && is_rtl())', source)
        self.assertNotRegex(source, r"\.(hide|remove)\s*\(")
        self.assertNotIn("permission", source.lower())

    def test_css_is_fully_scoped_without_hiding_or_important_rules(self):
        source = CSS.read_text(encoding="utf-8")
        self.assertNotIn("!important", source)
        self.assertNotRegex(source, r"\b(display\s*:\s*none|visibility\s*:\s*hidden)\b")
        self.assertIn("margin-inline", source)
        self.assertIn("padding-inline", source)
        self.assertIn("direction: rtl", source)
        self.assertIn(".layout-main-section", source)
        self.assertIn(".form-section", source)
        self.assertIn(".btn-primary", source)
        clean_source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
        selector_groups = re.findall(r"(?:^|\})([^{}]+)\{", clean_source, flags=re.MULTILINE)
        selectors = [item.strip() for group in selector_groups for item in group.split(",")]
        self.assertTrue(selectors)
        self.assertTrue(all(selector.startswith("body.cardboard-management-surface")
                            for selector in selectors), selectors)


if __name__ == "__main__":
    unittest.main()
