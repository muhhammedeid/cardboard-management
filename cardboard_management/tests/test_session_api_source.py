import unittest
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "cardboard_management" / "api" / "session.py"


class TestSessionApiSource(unittest.TestCase):
    def test_session_context_exposes_authenticated_csrf_and_ai_capability_contract(self):
        source = SOURCE.read_text()
        self.assertIn('@frappe.whitelist(methods=["GET"])', source)
        self.assertIn("def get_session_context", source)
        self.assertIn("frappe.session.user == \"Guest\"", source)
        self.assertIn("from frappe.sessions import get_csrf_token", source)
        self.assertIn('"csrf_token": get_csrf_token()', source)
        self.assertIn("from cardboard_management.cardboard_management.api.ai_chat import can_use_ai_assistant", source)
        self.assertIn('"can_use_ai_assistant": can_use_ai_assistant()', source)


if __name__ == "__main__":
    unittest.main()
