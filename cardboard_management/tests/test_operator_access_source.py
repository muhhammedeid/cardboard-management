"""Contracts for role-scoped operational defaults and permissions."""
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SETUP = APP / "setup.py"
PROFILE = APP / "fixtures" / "module_profile.json"
HOOKS = APP / "hooks.py"


class TestOperatorAccessSource(unittest.TestCase):
    def test_native_user_default_workspace_is_role_scoped(self):
        source = SETUP.read_text(encoding="utf-8")
        self.assertIn('OPERATOR_ROLE = "Cardboard Operator"', source)
        self.assertIn('OPERATOR_WORKSPACE = "Cardboard Management"', source)
        self.assertIn('default_workspace', source)
        self.assertIn('Administrator', source)
        self.assertIn('ensure_cardboard_operator_defaults', source)
        hooks = HOOKS.read_text(encoding="utf-8")
        self.assertIn('"User": {"on_update":', hooks)
        self.assertIn('ensure_cardboard_operator_default_workspace', hooks)

    def test_operator_permissions_are_minimal_and_cover_workspace_routes(self):
        source = SETUP.read_text(encoding="utf-8")
        for doctype, permissions in {
            "Cardboard Supply": {"read", "write", "create", "submit"},
            "Quick Expense": {"read", "write", "create", "submit"},
            "Cardboard Supplier Payment": {"read", "write", "create", "submit"},
            "Supplier": {"read", "write", "create"},
            "Item": {"read"},
            "Warehouse": {"read"},
            "Stock Ledger Entry": {"read", "report"},
            "Purchase Invoice": {"read", "report"},
        }.items():
            self.assertIn(doctype, source)
            for permission in permissions:
                self.assertIn(f'"{permission}"', source)
        for report in ("Stock Balance", "Accounts Payable", "Purchase Register"):
            self.assertIn(report, source)
        self.assertIn('OPERATOR_PERMISSION_FIELDS', source)
        self.assertIn('1 if permission in permissions else 0', source)
        self.assertIn('filters={"parent": doctype, "role": OPERATOR_ROLE, "permlevel": 0, "if_owner": 0}', source)
        self.assertIn('"Stock Ledger Entry": {"read", "report"}', source)
        self.assertNotIn('"delete": 1', source)
        self.assertNotIn('"cancel": 1', source)

    def test_module_profile_retains_only_operational_presentation_modules(self):
        profile = PROFILE.read_text(encoding="utf-8")
        for blocked in ("Accounts", "Buying", "Stock", "Manufacturing", "Website"):
            self.assertIn(f'"module": "{blocked}"', profile)
        for visible in ("Cardboard Management", "Core", "Desk", "Printing"):
            self.assertNotIn(f'"module": "{visible}"', profile)


if __name__ == "__main__":
    unittest.main()
