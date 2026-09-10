"""Developer smoke verification: Cardboard Sale stock lifecycle, always rolled back."""
import frappe
from frappe.utils import nowdate


def verify_sale_flows():
    results = []
    try:
        settings = frappe.get_cached_doc("Cardboard Dashboard Settings")
        item = frappe.db.get_value(
            "Item",
            {"disabled": 0, "is_stock_item": 1, "stock_uom": "Kg", "item_group": settings.cardboard_item_group},
            "name",
        )
        from erpnext.stock.utils import get_stock_balance

        before = get_stock_balance(item, settings.default_warehouse, nowdate())
        assert before >= 50, f"insufficient baseline stock for smoke verification: {before}"

        sale = frappe.get_doc(
            dict(
                doctype="Cardboard Sale",
                posting_date=nowdate(),
                item=item,
                quantity=50,
                rate_per_kg=5.5,
                buyer_name="P03-W07 smoke verification",
            )
        ).insert().submit()
        assert frappe.db.get_value("Cardboard Sale", sale.name, "company") == settings.company
        assert frappe.db.get_value("Cardboard Sale", sale.name, "warehouse") == settings.default_warehouse
        assert frappe.db.get_value("Cardboard Sale", sale.name, "total_amount") == 275.0
        assert sale.stock_entry, "native Stock Entry was not linked"
        stock_entry = frappe.get_doc("Stock Entry", sale.stock_entry)
        assert stock_entry.docstatus == 1 and stock_entry.purpose == "Material Issue"
        after = get_stock_balance(item, settings.default_warehouse, nowdate())
        assert after == before - 50, f"stock did not reduce by 50: {before} -> {after}"

        sale.cancel()
        stock_entry.reload()
        assert stock_entry.docstatus == 2, "native Stock Entry did not cancel with the sale"
        restored = get_stock_balance(item, settings.default_warehouse, nowdate())
        assert restored == before, f"stock did not restore after cancellation: {restored} != {before}"

        results.append(
            dict(
                sale=sale.name,
                stock_entry=sale.stock_entry,
                before=before,
                after=after,
                restored=restored,
                total_amount=275.0,
            )
        )
        return dict(results=results, persistence="All verification transactions rolled back")
    finally:
        frappe.db.rollback()
