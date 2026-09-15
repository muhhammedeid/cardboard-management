"""Database-free contracts for the real-mode gap repairs (Nova verification pass).

Covers three additive backend changes:
  * `sales.get_create_capabilities` — a create form needs a capability answer before
    any document exists (supply already had one).
  * `reporting.get_supplier_statement` — the timeline used to be unbounded.
  * Arabic coverage for the reporting date-range validation messages.
"""

import ast
import csv
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SALES_API = APP / "cardboard_management" / "api" / "sales.py"
REPORTING = APP / "reporting.py"
TRANSLATIONS = APP / "translations" / "ar.csv"

REQUIRED_TRANSLATIONS = {
    "To Date cannot be in the future": "لا يمكن أن يكون تاريخ النهاية في المستقبل",
    "From Date cannot be after To Date": "لا يمكن أن يكون تاريخ البداية بعد تاريخ النهاية",
    "Invalid reporting status: {0}": "حالة تقرير غير صحيحة: {0}",
    "Cardboard item is outside the configured reporting scope": "نوع الكرتون خارج نطاق التقارير المُهيّأ",
}


def _function_node(tree, name):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} is not defined at module level")


def _is_whitelisted(node):
    return any(
        isinstance(decorator, ast.Call) and getattr(decorator.func, "attr", "") == "whitelist"
        for decorator in node.decorator_list
    )


class TestSalesCreateCapabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SALES_API.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_exposes_a_whitelisted_create_capability_service(self):
        node = _function_node(self.tree, "get_create_capabilities")
        self.assertTrue(_is_whitelisted(node))
        self.assertEqual([arg.arg for arg in node.args.args], [])

    def test_mirrors_the_supply_capability_contract(self):
        node = _function_node(self.tree, "get_create_capabilities")
        returned = [
            child
            for child in ast.walk(node)
            if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict)
        ]
        self.assertTrue(returned, "the service must return a dict literal")
        keys = {key.value for key in returned[0].value.keys if isinstance(key, ast.Constant)}
        self.assertEqual(keys, {"can_create", "can_submit"})

    def test_answers_a_create_capability_question_before_any_document_exists(self):
        node = _function_node(self.tree, "get_create_capabilities")
        self.assertEqual([arg.arg for arg in node.args.args], [])
        self.assertNotIn("name", {arg.arg for arg in node.args.args})


class TestSupplierStatementWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = REPORTING.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        # `cint` mirrors frappe.utils.cint: None/"" collapse to 0.
        cls.namespace = {"cint": lambda value=0: int(value or 0)}
        for name in ("STATEMENT_PAGE_SIZE", "STATEMENT_MAX_PAGE_SIZE"):
            assignment = next(
                node
                for node in cls.tree.body
                if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name
            )
            cls.namespace[name] = ast.literal_eval(assignment.value)
        paginate = _function_node(cls.tree, "_paginate")
        exec(compile(ast.Module(body=[paginate], type_ignores=[]), "<_paginate>", "exec"), cls.namespace)

    def test_paginate_is_defined(self):
        self.assertIn("_paginate", self.namespace)

    def test_window_limits_are_sane(self):
        default = self.namespace["STATEMENT_PAGE_SIZE"]
        maximum = self.namespace["STATEMENT_MAX_PAGE_SIZE"]
        self.assertGreater(default, 0)
        self.assertGreaterEqual(maximum, default)
        self.assertLessEqual(maximum, 1000)

    def test_statement_accepts_a_page_window(self):
        node = _function_node(self.tree, "get_supplier_statement")
        names = [arg.arg for arg in node.args.args]
        self.assertEqual(names, ["supplier", "from_date", "to_date", "page", "page_size"])
        # Everything after `supplier` is defaulted, so an existing caller keeps working.
        defaulted = names[len(names) - len(node.args.defaults) :]
        self.assertEqual(defaulted, ["from_date", "to_date", "page", "page_size"])
        self.assertIsNone(node.args.defaults[-1].value)

    def test_statement_response_reports_the_window(self):
        node = _function_node(self.tree, "get_supplier_statement")
        returned = [child for child in ast.walk(node) if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict)]
        self.assertTrue(returned, "the statement must return a dict literal")
        keys = {key.value for key in returned[0].value.keys if isinstance(key, ast.Constant)}
        self.assertIn("entries", keys)
        self.assertIn("pagination", {getattr(value, "id", "") for value in returned[0].value.values})

    def test_window_is_bounded_and_reports_more(self):
        paginate = self.namespace["_paginate"]
        rows = list(range(1000))

        window, meta = paginate(rows)
        self.assertEqual(len(window), 200)
        self.assertEqual(meta["total"], 1000)
        self.assertTrue(meta["has_more"])

        window, meta = paginate(rows, page=5, page_size=200)
        self.assertEqual(meta["page"], 5)
        self.assertFalse(meta["has_more"])

    def test_absurd_page_sizes_are_clamped(self):
        paginate = self.namespace["_paginate"]

        window, meta = paginate(list(range(10_000)), page_size=100_000)
        self.assertEqual(meta["page_size"], 500)
        self.assertEqual(len(window), 500)

        window, meta = paginate(list(range(10)), page=0, page_size=0)
        self.assertEqual(meta["page"], 1)
        self.assertEqual(meta["page_size"], 200)

        window, meta = paginate([], page=3)
        self.assertEqual(window, [])
        self.assertFalse(meta["has_more"])

    def test_statement_totals_declare_submitted_only(self):
        node = _function_node(self.tree, "get_supplier_summary")
        returned = [child for child in ast.walk(node) if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict)]
        keys = {key.value for key in returned[0].value.keys if isinstance(key, ast.Constant)}
        self.assertIn("submitted_only", keys)


