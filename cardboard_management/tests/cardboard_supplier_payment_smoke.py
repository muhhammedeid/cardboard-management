"""Developer smoke verification for P03-R02: real ERP transactions, always rolled back.

Runs against cardboard.localhost only via:
  bench --site cardboard.localhost execute \
    cardboard_management.tests.cardboard_supplier_payment_smoke.verify_supplier_payment_flows
"""
import frappe
from frappe.utils import flt, nowdate


def _make_purchase_invoice(supplier, company, posting_date=None, qty=10, rate=100):
	item = frappe.db.get_value(
		"Item", {"disabled": 0, "is_stock_item": 1, "stock_uom": "Kg"}, "name"
	) or frappe.db.get_value("Item", {"disabled": 0}, "name")
	warehouse = frappe.db.get_value(
		"Warehouse", {"company": company, "disabled": 0, "is_group": 0}, "name"
	)
	invoice = frappe.get_doc(
		dict(
			doctype="Purchase Invoice",
			supplier=supplier,
			company=company,
			posting_date=posting_date or nowdate(),
			set_posting_time=1,
			items=[dict(item_code=item, qty=qty, rate=rate, warehouse=warehouse)],
		)
	)
	invoice.insert()
	invoice.submit()
	return invoice


def verify_supplier_payment_flows():
	results = []
	try:
		company = frappe.db.get_single_value("Cardboard Dashboard Settings", "company")
		assert company, "Cardboard Dashboard Settings must define a company"
		# Fresh supplier per run: site data must never influence the assertions.
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": f"_P03R02 Smoke {frappe.generate_hash(length=8)}",
				"supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
			}
		).insert().name
		mode_of_payment = None
		for name in frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name"):
			if frappe.get_all(
				"Mode of Payment Account",
				filters={"parent": name, "company": company},
				pluck="default_account",
			):
				mode_of_payment = name
				break
		assert supplier and mode_of_payment

		# Case 1: valid partial payment generated and submitted natively.
		invoice = _make_purchase_invoice(supplier, company)
		payment = frappe.get_doc(
			dict(
				doctype="Cardboard Supplier Payment",
				posting_date=nowdate(),
				supplier=supplier,
				amount=400,
				mode_of_payment=mode_of_payment,
				notes="P03-R02 smoke verification (partial)",
			)
		).insert()
		payment.submit()
		payment.reload()
		entry = frappe.get_doc("Payment Entry", payment.payment_entry)
		assert entry.docstatus == 1
		assert entry.party == supplier and entry.company == company
		assert flt(entry.paid_amount) == 400
		assert entry.posting_date == payment.posting_date
		assert entry.mode_of_payment == mode_of_payment
		assert {r.reference_doctype for r in entry.references} == {"Purchase Invoice"}
		invoice.reload()
		assert flt(invoice.outstanding_amount) == flt(invoice.grand_total) - 400
		assert payment.payment_status == "Submitted"
		results.append(dict(case="valid_partial", wrapper=payment.name,
							payment_entry=payment.payment_entry,
							outstanding=invoice.outstanding_amount))

		# Case 2: cancel the wrapper; the native Payment Entry cancels with it.
		payment.cancel()
		payment.reload()
		assert payment.payment_status == "Cancelled"
		assert not frappe.db.exists(
			"Payment Entry", {"name": entry.name, "docstatus": 1}
		)
		invoice.reload()
		assert flt(invoice.outstanding_amount) == flt(invoice.grand_total)
		results.append(dict(case="cancel_restores", outstanding=invoice.outstanding_amount))

		# Case 3: invalid amounts are rejected before any Payment Entry exists.
		for label, amount in (("zero", 0), ("negative", -5)):
			try:
				frappe.get_doc(
					dict(
						doctype="Cardboard Supplier Payment",
						posting_date=nowdate(),
						supplier=supplier,
						amount=amount,
						mode_of_payment=mode_of_payment,
					)
				).insert()
				raise AssertionError(f"{label} amount should have been rejected")
			except frappe.ValidationError:
				results.append(dict(case=f"rejected_{label}"))
		# Over-outstanding amount: passes draft validation, rejected at submit
		# when the FIFO allocation against open invoices cannot cover it.
		try:
			over = frappe.get_doc(
				dict(
					doctype="Cardboard Supplier Payment",
					posting_date=nowdate(),
					supplier=supplier,
					amount=10 ** 9,
					mode_of_payment=mode_of_payment,
				)
			).insert()
			over.submit()
			raise AssertionError("over amount should have been rejected")
		except frappe.ValidationError:
			results.append(dict(case="rejected_over"))

		# Case 4: idempotency - a submitted wrapper never generates twice; the
		# generation path refuses duplicates because the wrapper already carries
		# its Payment Entry link.
		invoice2 = _make_purchase_invoice(supplier, company)
		payment2 = frappe.get_doc(
			dict(
				doctype="Cardboard Supplier Payment",
				posting_date=nowdate(),
				supplier=supplier,
				amount=300,
				mode_of_payment=mode_of_payment,
			)
		).insert()
		payment2.submit()
		entry2 = frappe.get_doc("Payment Entry", payment2.payment_entry)
		assert entry2.docstatus == 1
		before = frappe.db.count("Payment Entry")
		payment2.submit()  # retry: must complete the existing entry, not create one
		after = frappe.db.count("Payment Entry")
		assert before == after, "duplicate Payment Entry must not be created"
		payment2.reload()
		assert payment2.payment_entry == entry2.name
		results.append(dict(case="idempotent", payment_entry=entry2.name))

		return dict(results=results, persistence="All verification transactions rolled back")
	finally:
		frappe.db.rollback()
