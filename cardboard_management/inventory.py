"""Read-only operational inventory service backed by ERPNext Stock Balance."""

import frappe
from frappe import _
from frappe.query_builder import functions as qb_functions
from frappe.utils import flt, getdate, nowdate
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


def _sum_activity(doctype, fieldname, company, warehouse, item_groups, selected_date, item_code=None):
    """Aggregate submitted operational rows for one date (selected-day activity)."""
    alias = "activity_row"
    item = frappe.qb.DocType("Item")
    activity = frappe.qb.DocType(doctype).as_(alias)
    # Cardboard Sale stores company, but Cardboard Supply resolves it through its
    # warehouse. Restrict by the configured warehouse, whose company was already
    # validated to equal the settings company by get_inventory_context().
    conditions = [
        activity.docstatus == 1,
        activity.posting_date == getdate(selected_date),
        activity.warehouse == warehouse,
        item.item_group.isin(item_groups),
    ]
    if item_code:
        conditions.append(activity.item == item_code)
    query = (
        frappe.qb.from_(activity)
        .inner_join(item)
        .on(item.name == activity.item)
        .select(
            qb_functions.Count(activity.name).as_("count"),
            qb_functions.Coalesce(
                qb_functions.Sum(activity[fieldname]), 0
            ).as_("quantity"),
        )
        .where(conditions[0])
    )
    for condition in conditions[1:]:
        query = query.where(condition)
    row = query.run(as_dict=True)[0]
    return {"count": int(row.count or 0), "quantity": flt(row.quantity or 0)}


def _selected_date_activity(company, warehouse, item_groups, selected_date, item_code=None):
    supplies = _sum_activity(
        "Cardboard Supply", "net_weight", company, warehouse, item_groups, selected_date, item_code
    )
    sales = _sum_activity(
        "Cardboard Sale", "quantity", company, warehouse, item_groups, selected_date, item_code
    )
    return {
        "supplies": supplies,
        "sales": sales,
        "net": flt(supplies["quantity"]) - flt(sales["quantity"]),
    }


def _stock_position(company, warehouse, item_details, item_codes, selected_date):
    """ERPNext Stock Balance as the single stock authority, as-of the selected date."""
    if not item_codes:
        return []
    _columns, stock_rows = stock_balance.execute(
        frappe._dict(
            {
                "company": company,
                "warehouse": [warehouse],
                "item_code": item_codes,
                "from_date": "2000-01-01",
                "to_date": getdate(selected_date),
                "show_stock_ageing_data": False,
                "show_variant_attributes": False,
                "include_zero_stock_items": False,
            }
        )
    )
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
    return rows


@frappe.whitelist()
def get_inventory_overview(item_code=None, selected_date=None):
    """Return the ERPNext stock position as-of the selected date plus day activity.

    A previous date means the stock position at the end of that day (historical
    snapshot from the Stock Balance engine), never just that day's transactions.
    """
    _require_inventory_access()
    context = get_inventory_context()
    item_codes = [item.name for item in context["items"]]
    if item_code and item_code not in item_codes:
        frappe.throw(_("نوع الكرتون المحدد غير متاح في إعدادات إدارة الكرتون."))

    selected_date = getdate(selected_date or nowdate())
    if selected_date > getdate(nowdate()):
        frappe.throw(_("لا يمكن اختيار تاريخ في المستقبل."))

    visible_item_codes = [item_code] if item_code else item_codes
    if not visible_item_codes:
        return {"state": "no_items", **context, "selected_date": str(selected_date), "items": []}

    rows = _stock_position(
        context.company,
        context.warehouse,
        {item.name: item for item in context["items"]},
        visible_item_codes,
        selected_date,
    )
    uoms = {row["stock_uom"] for row in rows if row["stock_uom"]}
    activity = _selected_date_activity(
        context.company,
        context.warehouse,
        [context.cardboard_item_group, *get_descendants_of("Item Group", context.cardboard_item_group)],
        selected_date,
        item_code,
    )
    return {
        "state": "ok" if rows else "no_stock",
        **context,
        "selected_date": str(selected_date),
        "is_today": getdate(selected_date) == getdate(nowdate()),
        "items": context["items"],
        "rows": rows,
        "summary": {
            "quantity": sum(row["quantity"] for row in rows) if len(uoms) == 1 else None,
            "uom": next(iter(uoms), None) if len(uoms) == 1 else None,
            "stock_value": sum(row["stock_value"] for row in rows),
        },
        "activity": activity,
    }
