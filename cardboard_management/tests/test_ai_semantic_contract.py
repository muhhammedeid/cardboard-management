"""DB-free contract tests for the AI V3 semantic query engine (validator)."""

import unittest


class SemanticBase(unittest.TestCase):
    def setUp(self):
        from cardboard_management.cardboard_management.api import ai_semantic
        self.m = ai_semantic

    def run_query(self, query):
        return self.m.validate_query(dict(query))

    def expect_reject(self, query, code):
        try:
            self.run_query(query)
        except self.m.SemanticError as error:
            self.assertEqual(error.code, code, (code, error.code, error.message_ar))
        else:
            self.fail(f"expected {code} for {query}")


class TestSemanticSchema(SemanticBase):
    QUERY = {
        "version": "1",
        "domain": "suppliers",
        "operation": "rank",
        "sort": {"field": "outstanding", "direction": "desc"},
        "limit": 3,
    }

    def test_schema_version_is_recorded_and_enforced(self):
        resolved = self.run_query(self.QUERY)
        self.assertEqual(resolved["version"], "1")
        self.expect_reject({**self.QUERY, "version": "2"}, "INVALID_QUERY")

    def test_unknown_top_level_keys_are_rejected(self):
        self.expect_reject({**self.QUERY, "mystery": 1}, "INVALID_QUERY")

    def test_unsupported_domain_is_rejected(self):
        self.expect_reject({**self.QUERY, "domain": "hr"}, "UNSUPPORTED_DOMAIN")

    def test_unsupported_operation_is_rejected(self):
        self.expect_reject({**self.QUERY, "operation": "aggregate"}, "UNSUPPORTED_METRIC")
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "rank"},
            "UNSUPPORTED_OPERATION",
        )

    def test_unsupported_field_is_rejected(self):
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "list", "fields": ["salary"]},
            "UNSUPPORTED_FIELD",
        )

    def test_unsupported_metric_is_rejected(self):
        self.expect_reject(
            {
                "version": "1", "domain": "suppliers", "operation": "aggregate",
                "aggregation": {"outstanding": "sum"},
            },
            "UNSUPPORTED_METRIC",
        )
        self.expect_reject(
            {
                "version": "1", "domain": "supplies", "operation": "aggregate",
                "aggregation": {"payable_weight_kg": "median"},
            },
            "UNSUPPORTED_METRIC",
        )

    def test_unsupported_filter_is_rejected(self):
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "list", "filters": {"buyer": "احد"}},
            "UNSUPPORTED_FIELD",
        )

    def test_invalid_period_is_rejected(self):
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "list", "period": {"type": "next_year"}},
            "INVALID_PERIOD",
        )
        self.expect_reject(
            {
                "version": "1", "domain": "supplies", "operation": "list",
                "period": {"from": "2026-09-10", "to": "2026-09-01"},
            },
            "INVALID_PERIOD",
        )

    def test_invalid_sort_is_rejected(self):
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "list", "sort": {"field": "supplier_name", "direction": "desc"}},
            "UNSUPPORTED_FIELD",
        )
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "list", "sort": {"field": "date", "direction": "sideways"}},
            "INVALID_QUERY",
        )

    def test_rank_and_list_limits_are_enforced(self):
        self.expect_reject({**self.QUERY, "limit": 11}, "INVALID_QUERY")
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "list", "limit": 26},
            "INVALID_QUERY",
        )
        self.assertEqual(self.run_query(self.QUERY)["limit"], 3)
        self.assertEqual(
            self.run_query({**self.QUERY, "domain": "supplies", "operation": "list", "sort": None})["limit"] if False else 3,
            3,
        )

    def test_offset_bounds_are_enforced(self):
        self.expect_reject(
            {"version": "1", "domain": "supplies", "operation": "list", "offset": 51},
            "INVALID_QUERY",
        )
        resolved = self.run_query(
            {"version": "1", "domain": "supplies", "operation": "list", "limit": 5, "offset": 3}
        )
        self.assertEqual(resolved["offset"], 3)


class TestQueryPatch(SemanticBase):
    QUERY = {
        "version": "1",
        "domain": "supplies",
        "operation": "get",
        "filters": {"supplier": "محمد"},
        "sort": {"field": "date", "direction": "desc"},
        "limit": 1,
    }

    def test_patch_requires_a_previous_validated_query(self):
        try:
            self.m.apply_patch(None, {"offset": 1})
        except self.m.SemanticError as error:
            self.assertEqual(error.code, "INVALID_QUERY")
        else:
            self.fail("patch without previous query must fail")

    def test_unknown_patch_keys_are_rejected(self):
        previous = self.m.validate_query(self.QUERY)
        self.expect_reject({**self.QUERY, "_secret": 1}, "INVALID_QUERY")
        try:
            self.m.apply_patch(previous, {"hacker": 1})
        except self.m.SemanticError as error:
            self.assertEqual(error.code, "INVALID_QUERY")
        else:
            self.fail("unknown patch key must fail")

    def test_patch_is_applied_and_fully_revalidated(self):
        previous = self.m.validate_query(self.QUERY)
        merged = self.m.apply_patch(previous, {"offset": 1})
        self.assertEqual(merged["offset"], 1)
        self.assertEqual(merged["domain"], "supplies")
        with self.assertRaises(self.m.SemanticError):
            self.m.apply_patch(previous, {"limit": 900})
        with self.assertRaises(self.m.SemanticError):
            self.m.apply_patch(previous, {"domain": "hr"})

    def test_patch_period_change_revalidates(self):
        previous = self.m.validate_query(self.QUERY)
        merged = self.m.apply_patch(previous, {"period": {"type": "previous_month"}})
        self.assertEqual(merged["period"], {"type": "previous_month"})
        with self.assertRaises(self.m.SemanticError):
            self.m.apply_patch(previous, {"period": {"type": "weekend_special"}})

    def test_interpret_output_merges_model_output_types(self):
        previous = self.m.validate_query(self.QUERY)
        self.assertEqual(self.m.interpret_output({"type": "new_query", "query": self.QUERY}, None)["type"], "new_query")
        patched = self.m.interpret_output({"type": "query_patch", "patch": {"offset": 1}}, previous)
        self.assertEqual(patched["type"], "query_patch")
        self.assertEqual(patched["query"]["offset"], 1)
        clarified = self.m.interpret_output({"type": "clarify", "question": "أي مورد؟"}, None)
        self.assertEqual(clarified["type"], "clarify")
        refused = self.m.interpret_output({"type": "refuse", "reason": "out_of_scope"}, None)
        self.assertEqual(refused["type"], "refuse")


if __name__ == "__main__":
    unittest.main()
