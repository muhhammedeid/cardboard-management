import json
import unittest
from pathlib import Path


class TestCardboardSupplyTicketPrintFormatSource(unittest.TestCase):
	def test_ticket_definition_is_version_controlled_and_owned_by_app(self):
		path = (
			Path(__file__).resolve().parents[1]
			/ "cardboard_management"
			/ "print_format"
			/ "cardboard_supply_ticket"
			/ "cardboard_supply_ticket.json"
		)

		self.assertTrue(path.is_file())
		print_format = json.loads(path.read_text())
		self.assertEqual(print_format["doctype"], "Print Format")
		self.assertEqual(print_format["name"], "Cardboard Supply Ticket")
		self.assertEqual(print_format["doc_type"], "Cardboard Supply")
		self.assertEqual(print_format["module"], "Cardboard Management")
		self.assertEqual(print_format["standard"], "Yes")
		self.assertTrue(print_format["custom_format"])

	def test_ticket_template_declares_supplier_facing_business_semantics(self):
		path = (
			Path(__file__).resolve().parents[1]
			/ "cardboard_management"
			/ "print_format"
			/ "cardboard_supply_ticket"
			/ "cardboard_supply_ticket.json"
		)
		html = json.loads(path.read_text())["html"]

		for text in (
			"كارتة استلام توريدة",
			"Cardboard Supply Ticket",
			'dir="rtl"',
			'@page { size: A5',
			'data-ticket-field="net_weight"',
			'data-ticket-field="discount_weight"',
			'data-ticket-field="payable_weight"',
			'data-ticket-field="rate_per_kg"',
			'data-ticket-field="total_amount"',
			'data-ticket-field="invoice_total"',
			'data-ticket-field="paid_amount"',
			'data-ticket-field="outstanding_amount"',
			'doc.ticket_company_name',
			'doc.ticket_company_logo',
			'doc.ticket_currency',
			'doc.ticket_supplier_name',
			'doc.ticket_weight_uom',
			'display_payable_weight',
			'doc.get_formatted',
			'doc.integration_status',
		):
			with self.subTest(text=text):
				self.assertIn(text, html)

		self.assertNotIn("total_amount / doc.net_weight", html)
		self.assertNotIn("purchase_invoice.items", html)


	def test_controller_prepares_live_ticket_context_without_persistence(self):
		controller_path = (
			Path(__file__).resolve().parents[1]
			/ "cardboard_management"
			/ "doctype"
			/ "cardboard_supply"
			/ "cardboard_supply.py"
		)
		controller = controller_path.read_text()

		for text in (
			"def before_print(self, settings=None):",
			"self.refresh_payment_summary()",
			"self.display_payable_weight = self.get_display_payable_weight()",
			"self.set_ticket_print_context()",
			"self.ticket_company_name",
			"self.ticket_company_logo",
			"self.ticket_currency",
			"self.ticket_item_name",
			"frappe.db.get_value(\"Warehouse\", self.warehouse, \"company\")",
		):
			with self.subTest(text=text):
				self.assertIn(text, controller)


if __name__ == "__main__":
	unittest.main()
