from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase

from cardboard_management import dashboard as dashboard_service
from cardboard_management.dashboard import get_chart_data, get_metric_value


class TestCardboardDashboardMetrics(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.supply_names = []
		self.expense_names = []
		self.item_names = []
		self.bin_names = []
		self.purchase_invoice_names = []
		self.payment_entry_names = []
		self.payment_ledger_names = []
		settings = frappe.get_single("Cardboard Dashboard Settings")
		self.company = settings.company
		self.item_group = settings.cardboard_item_group
		self.warehouse = frappe.db.get_value(
			"Warehouse", {"company": self.company, "is_group": 0, "disabled": 0}, "name"
		)
		other_company = frappe.db.get_value("Company", {"name": ["!=", self.company]}, "name")
		self.other_warehouse = frappe.db.get_value(
			"Warehouse", {"company": other_company, "is_group": 0, "disabled": 0}, "name"
		)
		self.other_company = other_company
		self.assertTrue(self.company)
		self.assertTrue(self.item_group)
		self.assertTrue(self.warehouse)
		self.assertTrue(self.other_warehouse)

	def tearDown(self):
		if self.supply_names:
			frappe.db.delete("Cardboard Supply", {"name": ["in", self.supply_names]})
		if self.expense_names:
			frappe.db.delete("Quick Expense", {"name": ["in", self.expense_names]})
		if self.payment_entry_names:
			frappe.db.delete("Payment Entry Reference", {"parent": ["in", self.payment_entry_names]})
			frappe.db.delete("Payment Entry", {"name": ["in", self.payment_entry_names]})
		if self.purchase_invoice_names:
			frappe.db.delete("Purchase Invoice", {"name": ["in", self.purchase_invoice_names]})
		if self.payment_ledger_names:
			frappe.db.delete("Payment Ledger Entry", {"name": ["in", self.payment_ledger_names]})
		if self.bin_names:
			frappe.db.delete("Bin", {"name": ["in", self.bin_names]})
		if self.item_names:
			frappe.db.delete("Item", {"name": ["in", self.item_names]})
		super().tearDown()

	def insert_supply(self, posting_date, weight, amount, docstatus=1, warehouse=None, item="_Test Item", supplier="_Test Supplier"):
		name = f"CM-DASH-{frappe.generate_hash(length=10)}"
		frappe.db.sql(
			"""insert into `tabCardboard Supply`
				(name, creation, modified, modified_by, owner, docstatus,
				 posting_date, supplier, item, warehouse, gross_weight,
				 tare_weight, net_weight, payable_weight, rate_per_kg, total_amount)
			values (%s, now(), now(), 'Administrator', 'Administrator', %s,
				%s, %s, %s, %s, %s, 0, %s, %s, 1, %s)""",
			(
				name,
				docstatus,
				posting_date,
				supplier,
				item,
				warehouse or self.warehouse,
				weight,
				weight,
				weight,
				amount,
			),
		)
		self.supply_names.append(name)
		return name

	def insert_expense(self, posting_date, amount, docstatus=1, company=None):
		name = f"CM-DASH-QE-{frappe.generate_hash(length=10)}"
		frappe.db.sql(
			"""insert into `tabQuick Expense`
				(name, creation, modified, modified_by, owner, docstatus,
				 posting_date, company, expense_account, payment_account, amount)
			values (%s, now(), now(), 'Administrator', 'Administrator', %s,
				%s, %s, '_Test Expense', '_Test Cash', %s)""",
			(name, docstatus, posting_date, company or self.company, amount),
		)
		self.expense_names.append(name)
		return name

	def insert_stock(self, item_group, warehouse, quantity):
		item = f"CM-DASH-ITEM-{frappe.generate_hash(length=8)}"
		bin_name = f"CM-DASH-BIN-{frappe.generate_hash(length=8)}"
		frappe.db.sql(
			"""insert into `tabItem`
				(name, creation, modified, modified_by, owner, docstatus,
				 item_code, item_name, item_group, stock_uom, is_stock_item, disabled)
			values (%s, now(), now(), 'Administrator', 'Administrator', 0,
				%s, %s, %s, 'Kg', 1, 0)""",
			(item, item, item, item_group),
		)
		frappe.db.sql(
			"""insert into `tabBin`
				(name, creation, modified, modified_by, owner, docstatus,
				 item_code, warehouse, actual_qty)
			values (%s, now(), now(), 'Administrator', 'Administrator', 0,
				%s, %s, %s)""",
			(bin_name, item, warehouse, quantity),
		)
		self.item_names.append(item)
		self.bin_names.append(bin_name)
		return item

	def insert_supplier_payment(
		self,
		posting_date,
		allocated_amount,
		docstatus=1,
		company=None,
		payment_type="Pay",
		party_type="Supplier",
		is_cardboard_purchase=True,
	):
		company = company or self.company
		invoice = f"CM-DASH-PI-{frappe.generate_hash(length=8)}"
		payment = f"CM-DASH-PE-{frappe.generate_hash(length=8)}"
		reference = f"CM-DASH-PER-{frappe.generate_hash(length=8)}"
		frappe.db.sql(
			"""insert into `tabPurchase Invoice`
				(name, creation, modified, modified_by, owner, docstatus,
				 posting_date, company, supplier, custom_cardboard_supply)
			values (%s, now(), now(), 'Administrator', 'Administrator', 1,
				%s, %s, '_Test Supplier', %s)""",
			(invoice, posting_date, company, invoice if is_cardboard_purchase else None),
		)
		frappe.db.sql(
			"""insert into `tabPayment Entry`
				(name, creation, modified, modified_by, owner, docstatus,
				 posting_date, company, payment_type, party_type, party,
				 paid_amount, received_amount, unallocated_amount)
			values (%s, now(), now(), 'Administrator', 'Administrator', %s,
				%s, %s, %s, %s, '_Test Supplier', %s, %s, 0)""",
			(payment, docstatus, posting_date, company, payment_type, party_type,
			 allocated_amount, allocated_amount),
		)
		frappe.db.sql(
			"""insert into `tabPayment Entry Reference`
				(name, creation, modified, modified_by, owner, docstatus,
				 parent, parentfield, parenttype, idx, reference_doctype,
				 reference_name, allocated_amount)
			values (%s, now(), now(), 'Administrator', 'Administrator', %s,
				%s, 'references', 'Payment Entry', 1, 'Purchase Invoice', %s, %s)""",
			(reference, docstatus, payment, invoice, allocated_amount),
		)
		self.purchase_invoice_names.append(invoice)
		self.payment_entry_names.append(payment)

	def insert_payment_ledger_amount(self, amount, company=None, party="_Test Supplier", delinked=0):
		name = f"CM-DASH-PLE-{frappe.generate_hash(length=8)}"
		frappe.db.sql(
			"""insert into `tabPayment Ledger Entry`
				(name, creation, modified, modified_by, owner, docstatus,
				 posting_date, company, account_type, party_type, party,
				 account, voucher_type, voucher_no, against_voucher_type,
				 against_voucher_no, amount, amount_in_account_currency,
				 account_currency, delinked)
			values (%s, now(), now(), 'Administrator', 'Administrator', 0,
				'2026-08-15', %s, 'Payable', 'Supplier', %s,
				'_Test Payable', 'Purchase Invoice', %s, 'Purchase Invoice',
				%s, %s, %s, 'EGP', %s)""",
			(name, company or self.company, party, name, name, amount, amount, delinked),
		)
		self.payment_ledger_names.append(name)

	def test_today_supply_weight_is_correct(self):
		day = date(2026, 8, 15)
		self.insert_supply(day, 125.5, 900)
		self.insert_supply(day, 40, 200, docstatus=0)
		self.insert_supply(day, 55, 300, docstatus=2)
		self.insert_supply(day, 900, 8000, warehouse=self.other_warehouse)
		self.assertEqual(get_metric_value("today_supply_weight", day), 125.5)

	def test_today_purchase_amount_is_correct(self):
		day = date(2026, 8, 15)
		self.insert_supply(day, 100, 875.25)
		self.insert_supply(date(2026, 8, 14), 100, 700)
		self.insert_supply(day, 100, 999, warehouse=self.other_warehouse)
		self.assertEqual(get_metric_value("today_purchase_amount", day), 875.25)

	def test_today_expense_amount_is_correct(self):
		day = date(2026, 8, 15)
		self.insert_expense(day, 210.75)
		self.insert_expense(date(2026, 8, 14), 100)
		self.insert_expense(day, 999, company=self.other_company)
		self.assertEqual(get_metric_value("today_expenses", day), 210.75)

	def test_month_supply_weight_is_correct(self):
		day = date(2026, 8, 15)
		self.insert_supply(date(2026, 8, 1), 100, 500)
		self.insert_supply(date(2026, 8, 31), 250, 900)
		self.insert_supply(date(2026, 7, 31), 800, 1000)
		self.assertEqual(get_metric_value("month_purchased_weight", day), 350)

	def test_month_purchase_cost_is_correct(self):
		day = date(2026, 8, 15)
		self.insert_supply(date(2026, 8, 1), 100, 500.5)
		self.insert_supply(date(2026, 8, 31), 250, 900.25)
		self.insert_supply(date(2026, 9, 1), 800, 1000)
		self.assertEqual(get_metric_value("month_purchase_cost", day), 1400.75)

	def test_month_expenses_are_correct(self):
		day = date(2026, 8, 15)
		self.insert_expense(date(2026, 8, 1), 75.25)
		self.insert_expense(date(2026, 8, 31), 124.75)
		self.insert_expense(date(2026, 7, 31), 500)
		self.assertEqual(get_metric_value("month_expenses", day), 200)

	def test_cancelled_supplies_are_excluded(self):
		day = date(2026, 8, 15)
		self.insert_supply(day, 40, 100)
		self.insert_supply(day, 600, 900, docstatus=2)
		self.assertEqual(get_metric_value("today_supply_weight", day), 40)
		self.assertEqual(get_metric_value("today_purchase_amount", day), 100)

	def test_cancelled_expenses_are_excluded(self):
		day = date(2026, 8, 15)
		self.insert_expense(day, 60)
		self.insert_expense(day, 700, docstatus=2)
		self.assertEqual(get_metric_value("today_expenses", day), 60)

	def test_current_stock_uses_bin_and_cardboard_item_scope(self):
		baseline = get_metric_value("current_stock_weight", date(2026, 8, 15))
		other_group = frappe.db.get_value(
			"Item Group", {"name": ["!=", self.item_group], "is_group": 0}, "name"
		)
		self.insert_stock(self.item_group, self.warehouse, 120.5)
		self.insert_stock(other_group, self.warehouse, 900)
		self.insert_stock(self.item_group, self.other_warehouse, 700)
		self.assertEqual(
			get_metric_value("current_stock_weight", date(2026, 8, 15)), baseline + 120.5
		)

	def test_supplier_payments_are_allocated_cardboard_purchases_only(self):
		day = date(2026, 8, 15)
		self.insert_supplier_payment(day, 300)
		self.insert_supplier_payment(date(2026, 8, 1), 50)
		self.insert_supplier_payment(day, 700, docstatus=0)
		self.insert_supplier_payment(day, 800, payment_type="Receive")
		self.insert_supplier_payment(day, 900, party_type="Customer")
		self.insert_supplier_payment(day, 1000, is_cardboard_purchase=False)
		self.insert_supplier_payment(day, 1100, company=self.other_company)
		self.assertEqual(get_metric_value("today_supplier_payments", day), 300)
		self.assertEqual(get_metric_value("month_supplier_payments", day), 350)

	def test_supplier_outstanding_uses_payment_ledger_state(self):
		self.insert_payment_ledger_amount(500, party="CM Dashboard Supplier A")
		self.insert_payment_ledger_amount(-125, party="CM Dashboard Supplier A")
		self.insert_payment_ledger_amount(75, party="CM Dashboard Supplier B")
		self.insert_payment_ledger_amount(-100, party="CM Dashboard Supplier Advance")
		self.insert_payment_ledger_amount(900, company=self.other_company)
		self.insert_payment_ledger_amount(1000, delinked=1)
		self.assertEqual(get_metric_value("supplier_outstanding", date(2026, 8, 15)), 450)

	def test_daily_supplied_weight_chart_aggregates_last_30_days(self):
		day = date(2026, 8, 30)
		self.insert_supply(date(2026, 8, 1), 10, 100)
		self.insert_supply(date(2026, 8, 15), 20, 200)
		self.insert_supply(date(2026, 8, 15), 5, 50)
		self.insert_supply(date(2026, 7, 31), 999, 999)
		chart = get_chart_data("daily_supplied_weight", day)
		self.assertEqual(len(chart["labels"]), 30)
		self.assertEqual(chart["labels"][0], "2026-08-01")
		self.assertEqual(chart["labels"][-1], "2026-08-30")
		self.assertEqual(chart["datasets"][0]["values"][0], 10)
		self.assertEqual(chart["datasets"][0]["values"][14], 25)

	def test_purchases_by_type_chart_respects_item_scope(self):
		day = date(2026, 8, 15)
		other_group = frappe.db.get_value(
			"Item Group", {"name": ["!=", self.item_group], "is_group": 0}, "name"
		)
		cardboard_item = self.insert_stock(self.item_group, self.warehouse, 0)
		non_cardboard_item = self.insert_stock(other_group, self.warehouse, 0)
		self.insert_supply(day, 75, 100, item=cardboard_item)
		self.insert_supply(day, 25, 50, item=cardboard_item)
		self.insert_supply(day, 1000, 5000, item=non_cardboard_item)
		chart = get_chart_data("purchases_by_type", day)
		self.assertEqual(chart["labels"], [cardboard_item])
		self.assertEqual(chart["datasets"][0]["values"], [100])

	def test_top_suppliers_chart_is_aggregated_sorted_and_limited(self):
		day = date(2026, 8, 15)
		for index in range(12):
			self.insert_supply(day, index + 1, 10, supplier=f"CM Supplier {index:02d}")
		self.insert_supply(day, 1000, 10, warehouse=self.other_warehouse, supplier="Other Company")
		chart = get_chart_data("top_suppliers", day)
		self.assertEqual(len(chart["labels"]), 10)
		self.assertEqual(chart["labels"][0], "CM Supplier 11")
		self.assertEqual(chart["datasets"][0]["values"][0], 12)
		self.assertNotIn("CM Supplier 00", chart["labels"])

	def test_supplier_outstanding_chart_uses_current_payment_ledger(self):
		day = date(2026, 8, 15)
		self.insert_payment_ledger_amount(400, party="CM Outstanding A")
		self.insert_payment_ledger_amount(-50, party="CM Outstanding A")
		self.insert_payment_ledger_amount(125, party="CM Outstanding B")
		self.insert_payment_ledger_amount(-80, party="CM Advance")
		self.insert_payment_ledger_amount(900, company=self.other_company, party="Other Company")
		chart = get_chart_data("supplier_outstanding", day)
		self.assertEqual(chart["labels"], ["CM Outstanding A", "CM Outstanding B"])
		self.assertEqual(chart["datasets"][0]["values"], [350, 125])

	def test_number_card_endpoints_return_native_widget_payloads(self):
		currency_methods = {
			"today_purchase_amount",
			"today_supplier_payments",
			"today_expenses",
			"supplier_outstanding",
			"this_month_purchase_cost",
			"this_month_expenses",
			"this_month_paid_to_suppliers",
		}
		methods = [
			"today_supplies_weight",
			"today_purchase_amount",
			"today_supplier_payments",
			"today_expenses",
			"current_stock_weight",
			"supplier_outstanding",
			"this_month_purchased_weight",
			"this_month_purchase_cost",
			"this_month_expenses",
			"this_month_paid_to_suppliers",
		]
		for method_name in methods:
			payload = getattr(dashboard_service, method_name)()
			self.assertIn("value", payload)
			self.assertIn("route", payload)
			self.assertEqual(
				payload["fieldtype"], "Currency" if method_name in currency_methods else "Float"
			)
			if method_name in currency_methods:
				self.assertEqual(payload["options"], frappe.get_cached_value("Company", self.company, "default_currency"))
