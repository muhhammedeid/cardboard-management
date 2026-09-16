from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate
from frappe.utils.nestedset import get_descendants_of

from cardboard_management.cardboard_management.api import without_transport_metadata


SUPPLY_DOCTYPE = "Cardboard Supply"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
SORT_FIELDS = {
    "posting_date": "posting_date",
    "name": "name",
    "supplier": "supplier",
    "item": "item",
    "total_amount": "total_amount",
    "payable_weight": "payable_weight",
    "modified": "modified",
}
EDITABLE_FIELDS = {
    "posting_date",
    "supplier",
    "item",
    "gross_weight",
    "tare_weight",
    "rate_per_kg",
    "discount_type",
    "discount_value",
    "vehicle_no",
    "driver_name",
    "weight_ticket",
    "supplier_receipt",
    "notes",
}
LIST_FIELDS = [
    "name",
    "posting_date",
    "supplier",
    "item",
    "payable_weight",
    "total_amount",
    "docstatus",
]
DETAIL_FIELDS = [
    "name",
    "posting_date",
    "supplier",
    "item",
    "warehouse",
    "gross_weight",
    "tare_weight",
    "net_weight",
    "discount_type",
    "discount_value",
    "discount_weight",
    "payable_weight",
    "display_payable_weight",
    "rate_per_kg",
    "total_amount",
    "purchase_invoice",
    "payment_status",
    "purchase_invoice_outstanding",
    "invoice_total",
    "invoice_paid_amount",
    "integration_status",
    "vehicle_no",
    "driver_name",
    "weight_ticket",
    "supplier_receipt",
    "notes",
    "docstatus",
]


def _error(code, message, *, field=None, exc=frappe.ValidationError):
    payload = {"code": code, "message": str(message)}
    if field:
        payload["field"] = field
    frappe.local.response["supply_error"] = payload
    frappe.throw(message, exc=exc)


def _require_read(name):
    if not frappe.db.exists(SUPPLY_DOCTYPE, name):
        _error("not_found", _("Supply {0} was not found").format(name), exc=frappe.DoesNotExistError)
    doc = frappe.get_doc(SUPPLY_DOCTYPE, name)
    doc.check_permission("read")
    return doc


def _settings_and_scope():
    settings = frappe.get_cached_doc("Cardboard Dashboard Settings")
    if not settings.company or not settings.cardboard_item_group or not settings.default_warehouse:
        _error("configuration_error", _("Cardboard Supply settings are incomplete"))
    groups = [settings.cardboard_item_group]
    groups.extend(get_descendants_of("Item Group", settings.cardboard_item_group))
    return settings, groups


def _names(doctype, names, value_field):
    if not names:
        return {}
    rows = frappe.get_all(doctype, filters={"name": ["in", list(names)]}, fields=["name", value_field])
    return {row.name: row.get(value_field) or row.name for row in rows}


def _capabilities(doc):
    draft = doc.docstatus == 0
    submitted = doc.docstatus == 1
    return {
        "can_edit": bool(draft and doc.has_permission("write")),
        "can_submit": bool(draft and doc.has_permission("submit")),
        "can_cancel": bool(submitted and doc.has_permission("cancel")),
        "can_capture_gross": bool(draft and doc.has_permission("write")),
        "can_capture_tare": bool(draft and doc.has_permission("write")),
        "can_print": bool(doc.has_permission("read")),
    }


def _serialize(doc, *, detail=False):
    if detail:
        doc.onload()
        values = {field: doc.get(field) for field in DETAIL_FIELDS}
        values["supplier_name"] = frappe.db.get_value("Supplier", doc.supplier, "supplier_name") or doc.supplier
        values["item_name"] = frappe.db.get_value("Item", doc.item, "item_name") or doc.item
        values["status"] = "Draft" if doc.docstatus == 0 else "Submitted" if doc.docstatus == 1 else "Cancelled"
        values["capabilities"] = _capabilities(doc)
        return values
    return {
        "name": doc.name,
        "posting_date": doc.posting_date,
        "supplier": doc.supplier,
        "supplier_name": frappe.db.get_value("Supplier", doc.supplier, "supplier_name") or doc.supplier,
        "item": doc.item,
        "item_name": frappe.db.get_value("Item", doc.item, "item_name") or doc.item,
        "payable_weight": doc.payable_weight,
        "total_amount": doc.total_amount,
        "status": "Draft" if doc.docstatus == 0 else "Submitted" if doc.docstatus == 1 else "Cancelled",
        "docstatus": doc.docstatus,
    }


