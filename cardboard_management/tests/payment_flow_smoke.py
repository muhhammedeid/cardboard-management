"""Developer smoke verification: real ERP transactions, always rolled back."""
import frappe
from frappe.utils import nowdate


def verify_payment_flows():
    results = []
    try:
        supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
        item = frappe.db.get_value("Item", {"disabled": 0, "is_stock_item": 1, "stock_uom": "Kg"}, "name")
        warehouse = frappe.db.get_value("Warehouse", {"disabled": 0, "is_group": 0}, "name")
        for label, amount, expected, status in (
            ("deferred", None, 5525, "Unpaid"),
            ("partial", 2000, 3525, "Partially Paid"),
            ("full", 5525, 0, "Paid"),
        ):
            supply = frappe.get_doc(dict(doctype="Cardboard Supply", posting_date=nowdate(),
                supplier=supplier, item=item, warehouse=warehouse, gross_weight=1150,
                tare_weight=250, discount_type="Kg", discount_value=50, rate_per_kg=6.5)).insert().submit()
            invoice = frappe.get_doc("Purchase Invoice", supply.purchase_invoice)
            payment = None
            if amount is not None:
                account = frappe.db.get_value("Account", dict(company=invoice.company,
                    is_group=0, disabled=0, account_type=["in", ["Cash", "Bank"]]), "name")
                payment = supply.make_payment_entry(account)
                assert payment.is_new() and payment.docstatus == 0
                payment.paid_amount = amount
                payment.received_amount = amount
                payment.references[0].allocated_amount = amount
                payment.reference_no = "P01-W04 smoke verification"
                payment.reference_date = nowdate()
                payment.insert().submit()
            invoice.reload()
            supply.reload()
            supply.onload()
            assert invoice.outstanding_amount == expected
            assert supply.as_dict().payment_status == status
            assert supply.as_dict().purchase_invoice_outstanding == expected
            row = dict(case=label, total=invoice.grand_total, payment=amount,
                outstanding=invoice.outstanding_amount, status=supply.payment_status,
                supply=supply.name, invoice=invoice.name,
                payment_entry=payment.name if payment else None)
            if payment:
                payment.cancel()
                invoice.reload()
                supply.reload()
                supply.onload()
                assert invoice.outstanding_amount == 5525 and supply.payment_status == "Unpaid"
                row["after_cancel"] = dict(outstanding=invoice.outstanding_amount, status=supply.payment_status)
            results.append(row)
        return dict(results=results, persistence="All verification transactions rolled back")
    finally:
        frappe.db.rollback()
