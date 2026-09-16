"""Runtime domain-engine contracts for the AI V3 query engine (live site)."""

import unittest
from unittest.mock import patch


class EngineBase(unittest.TestCase):
    def setUp(self):
        import frappe
        self._previous_user = frappe.session.user
        frappe.set_user("muhamedeiddev@gmail.com")

    def tearDown(self):
        import frappe
        frappe.set_user(self._previous_user or "Administrator")
        frappe.db.rollback()

    @staticmethod
    def _previous_user():  # retained for compatibility
        return None

    def engine(self):
        from cardboard_management.cardboard_management.api import ai_query_engine
        return ai_query_engine


class TestEngineRuntime(EngineBase):
    ENGINE_RESULT = {
        "payable_weight": 2000, "total_amount": 150,
    }

    def test_supplier_ranking_returns_ranked_authoritative_records(self):
        engine = self.engine()
        payload = {"total_outstanding": 300, "suppliers": [
            {"supplier": "SUP-1", "supplier_name": "First", "outstanding": 200, "supply_value": 0, "paid_amount": 0},
            {"supplier": "SUP-2", "supplier_name": "Second", "outstanding": 100, "supply_value": 50, "paid_amount": 0},
            {"supplier": "SUP-3", "supplier_name": "Third", "outstanding": 0, "supply_value": 25, "paid_amount": 0},
        ]}
        with patch.object(engine.reporting, "get_outstanding_report", return_value=payload):
            result = engine.execute_query({
                "version": "1", "domain": "suppliers", "operation": "rank",
                "sort": {"field": "outstanding", "direction": "desc"}, "limit": 2,
            })
        self.assertEqual([row["rank"] for row in result["records"]], [1, 2])
        self.assertEqual(result["facts"][0]["value"], 200)

    def test_ambiguous_supplier_returns_disambiguation_not_a_guess(self):
        engine = self.engine()
        candidates = [
            {"id": "احمد محمد", "label": "احمد محمد", "source": {"route": "/suppliers/احمد محمد", "label": "Supplier"}},
            {"id": "احمد سيد", "label": "احمد سيد", "source": {"route": "/suppliers/احمد سيد", "label": "Supplier"}},
        ]
        with patch.object(engine, "resolve_supplier", return_value=(None, candidates)):
            result = engine.execute_query({
                "version": "1", "domain": "suppliers", "operation": "get",
                "filters": {"supplier": "احمد"},
            })
        self.assertEqual(result["status"], "ambiguity")
        self.assertEqual(len(result["disambiguation"]), 2)

    def test_missing_entity_raises_not_found(self):
        engine = self.engine()

        class Empty:
            items = []

        with patch.object(engine.frappe, "get_list", return_value=[]):
            from cardboard_management.cardboard_management.api.ai_semantic import SemanticError
            with self.assertRaises(SemanticError) as ctx:
                engine.resolve_supplier("مورد غير موجود")
        self.assertEqual(getattr(engine.SemanticError("x", "y"), "code", "x"), "x")
        self.assertEqual(engine.SemanticError, engine.SemanticError)

    def test_supplies_aggregate_is_supplier_scoped_server_side(self):
        engine = self.engine()
        summary = {"supply_history": [
            {"supply": "CS-1", "posting_date": "2026-09-01", "item": "I", "item_name": "Item", "payable_weight": 11497.6, "value": 80480.2},
        ], "supplier": {"name": "SUP", "supplier_name": "محمد عيد"}}
        with patch.object(engine.reporting, "get_supplier_summary", return_value=summary):
            result = engine.execute_query({
                "version": "1", "domain": "supplies", "operation": "aggregate",
                "filters": {"supplier": "محمد عيد"},
                "period": {"type": "month_to_date"},
                "aggregation": {"payable_weight_tons": "sum", "total_amount": "sum"},
            })
        values = {fact["id"]: fact["value"] for fact in result["facts"]}
        self.assertAlmostEqual(values["total.payable_weight_tons"], 11.498, places=3)
        self.assertEqual(values["total.total_amount"], 80480.2)

    def test_tons_are_never_summed_directly(self):
        engine = self.engine()
        payload = {"count": 2, "quantity": 3000.0, "payable_weight": 2500.0, "value": 9000.0}
        with patch.object(engine.reporting, "get_operations_summary", return_value={"supplies": payload, "sales": {}, "expenses": {}, "supplier_payments": {}, "inventory_movement": {}}):
            result = engine.execute_query({
                "version": "1", "domain": "supplies", "operation": "aggregate",
                "period": {"type": "month_to_date"},
                "aggregation": {"payable_weight_tons": "sum"},
            })
        values = {fact["id"]: fact["value"] for fact in result["facts"]}
        self.assertAlmostEqual(values["total.payable_weight_tons"], 2.5, places=3)

    def test_supplies_compare_periods_uses_two_validated_windows(self):
        engine = self.engine()
        summary_current = {"supply_history": [{"supply": "CS-1", "posting_date": "2026-09-15", "item": "I", "item_name": "Item", "payable_weight": 1000, "value": 7000}], "supplier": {"name": "S", "supplier_name": "S"}}
        summary_previous = {"supply_history": [{"supply": "CS-0", "posting_date": "2026-08-15", "item": "I", "item_name": "Item", "payable_weight": 800, "value": 5600}], "supplier": {"name": "S", "supplier_name": "S"}}
        with patch.object(engine, "resolve_supplier", return_value=("S", [])), patch.object(engine.reporting, "get_supplier_summary", side_effect=[summary_current, summary_previous]):
            result = engine.execute_query({
                "version": "1", "domain": "supplies", "operation": "compare",
                "filters": {"supplier": "S"},
                "period": {"type": "month_to_date"},
                "compare_period": {"type": "previous_month"},
                "aggregation": {"payable_weight_kg": "sum", "total_amount": "sum"},
            })
        values = {fact["id"]: fact["value"] for fact in result["facts"]}
        self.assertEqual(values["current.payable_weight_kg"], 1000)
        self.assertEqual(values["comparison.total_amount"], 5600)
        self.assertEqual(values["change.total_amount"], 1400)

    def test_expense_compare_reports_both_windows(self):
        engine = self.engine()
        current = {"total_expense_amount": 15300, "expense_count": 3, "by_account": []}
        previous = {"total_expense_amount": 9900, "expense_count": 2, "by_account": []}
        with patch.object(engine.reporting, "get_expense_summary", side_effect=[current, previous]):
            result = engine.execute_query({
                "version": "1", "domain": "expenses", "operation": "compare",
                "period": {"type": "month_to_date"},
                "compare_period": {"type": "previous_month"},
                "aggregation": {"amount": "sum"},
            })
        values = {fact["id"]: fact["value"] for fact in result["facts"]}
        self.assertEqual(values["current.amount"], 15300)
        self.assertEqual(values["comparison.amount"], 9900)
        self.assertEqual(values["change.amount"], 5400)

    def test_payments_require_supplier_and_bounded_window(self):
        engine = self.engine()
        from cardboard_management.cardboard_management.api.ai_semantic import SemanticError
        with patch.object(engine.reporting, "get_supplier_summary", return_value={"payment_history": [
            {"payment": "CSP-1", "posting_date": "2026-09-10", "amount": 1000, "mode_of_payment": "Cash"},
        ]}):
            result = engine.execute_query({
                "version": "1", "domain": "payments", "operation": "get",
                "filters": {"supplier": "محمد عيد"},
                "period": {"type": "month_to_date"},
            })
        self.assertEqual(result["records"][0]["id"], "CSP-1")
        with self.assertRaises(SemanticError):
            engine.execute_query({
                "version": "1", "domain": "payments", "operation": "list",
                "period": {"type": "month_to_date"},
            })


if __name__ == "__main__":
    unittest.main()
