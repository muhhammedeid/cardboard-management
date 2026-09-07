from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, getdate, nowdate

from cardboard_management.cardboard_management.doctype.quick_expense.quick_expense import QuickExpense

WORKSPACE = (Path(__file__).resolve().parents[3] / "workspace" /
             "cardboard_management" / "cardboard_management.json")


class TestQuickExpense(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = None
		for name in frappe.get_all("Company", pluck="name"):
			expense_account = frappe.db.get_value(
				"Account",
				{"company": name, "root_type": "Expense", "is_group": 0, "disabled": 0},
				"name",
			)
			bank_account = frappe.db.get_value(
				"Account",
				{"company": name, "is_group": 0, "disabled": 0, "account_type": ("in", ("Cash", "Bank"))},
				"name",
			)
			if expense_account and bank_account:
				cls.company = name
				cls.expense_account = expense_account
				cls.bank_account = bank_account
				break
		if not cls.company:
			raise AssertionError(
				"Quick Expense tests require one company with an enabled non-group Expense "
				"account and Cash/Bank account"
			)
		cls.foreign_expense_account = frappe.db.get_value(
			"Account",
			{"company": ("!=", cls.company), "root_type": "Expense", "is_group": 0, "disabled": 0},
			"name",
		)
		cls.foreign_bank_account = frappe.db.get_value(
			"Account",
			{
				"company": ("!=", cls.company),
				"is_group": 0,
				"disabled": 0,
				"account_type": ("in", ("Cash", "Bank")),
			},
			"name",
		)

	def make_expense(self, **overrides):
		values = {
			"doctype": "Quick Expense",
			"posting_date": nowdate(),
			"company": self.company,
			"expense_account": self.expense_account,
			"amount": 100,
			"payment_account": self.bank_account,
		}
		values.update(overrides)
		return frappe.get_doc(values)

	def test_valid_expense_saves_and_submits(self):
		expense = self.make_expense(description="Transport for pickup run").insert()

		self.assertRegex(expense.name, rf"^QE-{getdate(expense.posting_date).year}-\d{{5}}$")
		self.assertEqual(expense.accounting_status, "Not Integrated")
		self.assertIsNone(expense.accounting_document)
		expense.submit()

		self.assertEqual(expense.docstatus, 1)
		self.assertTrue(expense.accounting_document)

	def test_zero_and_negative_amount_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_expense(amount=0).validate()
		with self.assertRaises(frappe.ValidationError):
			self.make_expense(amount=-25).validate()

	def test_mismatched_expense_account_company_rejected(self):
		if not self.foreign_expense_account:
			self.skipTest("Site has no second company with an expense account")
		with self.assertRaises(frappe.ValidationError):
			self.make_expense(expense_account=self.foreign_expense_account).validate()

	def test_mismatched_payment_account_company_rejected(self):
		if not self.foreign_bank_account:
			self.skipTest("Site has no second company with a Cash/Bank account")
		with self.assertRaises(frappe.ValidationError):
			self.make_expense(payment_account=self.foreign_bank_account).validate()

	def test_group_or_disabled_expense_account_rejected(self):
		group_account = frappe.db.get_value(
			"Account",
			{"company": self.company, "root_type": "Expense", "is_group": 1, "disabled": 0},
			"name",
		)
		if group_account:
			with self.assertRaises(frappe.ValidationError):
				self.make_expense(expense_account=group_account).validate()
		non_expense_account = frappe.db.get_value(
			"Account",
			{
				"company": self.company,
				"root_type": ("!=", "Expense"),
				"is_group": 0,
				"disabled": 0,
			},
			"name",
		)
		if non_expense_account:
			with self.assertRaises(frappe.ValidationError):
				self.make_expense(expense_account=non_expense_account).validate()

	def test_non_cash_bank_payment_account_rejected(self):
		other_account = frappe.db.get_value(
			"Account",
			{
				"company": self.company,
				"is_group": 0,
				"disabled": 0,
				"account_type": ("not in", ("Cash", "Bank")),
			},
			"name",
		)
		if not other_account:
			self.skipTest("Site has no non-cash/bank account on the target company")
		with self.assertRaises(frappe.ValidationError):
			self.make_expense(payment_account=other_account).validate()

	def test_accounts_must_match_company_currency(self):
		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		mismatched = frappe.db.get_value(
			"Account",
			{
				"company": self.company,
				"is_group": 0,
				"disabled": 0,
				"account_currency": ("!=", company_currency),
			},
			"name",
		)
		if not mismatched:
			self.skipTest("Site has no cross-currency account on the target company")
		with self.assertRaises(frappe.ValidationError):
			self.make_expense(payment_account=mismatched).validate()

	def test_reference_date_requires_reference_no(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_expense(reference_date=nowdate()).validate()

	def test_submit_creates_submitted_journal_entry(self):
		expense = self.make_expense(amount=350).insert()
		expense.submit()
		expense.onload()

		journal_entry = frappe.get_doc("Journal Entry", expense.accounting_document)
		self.assertEqual(journal_entry.doctype, "Journal Entry")
		self.assertEqual(journal_entry.docstatus, 1)
		self.assertEqual(journal_entry.company, self.company)
		self.assertEqual(getdate(journal_entry.posting_date), getdate(expense.posting_date))
		self.assertEqual(expense.accounting_status, "Integrated")

	def test_journal_entry_debits_expense_and_credits_payment_account(self):
		expense = self.make_expense(amount=350).insert()
		expense.submit()

		journal_entry = frappe.get_doc("Journal Entry", expense.accounting_document)
		expense_row = next(d for d in journal_entry.accounts if d.account == self.expense_account)
		payment_row = next(d for d in journal_entry.accounts if d.account == self.bank_account)
		self.assertEqual(len(journal_entry.accounts), 2)
		self.assertGreater(flt(expense_row.debit), 0)
		self.assertEqual(flt(expense_row.credit), 0)
		self.assertEqual(flt(payment_row.credit), 350)
		self.assertEqual(flt(payment_row.debit), 0)

	def test_journal_entry_preserves_exact_amount(self):
		expense = self.make_expense(amount=1234.5).insert()
		expense.submit()
		expense.reload()

		journal_entry = frappe.get_doc("Journal Entry", expense.accounting_document)
		self.assertEqual(journal_entry.total_debit, 1234.5)
		self.assertEqual(journal_entry.total_credit, 1234.5)
		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Journal Entry", "voucher_no": journal_entry.name},
			fields=["account", "debit", "credit"],
		)
		expense_gl = next(d for d in gl_entries if d.account == self.expense_account)
		payment_gl = next(d for d in gl_entries if d.account == self.bank_account)
		self.assertEqual(expense_gl.debit, 1234.5)
		self.assertEqual(payment_gl.credit, 1234.5)

	def test_journal_entry_references_quick_expense_and_remark(self):
		expense = self.make_expense(description="Loading help", amount=80).insert()
		expense.submit()

		journal_entry = frappe.get_doc("Journal Entry", expense.accounting_document)
		for row in journal_entry.accounts:
			self.assertEqual(row.reference_type, "Quick Expense")
			self.assertEqual(row.reference_name, expense.name)
		self.assertIn(expense.name, journal_entry.user_remark)

	def test_duplicate_submit_retry_reuses_same_journal_entry(self):
		expense = self.make_expense(amount=65).insert()
		expense.submit()
		first_name = expense.accounting_document

		retry = frappe.get_doc("Quick Expense", expense.name)
		retry.create_journal_entry()
		retry.reload()

		self.assertEqual(retry.accounting_document, first_name)
		self.assertEqual(
			frappe.db.count(
				"Journal Entry Account",
				{"reference_type": "Quick Expense", "reference_name": expense.name},
			),
			2,
		)
		self.assertEqual(
			frappe.get_value("Journal Entry", first_name, "docstatus"),
			1,
		)

	def test_cancel_reverses_gl_entries(self):
		expense = self.make_expense(amount=220).insert()
		expense.submit()
		journal_entry_name = expense.accounting_document

		expense.cancel()
		expense.onload()

		self.assertEqual(frappe.get_value("Quick Expense", expense.name, "docstatus"), 2)
		self.assertEqual(frappe.get_value("Journal Entry", journal_entry_name, "docstatus"), 2)
		self.assertEqual(expense.accounting_status, "Cancelled")
		gl_entries = frappe.get_all(
			"GL Entry",
			filters={"voucher_type": "Journal Entry", "voucher_no": journal_entry_name},
			fields=["is_cancelled", "debit", "credit"],
		)
		self.assertTrue(gl_entries)
		for gl_entry in gl_entries:
			self.assertEqual(gl_entry.is_cancelled, 1)

	def test_accounting_link_is_stored_and_status_reflects_linkage(self):
		expense = self.make_expense(amount=90).insert()
		expense.submit()
		expense.reload()
		expense.onload()

		self.assertEqual(
			frappe.get_value("Quick Expense", expense.name, "accounting_document"),
			expense.accounting_document,
		)
		self.assertEqual(expense.accounting_status, "Integrated")

		journal_entry = frappe.get_doc("Journal Entry", expense.accounting_document)
		self.assertEqual(journal_entry.company, self.company)
		self.assertEqual(len(journal_entry.accounts), 2)

	def test_workspaces_ship_expense_quick_links(self):
		import json

		self.assertTrue(WORKSPACE.is_file(), "Ship the workspace in the custom app")
		workspace = json.loads(WORKSPACE.read_text())
		shortcut_labels = [s["label"] for s in workspace["shortcuts"]]
		self.assertIn("New Expense", shortcut_labels)
		self.assertIn("Expenses", shortcut_labels)
		links = {link["label"]: link["link_to"] for link in workspace["links"] if link["type"] != "Card Break"}
		self.assertEqual(links["Quick Expense"], "Quick Expense")
		card_names = [link["label"] for link in workspace["links"] if link["type"] == "Card Break"]
		self.assertIn("Expenses", card_names)
		shortcut_names = [
			block["data"]["shortcut_name"] for block in json.loads(workspace["content"])
			if block["type"] == "shortcut"
		]
		self.assertIn("New Expense", shortcut_names)
		self.assertIn("Expenses", shortcut_names)
