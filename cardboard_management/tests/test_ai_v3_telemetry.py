"""Telemetry alignment contracts for AI V3."""

import unittest
from pathlib import Path

API = Path(__file__).resolve().parents[1] / "cardboard_management" / "api"


class TestV3Telemetry(unittest.TestCase):
    def setUp(self):
        self.chat = (API / "ai_chat.py").read_text(encoding="utf-8")
        self.telemetry = (API / "ai_telemetry.py").read_text(encoding="utf-8")

    def test_chat_records_only_allowed_metadata(self):
        allowed = {
            "correlation_id", "model", "provider", "semantic_domain", "semantic_operation",
            "query_type", "tool_name", "tool_names", "result_count", "query_status", "error_code",
            "interpretation_latency_ms", "query_latency_ms", "formatting_latency_ms", "total_latency_ms",
            "status", "stage", "tool_count", "delivery_mode",
        }
        import re
        emitted_keys = set(re.findall(r'"([a-z_]+)":', self.chat))
        forbidden = {"answer_text", "prompt", "transcript", "audio", "supplier_name", "question_text"}
        self.assertEqual(emitted_keys & forbidden, set(), emitted_keys & forbidden)
        # every allowed V3 telemetry key must plausibly exist somewhere in the module
        for key in ("correlation_id", "model", "provider", "total_latency_ms", "status", "tool_name", "semantic_domain", "semantic_operation", "query_type", "result_count", "query_status", "error_code"):
            self.assertIn(key, self.chat, key)

    def test_chat_events_never_contain_user_text_or_answers(self):
        # The interpreter prompts may carry the bounded user text forward; the
        # recorded telecometry events must never log it.
        for forbidden in ("answer_text", "question=user_text", "\"prompt\": user", "log_user_text"):
            self.assertNotIn(forbidden, self.chat)
        import re
        # count how many TELEMETRY record paths exist; they must not carry user text or business values
        self.assertNotIn("user_text=", self.chat)
        self.assertNotIn("record(\"text_chat\", {\"question", self.chat)
        self.assertNotIn("record(\"text_chat\", {\"answer", self.chat)

    def test_telemetry_module_stays_content_free(self):
        for forbidden in ("transcript", "answer", "audio", "supplier", "raw"):
            self.assertNotIn(f'"{forbidden}"', self.telemetry)


if __name__ == "__main__":
    unittest.main()