class TestReportingArabicCoverage(unittest.TestCase):
    def test_reporting_validation_messages_are_translated(self):
        translated = {}
        with TRANSLATIONS.open(encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if len(row) >= 2 and row[0].strip():
                    translated[row[0].strip()] = row[1].strip()

        missing = {
            english: arabic
            for english, arabic in REQUIRED_TRANSLATIONS.items()
            if translated.get(english, "") != arabic
        }
        self.assertEqual(missing, {})

    def test_every_reporting_message_has_an_arabic_entry(self):
        import re

        source = REPORTING.read_text(encoding="utf-8")
        messages = set(re.findall(r'_\(\s*"([^"]+)"', source))
        translated = set()
        with TRANSLATIONS.open(encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if row and row[0].strip():
                    translated.add(row[0].strip())

        self.assertEqual(sorted(messages - translated), [])


class TestTranslationHelperIsNeverShadowed(unittest.TestCase):
	"""`from frappe import _` is the operator-message helper; rebinding it to a
	throwaway inside a function makes the very next `_("…")` call raise
	`TypeError: 'list' object is not callable` instead of explaining the rejection.
	Found live: `create_supply` answered a stray field with that TypeError."""

	API_DIR = APP / "cardboard_management" / "api"

	def test_api_modules_never_rebind_the_translation_helper(self):
		offenders = []
		for path in sorted(self.API_DIR.glob("*.py")):
			tree = ast.parse(path.read_text(encoding="utf-8"))
			for node in ast.walk(tree):
				for assignment in [n for n in ast.walk(node) if isinstance(n, ast.Assign)]:
					for target in assignment.targets:
						if isinstance(target, ast.Name) and target.id == "_":
							offenders.append(f"{path.name}:{assignment.lineno}")
				for target in [n for n in ast.walk(node) if isinstance(n, ast.Tuple)]:
					for element in target.elts:
						if isinstance(element, ast.Name) and element.id == "_":
							offenders.append(f"{path.name}:{element.lineno}")

		self.assertEqual(offenders, [], "the translation helper must never be rebound")

	def test_supply_rejects_unknown_fields_without_crashing(self):
		source = (self.API_DIR / "supply.py").read_text(encoding="utf-8")
		self.assertIn('_("Unsupported Supply fields: {0}")', source)
		self.assertIn("settings, _scope = _settings_and_scope()", source)


if __name__ == "__main__":
    unittest.main()
