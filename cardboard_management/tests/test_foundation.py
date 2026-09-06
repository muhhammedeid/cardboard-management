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

	def test_foundation_has_no_business_event_or_migration_hooks(self):
		for name in (
			"doc_events", "scheduler_events", "override_doctype_class",
			"override_whitelisted_methods", "fixtures", "before_install",
			"after_install", "before_migrate", "after_migrate",
		):
			with self.subTest(hook=name):
				self.assertFalse(getattr(hooks, name, None))
