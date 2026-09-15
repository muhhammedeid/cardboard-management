import json
import unittest
from pathlib import Path


class TestCardboardSupplyTicketPrintFormatSource(unittest.TestCase):
	"""The printed ticket is the operator's paper weighing slip, trimmed to what they print:
	item, supplier, driver, vehicle and notes, the two weights, the net weight, the price line,
	and from the purchase invoice only what is paid and what is left."""

	def setUp(self):
		self.path = (
			Path(__file__).resolve().parents[1]
			/ "cardboard_management"
			/ "print_format"
			/ "cardboard_supply_ticket"
			/ "cardboard_supply_ticket.json"
		)
		self.definition = json.loads(self.path.read_text(encoding="utf-8"))
		self.html = self.definition["html"]

	def test_ticket_definition_is_version_controlled_and_owned_by_app(self):
		self.assertTrue(self.path.is_file())
		self.assertEqual(self.definition["doctype"], "Print Format")
		self.assertEqual(self.definition["name"], "Cardboard Supply Ticket")
		self.assertEqual(self.definition["doc_type"], "Cardboard Supply")
		self.assertEqual(self.definition["module"], "Cardboard Management")
		self.assertEqual(self.definition["standard"], "Yes")
		self.assertTrue(self.definition["custom_format"])
		self.assertEqual(self.definition["print_format_type"], "Jinja")

	def test_ticket_prints_only_the_fields_the_operator_asked_for(self):
		for text in (
			'@page { size: A5',
			'dir="rtl"',
			"تذكرة الوزن رقم",
			"التاريخ",
			"المخزن",
			"الصنف",
			"العميل / المورد",
			"اسم السائق",
			"رقم السيارة",
			"ملاحظات",
			"الوزن الأول (القائم)",
			"الوزن الثاني (الفارغ)",
			"وقت الدخول",
			"وقت الخروج",
			"صافي الوزن",
			"الوزن المحتسب",
			"خصم الوزن",
			"سعر الكيلو",
			"الإجمالي",
			"المدفوع",
			"المتبقي",
			"القائم بالوزن",
		):
			with self.subTest(text=text):
				self.assertIn(text, self.html)

	def test_ticket_no_longer_prints_the_removed_capture_and_invoice_fields(self):
		for removed in (
			"نوع الحركة",
			"وارد",
			"نوع السيارة",
			"رقم إذن التسليم",
			"رقم المقطورة",
			"رقم الشحنة",
			"إجمالي الفاتورة",
			"حالة السداد",
			"العملة",
		):
			with self.subTest(removed=removed):
				self.assertNotIn(removed, self.html)

		# The settlement band keeps only what is paid and what is left.
		self.assertIn('data-ticket-field="paid_amount"', self.html)
		self.assertIn('data-ticket-field="outstanding_amount"', self.html)
		for gone in ("invoice_total", "payment_status", "currency"):
			with self.subTest(marker=gone):
				self.assertNotIn(f'data-ticket-field="{gone}"', self.html)

	def test_ticket_money_goes_through_the_cleaning_helper(self):
		# The site's stored EGP symbol is the malformed "£ or ج.م"; paper must never show it.
		self.assertIn('doc.ticket_money("total_amount")', self.html)
		self.assertIn('doc.ticket_money("rate_per_kg")', self.html)
		self.assertIn('doc.ticket_money("invoice_paid_amount")', self.html)
		self.assertIn('doc.ticket_money("purchase_invoice_outstanding")', self.html)
		self.assertNotIn("£ or", self.html)
		self.assertNotIn("doc.get_formatted(\"total_amount\")", self.html)

	def test_ticket_without_a_purchase_invoice_says_so_instead_of_printing_zeroes(self):
		self.assertIn('{% if doc.integration_status == "Integrated" and doc.purchase_invoice %}', self.html)
		self.assertIn("Not Integrated — No Purchase Invoice", self.html)

	def test_supply_controller_publishes_the_ticket_context(self):
		controller = (
			Path(__file__).resolve().parents[1]
			/ "cardboard_management"
			/ "doctype"
			/ "cardboard_supply"
			/ "cardboard_supply.py"
		).read_text(encoding="utf-8")
		for attribute in (
			"ticket_company_name",
			"ticket_company_phone",
			"ticket_company_description",
			"ticket_item_name",
			"ticket_supplier_name",
			"ticket_weight_uom",
			"ticket_prepared_by",
		):
			with self.subTest(attribute=attribute):
				self.assertIn(attribute, controller)
		self.assertIn("def ticket_money", controller)
		self.assertIn("MALFORMED_CURRENCY_PREFIXES", controller)


if __name__ == "__main__":
	unittest.main()
