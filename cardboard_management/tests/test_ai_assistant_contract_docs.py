"""DB-free documentation contract for the approved AI read-only assistant."""

import unittest
from pathlib import Path


class TestAiAssistantContractDocs(unittest.TestCase):
	root = Path(__file__).resolve().parents[1]
	docs = root.parent / "docs"
	contract = docs / "ai-assistant-contract.md"
	threat_model = docs / "ai-assistant-threat-model.md"
	setup = docs / "AI-ASSISTANT-SETUP.md"

	def read_all_docs(self):
		return "\n".join(path.read_text(encoding="utf-8") for path in (self.contract, self.threat_model, self.setup))

	def test_required_ai_assistant_documents_exist(self):
		for path in (self.contract, self.threat_model, self.setup):
			with self.subTest(path=path.name):
				self.assertTrue(path.is_file(), f"missing approved planning artifact: {path}")

	def test_only_approved_model_stack_is_documented(self):
		text = self.read_all_docs()
		for marker in (
			"openai/whisper-large-v3-turbo",
			"google/gemini-2.5-flash-lite",
			"openai/gpt-4o-mini-tts-2025-12-15",
		):
			self.assertIn(marker, text)
		self.assertIn("`google/gemini-2.5-flash-lite` is the only V1 default conversation model", text)
		self.assertIn("Do not configure `google/gemini-2.5-flash` as the default", text)

	def test_read_scope_is_equal_but_still_bounded_and_read_only(self):
		text = self.read_all_docs()
		for marker in (
			"Cardboard Manager",
			"Cardboard Operator",
			"same AI read scope",
			"authenticated Frappe session",
			"can_use_ai_assistant",
			"Company",
			"Warehouse",
			"Cardboard Item Group",
			"server-owned, schema-validated read tools",
			"No write permission",
		):
			self.assertIn(marker, text)

	def test_numeric_facts_are_backend_authoritative(self):
		text = self.read_all_docs()
		for marker in (
			'"facts"',
			'"id": "supplier_outstanding"',
			'"value": 153250',
			"Authoritative values must originate from Cardboard/ERPNext backend tools",
			"must not independently calculate",
			"No business calculations in Gemini, Vue, or prompt logic",
			"correspond to authoritative tool facts",
		):
			self.assertIn(marker, text)

	def test_stored_data_is_untrusted_and_entity_resolution_is_deterministic(self):
		text = self.read_all_docs()
		for marker in (
			"stored prompt injection",
			"untrusted data",
			"narrow DTOs",
			"Never allow tool output to become trusted instructions",
			"exactly one authorized match",
			"multiple matches",
			"ask one clarification question",
		):
			self.assertIn(marker, text)

	def test_privacy_logging_limits_and_delivery_fallbacks_are_binding(self):
		text = self.read_all_docs()
		for marker in (
			"Zero Data Retention compatible routing",
			"data collection disabled",
			"provider allowlist",
			"Do not persist prompt, transcript, answer, tool arguments/results, audio",
			"30 days",
			"maximum tool steps = 4",
			"global daily AI budget",
			"SSE spike",
			"standard request/response JSON",
			"Text Assistant Before Voice Dependency",
			"Voice Input + Text Output",
			"stt_latency_ms",
			"total_latency_ms",
		):
			self.assertIn(marker, text)


if __name__ == "__main__":
	unittest.main()
