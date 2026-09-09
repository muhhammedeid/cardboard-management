"""Read-only foundation checks, runnable without a site or database."""

import importlib
import unittest
from pathlib import Path

from cardboard_management import hooks


class TestFoundation(unittest.TestCase):
	def test_erpnext_is_required(self):
		self.assertIn("erpnext", getattr(hooks, "required_apps", []))

	def test_module_is_declared_and_importable(self):
		package = Path(hooks.__file__).parent
		self.assertEqual((package / "modules.txt").read_text().splitlines(), ["Cardboard Management"])
		self.assertIsNotNone(importlib.import_module("cardboard_management.cardboard_management"))

	def test_foundation_has_no_core_overrides_or_background_business_hooks(self):
		for name in (
			"doc_events",
			"scheduler_events",
			"override_doctype_class",
			"override_whitelisted_methods",
			"before_install",
			"before_migrate",
		):
			with self.subTest(hook=name):
				self.assertFalse(getattr(hooks, name, None))

	def test_navigation_fixtures_are_limited_to_unassigned_operator_configuration(self):
		self.assertEqual(hooks.fixtures, [
			{"doctype": "Role", "filters": [["name", "=", "Cardboard Operator"]]},
			{"doctype": "Module Profile", "filters": [["name", "=", "Cardboard Operator"]]},
		])

	def test_install_and_migrate_hooks_own_standard_schema_extensions(self):
		expected = "cardboard_management.setup.ensure_purchase_invoice_integration_schema"
		self.assertEqual(hooks.after_install, expected)
		self.assertEqual(hooks.after_migrate, expected)