def _save_draft(doc, values):
    values = without_transport_metadata(values)
    if doc.docstatus != 0:
        _error("invalid_state", _("Only Draft supplies can be changed"), exc=frappe.ValidationError)
    doc.check_permission("write")
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        _error("invalid_field", _("Unsupported Supply fields: {0}").format(", ".join(sorted(unknown))))
    doc.update(values)
    doc.save()
    return _serialize(doc, detail=True)


def _preview_supply(values):
    values = without_transport_metadata(values)
    if not frappe.has_permission(SUPPLY_DOCTYPE, "create"):
        _error("permission_denied", _("Supply preview is not permitted"), exc=frappe.PermissionError)
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        _error("invalid_field", _("Unsupported Supply fields: {0}").format(", ".join(sorted(unknown))))
    settings, _scope = _settings_and_scope()
    doc = frappe.get_doc({"doctype": SUPPLY_DOCTYPE, "warehouse": settings.default_warehouse, **values})
    try:
        doc.validate()
    except frappe.ValidationError as exc:
        _error("validation_error", exc)
    return {
        "net_weight": doc.net_weight,
        "discount_weight": doc.discount_weight,
        "payable_weight": doc.payable_weight,
        "display_payable_weight": doc.get_display_payable_weight(),
        "total_amount": doc.total_amount,
    }


