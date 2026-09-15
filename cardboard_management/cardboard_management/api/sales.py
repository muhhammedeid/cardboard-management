from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from cardboard_management.cardboard_management.api import without_transport_metadata
from cardboard_management.cardboard_management.doctype.cardboard_sale.cardboard_sale import CardboardSale

try:
	from cardboard_management.cardboard_management.api.supply import lookup_items as lookup_cardboard_items
except ImportError:  # pragma: no cover - BCR01 supplies the shared item lookup in this branch.
	lookup_cardboard_items = None


SALE_DOCTYPE = "Cardboard Sale"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
SORT_FIELDS = {
	"posting_date": "posting_date",
	"creation": "creation",
	"name": "name",
	"buyer_name": "buyer_name",
	"item": "item",
	"quantity": "quantity",
	"total_amount": "total_amount",
	"modified": "modified",
}
STATUS_MAP = {"Draft": 0, "Submitted": 1, "Cancelled": 2, "draft": 0, "submitted": 1, "cancelled": 2}
STATUS_LABELS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
EDITABLE_FIELDS = {
	"posting_date",
	"item",
	"quantity",
	"rate_per_kg",
	"buyer_name",
	"notes",
}
LIST_FIELDS = [
	"name",
	"posting_date",
	"buyer_name",
	"item",
	"quantity",
	"rate_per_kg",
	"total_amount",
	"docstatus",
	"creation",
]
DETAIL_FIELDS = [
	"name",
	"posting_date",
	"buyer_name",
	"item",
	"quantity",
	"rate_per_kg",
	"total_amount",
	"notes",
	"company",
	"warehouse",
	"stock_entry",
	"docstatus",
]


def _clear_error():
	frappe.local.response.pop("sale_error", None)


def _set_error(code, message, *, field=None):
	payload = {"code": code, "message": str(message)}
	if field:
		payload["field"] = field
	frappe.local.response["sale_error"] = payload
	return payload


def _error(code, message, *, field=None, exc=frappe.ValidationError):
	_set_error(code, message, field=field)
	frappe.throw(message, exc=exc)


def _normalize_exception(exc):
	if frappe.local.response.get("sale_error"):
		raise exc
	message = str(exc)
	if CardboardSale.INSUFFICIENT_STOCK_MESSAGE in message:
		_set_error("insufficient_stock", message, field="quantity")
	elif isinstance(exc, frappe.PermissionError):
		_set_error("permission_denied", message)
	elif isinstance(exc, frappe.DoesNotExistError):
		_set_error("not_found", message)
	elif isinstance(exc, frappe.ValidationError):
		_set_error("validation", message)
	else:
		frappe.log_error(title="Sales API unexpected error", message=frappe.get_traceback())
		payload = _set_error("unexpected_error", _("Unexpected error while processing Cardboard Sale"))
		frappe.throw(payload["message"], exc=frappe.ValidationError)
	raise exc


def _status_label(docstatus):
	return STATUS_LABELS.get(cint(docstatus), "Unknown")


def _require_read(name):
	if not frappe.db.exists(SALE_DOCTYPE, name):
		_error("not_found", _("Sale {0} was not found").format(name), exc=frappe.DoesNotExistError)
	doc = frappe.get_doc(SALE_DOCTYPE, name)
	doc.check_permission("read")
	return doc


def _item_names(names):
	if not names:
		return {}
	rows = frappe.get_list("Item", filters={"name": ["in", list(names)]}, fields=["name", "item_name"])
	return {row.name: row.item_name or row.name for row in rows}


def _capabilities(doc):
	draft = doc.docstatus == 0
	submitted = doc.docstatus == 1
	return {
		"can_edit": bool(draft and doc.has_permission("write")),
		"can_submit": bool(draft and doc.has_permission("submit")),
		"can_cancel": bool(submitted and doc.has_permission("cancel")),
	}


def _serialize(doc, *, detail=False):
	item_name = frappe.db.get_value("Item", doc.item, "item_name") or doc.item
	base = {
		"name": doc.name,
		"posting_date": doc.posting_date,
		"buyer_name": doc.buyer_name,
		"item": doc.item,
		"item_name": item_name,
		"quantity": doc.quantity,
		"rate_per_kg": doc.rate_per_kg,
		"total_amount": doc.total_amount,
		"informational_value": doc.total_amount,
		"status": _status_label(doc.docstatus),
		"docstatus": doc.docstatus,
	}
	if not detail:
		return base
	for field in DETAIL_FIELDS:
		base[field] = doc.get(field)
	base["item_name"] = item_name
	base["informational_value"] = doc.total_amount
	base["capabilities"] = _capabilities(doc)
	return base


def _coerce_values(values):
	values = without_transport_metadata(values)
	if not values:
		return {}
	unknown = set(values) - EDITABLE_FIELDS
	if unknown:
		_error("validation", _("Unsupported Sale fields: {0}").format(", ".join(sorted(unknown))))
	return {key: value for key, value in values.items() if key in EDITABLE_FIELDS}


def _save_draft(doc, values):
	if doc.docstatus != 0:
		_error("invalid_state", _("Only Draft sales can be changed"))
	doc.check_permission("write")
	doc.update(_coerce_values(values))
	doc.save()
	return _serialize(doc, detail=True)


