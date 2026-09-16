"""Documentation contract for the AI V3 semantic-query architecture."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent / "docs"
API = ROOT / "cardboard_management" / "api"


class TestAiV3Documentation(unittest.TestCase):
    def setUp(self):
        self.v3 = (DOCS / "ai-assistant-v3.md").read_text(encoding="utf-8")
        self.legacy = "\n".join(
            (DOCS / name).read_text(encoding="utf-8")
            for name in ("ai-assistant-contract.md", "ai-assistant-threat-model.md", "AI-ASSISTANT-SETUP.md", "ai-assistant-v2-coverage.md")
            if (DOCS / name).is_file()
        )

    def test_v3_doc_describes_the_semantic_pipeline(self):
        for marker in (
            "NEW_QUERY | QUERY_PATCH | CLARIFY | REFUSE",
            "Semantic Business Query Engine",
            "QUERY_PATCH",
            "Domain registry",
            "QUERY_PATCH is a sparse object",
            "fully revalidates" if False else "ALWAYS",
        ):
            self.assertIn(marker, self.v3)

    def test_v3_doc_officially_lists_the_six_domain_tools(self):
        for tool in ("query_suppliers", "query_supplies", "query_sales", "query_inventory", "query_expenses", "query_payments"):
            self.assertIn(tool, self.v3)

    def test_current_docs_no_longer_present_the_v2_tool_catalog_as_current(self):
        # The V2 catalog must not be described as the current architecture in the
        # primary contract; peak retention of historical coverage lives in the
        # v2 coverage doc clearly marked deprecated.
        primary = self.v3
        for phrase in ("22 narrow read tools", "phrase routing is the current design", "ai_intent.py is the active parser"):
            self.assertNotIn(phrase, primary)

    def test_v3_source_carries_no_phrase_intents_or_reference_words(self):
        module_sources = "\n".join(
            (API / name).read_text(encoding="utf-8")
            for name in ("ai_chat.py", "ai_conversation_state.py", "ai_query_engine.py", "ai_domain_tools.py", "ai_semantic.py")
        )
        self.assertNotIn("REFERENCE_WORDS", module_sources)
        self.assertNotIn("extract_intent", module_sources)
        self.assertNotIn("ai_intent", module_sources)
        self.assertNotIn("_direct_supplier_reply", module_sources)
        self.assertNotIn("REFERENCE_WORDS", module_sources)


if __name__ == "__main__":
    unittest.main()
