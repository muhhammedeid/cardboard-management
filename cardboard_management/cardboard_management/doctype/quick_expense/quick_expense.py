import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate


class QuickExpense(Document):
	# Operational cash/bank expense. All accounting lives in the linked standard
	# Journal Entry; this doctype never writes GL entries or balances itself.
	ACCOUNTING_STATUS_DRAFT = "Not Integrated"
	ACCOUNTING_STATUS_LINKED = "Integrated"
	ACCOUNTING_STATUS_CANCELLED = "Cancelled"

	def validate(self):
		self.validate_posting_date()
		self.set_missing_company_from_payment_accounts()
		self.validate_company_scope()
		self.validate_amount()
		self.validate_expense_account()
		self.validate_payment_account()
		self.validate_reference()
		self.refresh_accounting_summary()

	def validate_posting_date(self):
		self.posting_date = self.posting_date or nowdate()
		if getdate(self.posting_date) > getdate(nowdate()):
			frappe.throw(_("Posting Date cannot be in the future"))

	def validate_company_scope(self):
		company = frappe.db.get_single_value("Cardboard Dashboard Settings", "company")
		if not company or not frappe.db.exists("Company", company):
			frappe.throw(_("Configure Company in Cardboard Dashboard Settings before recording expenses"))
		if self.company and self.company != company:
			frappe.throw(_("Quick Expense company must match the configured Company"))
		self.company = company

	def onload(self):
		self.refresh_accounting_summary()

	def on_submit(self):
		self.create_journal_entry()

	def before_cancel(self):
		# Standard ERPNext controller pattern (cf. Journal Entry / Payment Entry):
		# ignore internal ledger backlinks so the linked Journal Entry's GL entries
		# do not block the operational document's own cancellation.
		self.ignore_linked_doctypes = (
			"GL Entry",
			"Payment Ledger Entry",
			"Repost Payment Ledger",
			"Repost Payment Ledger Items",
			"Repost Accounting Ledger",
			"Repost Accounting Ledger Items",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
			"Advance Payment Ledger Entry",
		)
		self.cancel_journal_entry()

	def set_missing_company_from_payment_accounts(self):
		if self.company:
			return
		for fieldname in ("expense_account", "payment_account"):
			if self.get(fieldname):
				self.company = frappe.db.get_value("Account", self.get(fieldname), "company")
				if self.company:
					break

	def validate_amount(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))

	def validate_expense_account(self):
		account = self._validated_account(
			self.expense_account,
			label=_("Expense Category"),
			root_type="Expense",
			cash_or_bank=False,
		)
		if account and account.company != self.company:
			frappe.throw(
				_("Expense Category {0} does not belong to Company {1}").format(
					frappe.bold(self.expense_account), frappe.bold(self.company)
				)
			)

	def validate_payment_account(self):
		account = self._validated_account(
			self.payment_account,
			label=_("Payment Account"),
			root_type=None,
			cash_or_bank=True,
		)
		if account and account.company != self.company:
			frappe.throw(
				_("Payment Account {0} does not belong to Company {1}").format(
					frappe.bold(self.payment_account), frappe.bold(self.company)
				)
			)

	def _validated_account(self, account_name, label, root_type, cash_or_bank):
		if not account_name:
			return None
		if not frappe.db.exists("Account", account_name):
			frappe.throw(_("{0} {1} does not exist").format(label, frappe.bold(account_name)))
		account = frappe.db.get_value(
			"Account",
			account_name,
			["name", "company", "root_type", "account_type", "is_group", "disabled", "account_currency"],
			as_dict=True,
		)
		if account.disabled:
			frappe.throw(_("{0} {1} is disabled").format(label, frappe.bold(account_name)))
		if account.is_group:
			frappe.throw(
				_("{0} {1} is a group account and cannot be used in transactions").format(
					label, frappe.bold(account_name)
				)
			)
		if root_type and account.root_type != root_type:
			frappe.throw(_("{0} {1} is not an expense account").format(label, frappe.bold(account_name)))
		if cash_or_bank and account.account_type not in ("Cash", "Bank"):
			frappe.throw(
				_("{0} {1} must be a Cash or Bank account").format(label, frappe.bold(account_name))
			)
		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		if account.account_currency != company_currency:
			frappe.throw(
				_(
					"{0} {1} currency {2} does not match the company currency {3}. "
					"Cross-currency expenses are not supported."
				).format(
					label, frappe.bold(account_name), account.account_currency, company_currency
				)
			)
		return account

	def validate_reference(self):
		if self.reference_date and not self.reference_no:
			frappe.throw(_("Reference No is required when a Reference Date is set"))

	def refresh_accounting_summary(self):
		self.accounting_status = self.ACCOUNTING_STATUS_DRAFT
		if not self.accounting_document:
			return
		if not frappe.db.exists("Journal Entry", self.accounting_document):
			return
		docstatus = frappe.db.get_value("Journal Entry", self.accounting_document, "docstatus")
		if docstatus == 1:
			self.accounting_status = self.ACCOUNTING_STATUS_LINKED
		elif docstatus == 2:
			self.accounting_status = self.ACCOUNTING_STATUS_CANCELLED

	def create_journal_entry(self):
		if self.docstatus != 1:
			frappe.throw(_("Quick Expense must be submitted before creating accounting"))
		self._lock_for_integration()
		existing_name = self._existing_journal_entry_name()
		if existing_name:
			return self._complete_existing_journal_entry(existing_name)
		journal_entry = self._build_journal_entry()
		journal_entry.insert()
		self._validate_journal_entry_mapping(journal_entry)
		journal_entry.submit()
		self._validate_journal_entry_mapping(journal_entry)
		self._set_journal_entry_link(journal_entry.name)
		return journal_entry

	def cancel_journal_entry(self):
		linked_name = self.accounting_document or self._existing_journal_entry_name()
		if not linked_name:
			frappe.throw(_("Quick Expense {0} has no linked Journal Entry").format(frappe.bold(self.name)))
		if not frappe.db.exists("Journal Entry", linked_name):
			frappe.throw(_("Linked Journal Entry {0} does not exist").format(frappe.bold(linked_name)))
		journal_entry = frappe.get_doc("Journal Entry", linked_name)
		self._validate_journal_entry_mapping(journal_entry)
		if journal_entry.docstatus == 0:
			frappe.throw(_("Linked Journal Entry must be submitted before cancelling Quick Expense"))
		if journal_entry.docstatus == 1:
			# The forward link from this Quick Expense to the Journal Entry is
			# intentional: the JE must cancel first while this document keeps its
			# reference.
			journal_entry.ignore_linked_doctypes = ("Quick Expense",)
			journal_entry.cancel()

	def _lock_for_integration(self):
		frappe.db.sql(
			"select name from `tabQuick Expense` where name = %s for update",
			(self.name,),
		)
		self.accounting_document = frappe.db.get_value(
			"Quick Expense", self.name, "accounting_document"
		)

	def _existing_journal_entry_name(self):
		if self.accounting_document:
			return self.accounting_document
		return frappe.db.get_value(
			"Journal Entry Account",
			{"reference_type": "Quick Expense", "reference_name": self.name},
			"parent",
		)

	def _complete_existing_journal_entry(self, journal_entry_name):
		if not frappe.db.exists("Journal Entry", journal_entry_name):
			frappe.throw(_("Linked Journal Entry {0} does not exist").format(frappe.bold(journal_entry_name)))
		journal_entry = frappe.get_doc("Journal Entry", journal_entry_name)
		self._validate_journal_entry_mapping(journal_entry)
		if journal_entry.docstatus == 0:
			journal_entry.submit()
		self._validate_journal_entry_mapping(journal_entry)
		self._set_journal_entry_link(journal_entry.name)
		return journal_entry

	def _build_journal_entry(self):
		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		expense_account_currency = frappe.get_cached_value(
			"Account", self.expense_account, "account_currency"
		)
		multi_currency = 1 if expense_account_currency != company_currency else 0
		amount = flt(self.amount)
		remarks = self._journal_entry_remark()
		journal_entry = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": self.company,
				"posting_date": self.posting_date,
				"voucher_type": "Journal Entry",
				"user_remark": remarks,
				"multi_currency": multi_currency,
				"cheque_no": self.reference_no or None,
				"cheque_date": self.reference_date or None,
				"accounts": [
					{
						"account": self.expense_account,
						"debit_in_account_currency": amount,
						"credit_in_account_currency": 0,
						"exchange_rate": 1,
						"account_currency": expense_account_currency,
						"user_remark": remarks,
						"reference_type": "Quick Expense",
						"reference_name": self.name,
					},
					{
						"account": self.payment_account,
						"debit_in_account_currency": 0,
						"credit_in_account_currency": amount,
						"exchange_rate": 1,
						"account_currency": company_currency,
						"user_remark": remarks,
						"reference_type": "Quick Expense",
						"reference_name": self.name,
					},
				],
			}
		)
		return journal_entry

	def _journal_entry_remark(self):
		parts = [f"Quick Expense {self.name}"]
		if self.description:
			parts.append(self.description)
		return " - ".join(parts)

	def _validate_journal_entry_mapping(self, journal_entry):
		if journal_entry.docstatus == 2:
			frappe.throw(_("Linked Journal Entry is cancelled; a duplicate will not be created"))
		if self.accounting_document and self.accounting_document != journal_entry.name:
			frappe.throw(_("Linked Journal Entry does not belong to Quick Expense"))
		if journal_entry.company != self.company or journal_entry.voucher_type != "Journal Entry":
			frappe.throw(_("Linked Journal Entry company does not match Quick Expense"))
		if getdate(journal_entry.posting_date) != getdate(self.posting_date):
			frappe.throw(_("Linked Journal Entry posting date does not match Quick Expense"))
		rows = journal_entry.get("accounts") or []
		if len(rows) != 2:
			frappe.throw(_("Linked Journal Entry must contain exactly two rows"))
		if any(row.reference_type != "Quick Expense" or row.reference_name != self.name for row in rows):
			frappe.throw(_("Linked Journal Entry does not belong to Quick Expense"))
		expense_row = next(
			(row for row in rows if row.account == self.expense_account and flt(row.debit) > 0 and not flt(row.credit)),
			None,
		)
		payment_row = next(
			(row for row in rows if row.account == self.payment_account and flt(row.credit) > 0 and not flt(row.debit)),
			None,
		)
		if not expense_row or flt(expense_row.debit) != flt(self.amount):
			frappe.throw(_("Linked Journal Entry expense row does not match Quick Expense"))
		if not payment_row or flt(payment_row.credit) != flt(self.amount):
			frappe.throw(_("Linked Journal Entry payment row does not match Quick Expense"))

	def _set_journal_entry_link(self, journal_entry_name):
		self.accounting_document = journal_entry_name
		self.db_set("accounting_document", journal_entry_name, update_modified=False)

	@frappe.whitelist()
	def make_journal_entry(self):
		return self.create_journal_entry()
