"""Developer smoke verification: real ERP transactions, always rolled back."""
import frappe
from frappe.utils import nowdate


def verify_quick_expense_flows():
    results = []
    try:
        company = frappe.db.get_value(
            "Company",
            {
                "name": ("in", frappe.get_all("Company", pluck="name")),
            },
            "name",
        )
        # Pick the first company that has both an expense account and a cash/bank account.
        for candidate in frappe.get_all("Company", pluck="name"):
            expense_account = frappe.db.get_value(
                "Account",
                {"company": candidate, "root_type": "Expense", "is_group": 0, "disabled": 0},
                "name",
            )
            bank_account = frappe.db.get_value(
                "Account",
                {
                    "company": candidate,
                    "is_group": 0,
                    "disabled": 0,
                    "account_type": ("in", ("Cash", "Bank")),
                },
                "name",
            )
            if expense_account and bank_account:
                company, expense_account, payment_account = candidate, expense_account, bank_account
                break
        assert company and expense_account and payment_account

        for label, amount in (("submit", 250), ("retry", 250), ("cancel", 180)):
            expense = frappe.get_doc(
                dict(
                    doctype="Quick Expense",
                    posting_date=nowdate(),
                    company=company,
                    expense_account=expense_account,
                    amount=amount,
                    payment_account=payment_account,
                    description=f"P02-W02 smoke verification ({label})",
                )
            ).insert()
            expense.submit()
            expense.onload()
            journal_entry_name = expense.accounting_document
            journal_entry = frappe.get_doc("Journal Entry", journal_entry_name)
            assert journal_entry.docstatus == 1
            assert journal_entry.company == company
            expense_gl = frappe.get_all(
                "GL Entry",
                filters={"voucher_type": "Journal Entry", "voucher_no": journal_entry_name,
                         "account": expense_account},
                fields=["debit", "credit", "is_cancelled"],
            )
            payment_gl = frappe.get_all(
                "GL Entry",
                filters={"voucher_type": "Journal Entry", "voucher_no": journal_entry_name,
                         "account": payment_account},
                fields=["debit", "credit", "is_cancelled"],
            )
            assert len(expense_gl) == 1 and expense_gl[0]["debit"] == amount
            assert len(payment_gl) == 1 and payment_gl[0]["credit"] == amount
            row = dict(
                case=label, expense=expense.name, journal_entry=journal_entry_name,
                amount=amount, expense_debit=expense_gl[0]["debit"],
                payment_credit=payment_gl[0]["credit"],
                accounting_status=expense.accounting_status,
            )
            if label == "retry":
                # Duplicate submit path must reuse the same Journal Entry.
                before = frappe.db.count("Journal Entry")
                retry = frappe.get_doc("Quick Expense", expense.name)
                retry.create_journal_entry()
                assert retry.accounting_document == journal_entry_name
                assert frappe.db.count("Journal Entry") == before
                row["reused_entry"] = journal_entry_name
            if label == "cancel":
                expense.cancel()
                expense.onload()
                assert frappe.get_value("Journal Entry", journal_entry_name, "docstatus") == 2
                assert expense.accounting_status == "Cancelled"
                cancelled_gl = frappe.get_all(
                    "GL Entry",
                    filters={"voucher_type": "Journal Entry", "voucher_no": journal_entry_name},
                    fields=["is_cancelled"],
                )
                assert cancelled_gl and all(g["is_cancelled"] == 1 for g in cancelled_gl)
                row["gl_reversed"] = all(g["is_cancelled"] == 1 for g in cancelled_gl)
            results.append(row)
        return dict(results=results, persistence="All verification transactions rolled back")
    finally:
        frappe.db.rollback()
