"""Read-only operational inventory service backed by ERPNext Stock Balance."""

import frappe
from frappe import _
from frappe.utils import flt, nowdate
from frappe.utils.nestedset import get_descendants_of

from erpnext.stock.report.stock_balance import stock_balance


MISSING_WAREHOUSE_MESSAGE = "لم يتم تحديد المخزن الافتراضي في إعدادات إدارة الكرتون."


def _require_inventory_access():
    frappe.has_permission("Cardboard Dashboard Settings", "read", throw=True)


def get_inventory_context():
    """Resolve only app-owned settings; never infer a warehouse from stock data."""
    settings = frappe.get_cached_doc("Cardboard Dashboard Settings")
    if not settings.company or not frappe.db.exists("Company", settings.company):
        frappe.throw(_("لم يتم تحديد الشركة في إعدادات إدارة الكرتون."))
    if not settings.cardboard_item_group or not frappe.db.exists(
        "Item Group", settings.cardboard_item_group
    ):
        frappe.throw(_("لم يتم تحديد مجموعة أصناف الكرتون في إعدادات إدارة الكرتون."))
    if not settings.default_warehouse:
        frappe.throw(_(MISSING_WAREHOUSE_MESSAGE))

    warehouse = frappe.db.get_value(
        "Warehouse",
        settings.default_warehouse,
        ["name", "company", "disabled", "is_group", "warehouse_name"],
        as_dict=True,
    )
    if not warehouse or warehouse.disabled or warehouse.is_group or warehouse.company != settings.company:
        frappe.throw(_("المخزن الافتراضي في إعدادات إدارة الكرتون غير صالح."))

    item_groups = [settings.cardboard_item_group, *get_descendants_of("Item Group", settings.cardboard_item_group)]
    items = frappe.get_all(
        "Item",
        filters={"item_group": ["in", item_groups], "is_stock_item": 1, "disabled": 0},
        fields=["name", "item_name", "stock_uom"],
        order_by="item_name asc, name asc",
    )
    return frappe._dict(
        company=settings.company,
        warehouse=warehouse.name,
        warehouse_name=warehouse.warehouse_name or warehouse.name,
        cardboard_item_group=settings.cardboard_item_group,
        currency=frappe.get_cached_value("Company", settings.company, "default_currency"),
        items=items,
    )


@frappe.whitelist()
def get_inventory_overview(item_code=None):
    """Return the current ERPNext Stock Balance for the configured operational scope."""
    _require_inventory_access()
    context = get_inventory_context()
    item_codes = [item.name for item in context["items"]]
    if item_code and item_code not in item_codes:
        frappe.throw(_("نوع الكرتون المحدد غير متاح في إعدادات إدارة الكرتون."))

    visible_item_codes = [item_code] if item_code else item_codes
    if not visible_item_codes:
        return {"state": "no_items", **context}

    _columns, stock_rows = stock_balance.execute(
        frappe._dict(
            {
                "company": context.company,
                "warehouse": [context.warehouse],
                "item_code": visible_item_codes,
                "from_date": "2000-01-01",
                "to_date": nowdate(),
                "show_stock_ageing_data": False,
                "show_variant_attributes": False,
                "include_zero_stock_items": False,
            }
        )
    )
    item_details = {item.name: item for item in context["items"]}
    rows = []
    for row in stock_rows:
        if row.item_code not in item_details:
            continue
        if not flt(row.bal_qty) and not flt(row.bal_val):
            continue
        item = item_details[row.item_code]
        rows.append(
            {
                "item_code": row.item_code,
                "item_name": item.item_name or row.item_name or row.item_code,
                "stock_uom": row.stock_uom or item.stock_uom,
                "quantity": flt(row.bal_qty),
                "stock_value": flt(row.bal_val),
            }
        )

    uoms = {row["stock_uom"] for row in rows if row["stock_uom"]}
    return {
        "state": "ok" if rows else "no_stock",
        **context,
        "items": context["items"],
        "rows": rows,
        "summary": {
            "quantity": sum(row["quantity"] for row in rows) if len(uoms) == 1 else None,
            "uom": next(iter(uoms), None) if len(uoms) == 1 else None,
            "stock_value": sum(row["stock_value"] for row in rows),
        },
    }
