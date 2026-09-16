"""Read-only and security regression contracts for the AI V3 semantic surface."""

import unittest
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "cardboard_management" / "api"
V3_FILES = ("ai_semantic.py", "ai_query_engine.py", "ai_domain_tools.py", "ai_chat.py", "ai_conversation_state.py")

FORBIDDEN_MUTATIONS = (
    ".insert(", ".save()", ".submit()", ".cancel()",
    "frappe.delete_doc", "frappe.new_doc", "frappe.get_doc(", "frappe.db.set_value",
    "frappe.db.sql", "frappe.db.commit", "frappe.enqueue",
    "Payment Entry", "Journal Entry", "Stock Entry", "make_stock_entry",
)


class TestV3ReadOnlySurface(unittest.TestCase):
    def setUp(self):
        self.sources = {name: (API_ROOT / name).read_text(encoding="utf-8") for name in V3_FILES}

    def test_v3_modules_carry_no_mutation_or_sql_or_generic_access(self):
        for name, source in self.sources.items():
            for token in FORBIDDEN_MUTATIONS:
                self.assertNotIn(token, source, f"{name} must not contain {token}")

    def test_engine_scope_only_routes_to_documented_services(self):
        engine = self.sources["ai_query_engine.py"]
        for allowed in (
            "reporting.get_supplier_summary",
            "reporting.get_outstanding_report",
            "reporting.get_operations_summary",
            "reporting.get_sales_summary",
            "reporting.get_expense_summary",
            "get_inventory_overview",
        ):
            self.assertIn(allowed, engine)
        self.assertNotIn("frappe.get_all(", engine)

    def test_entity_lookup_uses_permission_aware_get_list(self):
        engine = self.sources["ai_query_engine.py"]
        self.assertIn("frappe.get_list(", engine)
        self.assertNotIn("frappe.get_all(", engine)

    def test_chat_gate_blocks_guests_and_requires_operational_role(self):
        chat = self.sources["ai_chat.py"]
        self.assertIn("require_ai_read_access", chat)
        engine = self.sources["ai_query_engine.py"]
        self.assertIn("AI_READ_ROLES", engine)
        self.assertIn("frappe.has_permission", engine)

    def test_rate_limit_and_message_bounds_survive(self):
        chat = self.sources["ai_chat.py"]
        self.assertIn("_rate_limit", chat)
        self.assertIn("MAX_MESSAGES", chat)
        self.assertIn("MAX_MESSAGE_CHARS", chat)

    def test_tts_and_stt_model_contract_is_untouched(self):
        provider = (API_ROOT / "ai_provider.py").read_text(encoding="utf-8")
        self.assertIn('"deepseek/deepseek-v4-flash-0731"', provider)
        self.assertIn('"openai/whisper-large-v3"', provider)
        self.assertIn('"google/gemini-3.1-flash-tts-preview"', provider)
        self.assertIn('"data_collection": "deny"', provider)
        self.assertIn('"zdr": True', provider)


if __name__ == "__main__":
    unittest.main()
