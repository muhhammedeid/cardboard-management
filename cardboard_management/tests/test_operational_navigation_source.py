"""Database-free contract for native Cardboard operator navigation."""
import json
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
HOOKS = APP / "hooks.py"
WORKSPACE = APP / "cardboard_management" / "workspace" / "cardboard_management" / "cardboard_management.json"
ROLE = APP / "fixtures" / "role.json"
PROFILE = APP / "fixtures" / "module_profile.json"


class TestOperationalNavigationSource(unittest.TestCase):
    def test_operator_role_and_native_module_profile_are_shipped_unassigned(self):
        hooks = HOOKS.read_text(encoding="utf-8")
        self.assertIn('"Cardboard Operator"', hooks)
        self.assertIn('"Role"', hooks)
        self.assertIn('"Module Profile"', hooks)

        role = json.loads(ROLE.read_text(encoding="utf-8"))
        self.assertEqual(role, [{"doctype": "Role", "name": "Cardboard Operator",
                                 "role_name": "Cardboard Operator", "disabled": 0,
                                 "is_custom": 1, "desk_access": 1}])

        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile[0]["doctype"], "Module Profile")
        self.assertEqual(profile[0]["name"], "Cardboard Operator")
        self.assertEqual(profile[0]["module_profile_name"], "Cardboard Operator")
        self.assertFalse(any("user" in key.lower() for key in profile[0]))
        blocked = {row["module"] for row in profile[0]["block_modules"]}
        self.assertIn("Accounts", blocked)
        self.assertIn("Stock", blocked)
        self.assertIn("Buying", blocked)
        self.assertNotIn("Cardboard Management", blocked)

    def test_workspace_visibility_is_role_scoped_but_administrator_routes_unchanged(self):
        workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        self.assertEqual(workspace["roles"], [{"role": "Cardboard Operator"}])
        self.assertEqual(workspace["public"], 1)
        self.assertEqual(workspace["for_user"], "")
        self.assertNotIn("Payment Entry", [shortcut["link_to"] for shortcut in workspace["shortcuts"]])


if __name__ == "__main__":
    unittest.main()
