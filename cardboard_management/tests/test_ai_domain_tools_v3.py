"""DB-free contracts for the six AI-facing domain tools (V3)."""

import importlib
import unittest


class TestDomainToolSurface(unittest.TestCase):
    def setUp(self):
        self.tools = importlib.import_module("cardboard_management.cardboard_management.api.ai_domain_tools")
        self.semantic = importlib.import_module("cardboard_management.cardboard_management.api.ai_semantic")

    def test_final_model_visible_tool_count_is_six(self):
        self.assertEqual(len(self.tools.TOOL_NAMES), 6)
        self.assertEqual(set(self.tools.TOOL_NAMES), {
            "query_suppliers", "query_supplies", "query_sales",
            "query_inventory", "query_expenses", "query_payments",
        })

    def test_registry_covers_exactly_the_registered_domains(self):
        self.assertEqual(
            set(self.tools._DOMAIN_BY_TOOL.values()),
            set(self.semantic.DOMAIN_REGISTRY),
        )

    def test_tool_schemas_are_published_for_each_domain(self):
        schemas = self.tools.tool_schemas()
        self.assertEqual(len(schemas), 6)
        names = {schema["function"]["name"] for schema in schemas}
        self.assertEqual(names, set(self.tools.TOOL_NAMES))
        for schema in schemas:
            self.assertEqual(schema["function"]["parameters"]["additionalProperties"], False)
            self.assertEqual(schema["function"]["parameters"]["required"], ["query"])

    def test_unknown_tool_is_rejected(self):
        from cardboard_management.cardboard_management.api.ai_semantic import SemanticError
        with self.assertRaises(SemanticError):
            self.tools.execute_tool("get_supplier_statement", {})

    def test_execute_tool_forces_the_tool_domain(self):
        executed = {}

        class DummyEngine:
            @staticmethod
            def execute_query(query):
                executed.update(query)
                return {"status": "ok", "facts": [], "records": [], "disambiguation": []}

        original = self.tools._engine_execute_query
        self.tools._engine_execute_query = DummyEngine.execute_query
        try:
            self.tools.execute_tool("query_supplies", {"query": {"operation": "list", "limit": 2}})
        finally:
            self.tools._engine_execute_query = original
        self.assertEqual(executed.get("domain"), "supplies")
        self.assertEqual(executed.get("version"), "1")


if __name__ == "__main__":
    unittest.main()
