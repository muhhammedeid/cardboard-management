"""DB-free contracts for the AI V3 conversation state (validated query only)."""

import unittest


class TestV3ConversationState(unittest.TestCase):
    def setUp(self):
        from cardboard_management.cardboard_management.api import ai_conversation_state
        self.state = ai_conversation_state

    def test_empty_state_shape(self):
        cleaned = self.state.empty_state()
        self.assertEqual(set(cleaned), {"version", "last_semantic_query", "last_resolved_entities"})
        self.assertIsNone(cleaned["last_semantic_query"])

    def test_only_validated_queries_are_persisted(self):
        from cardboard_management.cardboard_management.api import ai_semantic as semantic
        good = {
            "version": "1", "domain": "suppliers", "operation": "rank",
            "sort": {"field": "outstanding", "direction": "desc"}, "limit": 5,
        }
        cleaned = self.state._clean_state({"last_semantic_query": good})
        self.assertEqual(cleaned["last_semantic_query"]["operation"], "rank")
        dirty = self.state._clean_state({"last_semantic_query": {"version": "1", "domain": "nope", "operation": "list"}})
        self.assertIsNone(dirty["last_semantic_query"])

    def test_entities_are_bounded_and_filtered(self):
        cleaned = self.state._clean_state({
            "last_resolved_entities": {
                "supplier": "محمد عيد",
                "item": "CARDBOARD",
                "hacker": "x",
                "leak": "x" * 500,
            }
        })
        self.assertEqual(set(cleaned["last_resolved_entities"]), {"supplier", "item"})
        for value in cleaned["last_resolved_entities"].values():
            self.assertLessEqual(len(value), 140)

    def test_semantic_prompt_is_value_free(self):
        query = {
            "version": "1", "domain": "supplies", "operation": "aggregate",
            "filters": {"supplier": "محمد عيد"},
            "period": {"type": "month_to_date"},
            "aggregation": {"payable_weight_tons": "sum"},
        }
        prompt = self.state.semantic_prompt({"last_semantic_query": query})
        self.assertIn("supplies", prompt)
        self.assertNotIn("محمد", prompt)
        self.assertNotIn("filters", prompt)


if __name__ == "__main__":
    unittest.main()