@frappe.whitelist()
def list_supplies(
    date_from=None,
    date_to=None,
    supplier=None,
    item=None,
    status=None,
    search=None,
    page=1,
    page_size=DEFAULT_PAGE_SIZE,
    sort="posting_date desc",
):
    filters = {}
    if date_from:
        filters["posting_date"] = [">=", getdate(date_from)]
    if date_to:
        filters.setdefault("posting_date", ["between", [getdate(date_from or "1900-01-01"), getdate(date_to)]])
        if date_from:
            filters["posting_date"] = ["between", [getdate(date_from), getdate(date_to)]]
    if supplier:
        filters["supplier"] = supplier
    if item:
        filters["item"] = item
    if status:
        status_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
        if status not in status_map:
            _error("validation_error", _("Invalid Supply status"), field="status")
        filters["docstatus"] = status_map[status]
    or_filters = None
    if search:
        needle = f"%{frappe.db.escape(search, percent=False)}%"
        or_filters = {"name": ["like", needle], "supplier": ["like", needle], "item": ["like", needle]}

    page = max(cint(page), 1)
    page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
    sort_field, _unused, direction = (sort or "posting_date desc").partition(" ")
    sort_field = SORT_FIELDS.get(sort_field, "posting_date")
    direction = "asc" if direction.lower() == "asc" else "desc"
    rows = frappe.get_list(
        SUPPLY_DOCTYPE,
        filters=filters,
        or_filters=or_filters,
        fields=LIST_FIELDS,
        order_by=f"{sort_field} {direction}",
        start=(page - 1) * page_size,
        page_length=page_size,
    )
    count_rows = frappe.get_list(
        SUPPLY_DOCTYPE,
        filters=filters,
        or_filters=or_filters,
        fields=["count(name) as count"],
        page_length=1,
    )
    total = cint(count_rows[0].count if count_rows else 0)
    supplier_names = _names("Supplier", {row.supplier for row in rows}, "supplier_name")
    item_names = _names("Item", {row.item for row in rows}, "item_name")
    data = []
    for row in rows:
        record = dict(row)
        record["supplier_name"] = supplier_names.get(row.supplier, row.supplier)
        record["item_name"] = item_names.get(row.item, row.item)
        record["status"] = "Draft" if row.docstatus == 0 else "Submitted" if row.docstatus == 1 else "Cancelled"
        data.append(record)
    return {"data": data, "page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total}


@frappe.whitelist()
def get_supply(name):
    return _serialize(_require_read(name), detail=True)


@frappe.whitelist()
def lookup_suppliers(search=None, page_size=DEFAULT_PAGE_SIZE):
    if not frappe.has_permission("Supplier", "read"):
        _error("permission_denied", _("Supplier lookup is not permitted"), exc=frappe.PermissionError)
    page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
    filters = {"disabled": 0}
    if search:
        filters["supplier_name"] = ["like", f"%{frappe.db.escape(search, percent=False)}%"]
    return {"data": frappe.get_list("Supplier", filters=filters, fields=["name", "supplier_name"], page_length=page_size)}


@frappe.whitelist()
def lookup_items(search=None, page_size=DEFAULT_PAGE_SIZE):
    if not frappe.has_permission("Item", "read"):
        _error("permission_denied", _("Item lookup is not permitted"), exc=frappe.PermissionError)
    _settings, groups = _settings_and_scope()
    page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
    filters = {"disabled": 0, "is_stock_item": 1, "stock_uom": "Kg", "item_group": ["in", groups]}
    if search:
        term = f"%{frappe.db.escape(search, percent=False)}%"
        filters["item_name"] = ["like", term]
    return {"data": frappe.get_list("Item", filters=filters, fields=["name", "item_name", "item_group", "stock_uom"], page_length=page_size)}


@frappe.whitelist()
def preview_supply(**values):
    return _preview_supply(values)


@frappe.whitelist()
def create_supply(**values):
    values = without_transport_metadata(values)
    settings, _scope = _settings_and_scope()
    unknown = set(values) - EDITABLE_FIELDS
    if unknown:
        _error("invalid_field", _("Unsupported Supply fields: {0}").format(", ".join(sorted(unknown))))
    values["warehouse"] = settings.default_warehouse
    doc = frappe.get_doc({"doctype": SUPPLY_DOCTYPE, **values})
    doc.insert()
    return _serialize(doc, detail=True)


@frappe.whitelist()
def update_supply(name, **values):
    return _save_draft(_require_read(name), values)


@frappe.whitelist()
def submit_supply(name):
    doc = _require_read(name)
    if doc.docstatus != 0:
        _error("invalid_state", _("Only Draft supplies can be submitted"))
    doc.check_permission("submit")
    doc.submit()
    return _serialize(doc, detail=True)


@frappe.whitelist()
def cancel_supply(name):
    doc = _require_read(name)
    if doc.docstatus != 1:
        _error("invalid_state", _("Only Submitted supplies can be cancelled"))
    doc.check_permission("cancel")
    doc.cancel()
    return _serialize(doc, detail=True)


def _capture(name, fieldname, weight):
    from cardboard_management.rounding import round_kg

    doc = _require_read(name)
    if doc.docstatus != 0:
        _error("invalid_state", _("Scale capture is available for Draft supplies only"))
    doc.check_permission("write")
    if weight is None:
        _error("scale_error", _("Scale integration is not configured"))
    weight = flt(weight)
    if weight < 0:
        _error("scale_error", _("Captured weight cannot be negative"), field=fieldname)
    # P05-UAT-FIX04: captured scale values are stored as whole kilograms so the
    # whole operational flow sees the same integer inputs the ticket prints.
    weight = round_kg(weight)
    doc.set(fieldname, weight)
    doc.save()
    return {"field": fieldname, "weight": weight, "supply": _serialize(doc, detail=True)}


@frappe.whitelist()
def capture_gross_weight(name, weight=None):
    return _capture(name, "gross_weight", weight)


@frappe.whitelist()
def capture_tare_weight(name, weight=None):
    return _capture(name, "tare_weight", weight)


@frappe.whitelist()
def get_create_capabilities():
    can_create = bool(frappe.has_permission(SUPPLY_DOCTYPE, "create"))
    return {"can_create": can_create, "can_submit": bool(can_create and frappe.has_permission(SUPPLY_DOCTYPE, "submit"))}


@frappe.whitelist()
def get_capabilities(name):
    doc = _require_read(name)
    return {"name": name, "capabilities": _capabilities(doc)}


@frappe.whitelist()
def get_print_action(name):
    doc = _require_read(name)
    if not doc.has_permission("read"):
        _error("permission_denied", _("Supply ticket print is not permitted"), exc=frappe.PermissionError)
    query = urlencode({"doctype": SUPPLY_DOCTYPE, "name": doc.name, "format": "Cardboard Supply Ticket", "no_letterhead": 1})
    return {"name": doc.name, "format": "Cardboard Supply Ticket", "url": frappe.utils.get_url(f"/printview?{query}")}