def _make_filters(from_date=None, to_date=None, item=None, buyer=None, status=None):
	filters = {}
	if from_date and to_date:
		filters["posting_date"] = ["between", [getdate(from_date), getdate(to_date)]]
	elif from_date:
		filters["posting_date"] = [">=", getdate(from_date)]
	elif to_date:
		filters["posting_date"] = ["<=", getdate(to_date)]
	if item:
		filters["item"] = item
	if buyer:
		filters["buyer_name"] = ["like", f"%{buyer}%"]
	if status:
		if status not in STATUS_MAP:
			_error("validation", _("Invalid Sale status"), field="status")
		filters["docstatus"] = STATUS_MAP[status]
	return filters


def _make_search(search):
	if not search:
		return None
	needle = f"%{search}%"
	return {"name": ["like", needle], "buyer_name": ["like", needle], "item": ["like", needle]}


@frappe.whitelist()
def list_sales(
	from_date=None,
	to_date=None,
	item=None,
	buyer=None,
	status=None,
	search=None,
	page=1,
	page_size=DEFAULT_PAGE_SIZE,
	sort=None,
):
	_clear_error()
	try:
		filters = _make_filters(from_date=from_date, to_date=to_date, item=item, buyer=buyer, status=status)
		or_filters = _make_search(search)
		page = max(cint(page), 1)
		page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
		if sort:
			sort_field, _unused, direction = sort.partition(" ")
			sort_field = SORT_FIELDS.get(sort_field, "posting_date")
			direction = "asc" if direction.lower() == "asc" else "desc"
			order_by = f"{sort_field} {direction}, creation desc, name desc"
		else:
			order_by = "posting_date desc, creation desc, name desc"
		rows = frappe.get_list(
			SALE_DOCTYPE,
			filters=filters,
			or_filters=or_filters,
			fields=LIST_FIELDS,
			order_by=order_by,
			start=(page - 1) * page_size,
			page_length=page_size,
		)
		count_rows = frappe.get_list(
			SALE_DOCTYPE,
			filters=filters,
			or_filters=or_filters,
			fields=["count(name) as count"],
			page_length=1,
		)
		total = cint(count_rows[0].count if count_rows else 0)
		item_names = _item_names({row.item for row in rows})
		data = []
		for row in rows:
			record = dict(row)
			record["item_name"] = item_names.get(row.item, row.item)
			record["informational_value"] = row.total_amount
			record["status"] = _status_label(row.docstatus)
			data.append(record)
		return {"data": data, "page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_sale(name):
	_clear_error()
	try:
		return _serialize(_require_read(name), detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def lookup_buyers(search=None, page_size=DEFAULT_PAGE_SIZE):
	_clear_error()
	try:
		page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
		filters = {"buyer_name": ["!=", ""]}
		if search:
			filters["buyer_name"] = ["like", f"%{search}%"]
		rows = frappe.get_list(
			SALE_DOCTYPE,
			filters=filters,
			fields=["buyer_name"],
			order_by="modified desc",
			page_length=page_size * 3,
		)
		seen = set()
		data = []
		for row in rows:
			name = (row.buyer_name or "").strip()
			if not name or name in seen:
				continue
			seen.add(name)
			data.append({"buyer_name": name})
			if len(data) >= page_size:
				break
		return {"data": data}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def lookup_items(search=None, page_size=DEFAULT_PAGE_SIZE):
	_clear_error()
	try:
		if not lookup_cardboard_items:
			_error("configuration_error", _("Cardboard item lookup is unavailable"))
		return lookup_cardboard_items(search=search, page_size=page_size)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def create_sale(**values):
	_clear_error()
	try:
		doc = frappe.get_doc({"doctype": SALE_DOCTYPE, **_coerce_values(values)})
		doc.insert()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def update_sale(name, **values):
	_clear_error()
	try:
		return _save_draft(_require_read(name), values)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def submit_sale(name):
	_clear_error()
	try:
		doc = _require_read(name)
		if doc.docstatus != 0:
			_error("invalid_state", _("Only Draft sales can be submitted"))
		doc.check_permission("submit")
		doc.submit()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def cancel_sale(name):
	_clear_error()
	try:
		doc = _require_read(name)
		if doc.docstatus != 1:
			_error("invalid_state", _("Only Submitted sales can be cancelled"))
		doc.check_permission("cancel")
		doc.cancel()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_create_capabilities():
	"""Report whether this operator may start a sale at all.

	Mirrors `supply.get_create_capabilities`: a create form has no document to ask
	about yet, so it must never assume the right exists.
	"""
	_clear_error()
	try:
		can_create = bool(frappe.has_permission(SALE_DOCTYPE, "create"))
		return {
			"can_create": can_create,
			"can_submit": bool(can_create and frappe.has_permission(SALE_DOCTYPE, "submit")),
		}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_capabilities(name):
	_clear_error()
	try:
		doc = _require_read(name)
		return {"name": name, "capabilities": _capabilities(doc)}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_form_action(name):
	_clear_error()
	try:
		doc = _require_read(name)
		query = urlencode({"doctype": SALE_DOCTYPE, "name": doc.name})
		return {"name": doc.name, "url": frappe.utils.get_url(f"/app/cardboard-sale/{doc.name}"), "desk_route": f"/app/cardboard-sale/{doc.name}", "query": query}
	except Exception as exc:
		_normalize_exception(exc)
