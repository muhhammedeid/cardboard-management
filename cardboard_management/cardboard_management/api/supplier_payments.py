import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from cardboard_management.cardboard_management.api import without_transport_metadata
from cardboard_management.cardboard_management.doctype.cardboard_supplier_payment.cardboard_supplier_payment import (
	get_mapped_payment_account,
	get_supplier_payment_context as get_wrapper_payment_context,
)


PAYMENT_DOCTYPE = "Cardboard Supplier Payment"
SUPPLIER_DOCTYPE = "Supplier"
MODE_DOCTYPE = "Mode of Payment"
SETTINGS_DOCTYPE = "Cardboard Dashboard Settings"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
STATUS_MAP = {"Draft": 0, "Submitted": 1, "Cancelled": 2, "draft": 0, "submitted": 1, "cancelled": 2}
STATUS_LABELS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
SORT_FIELDS = {
	"posting_date": "posting_date", "supplier": "supplier", "amount": "amount",
	"mode_of_payment": "mode_of_payment", "status": "docstatus", "creation": "creation",
	"modified": "modified", "name": "name",
}
EDITABLE_FIELDS = {"supplier", "amount", "mode_of_payment", "posting_date", "reference_no", "reference_date", "notes"}
LIST_FIELDS = ["name", "posting_date", "supplier", "amount", "mode_of_payment", "docstatus", "creation"]


def _clear_error():
	frappe.local.response.pop("supplier_payment_error", None)


def _set_error(code, message, *, field=None):
	payload = {"code": code, "message": str(message)}
	if field:
		payload["field"] = field
	frappe.local.response["supplier_payment_error"] = payload
	return payload


def _error(code, message, *, field=None, exc=frappe.ValidationError):
	payload = _set_error(code, message, field=field)
	frappe.throw(payload["message"], exc=exc)


def _normalize_exception(exc):
	if frappe.local.response.get("supplier_payment_error"):
		raise exc
	message = str(exc)
	lowered = message.lower()
	if isinstance(exc, frappe.PermissionError):
		_set_error("permission_denied", message)
	elif isinstance(exc, frappe.DoesNotExistError):
		_set_error("not_found", message)
	elif "supplier" in lowered and ("disabled" in lowered or "does not exist" in lowered):
		_set_error("invalid_supplier", message, field="supplier")
	elif "mode of payment" in lowered:
		_set_error("invalid_mode_of_payment", message, field="mode_of_payment")
	elif "configure company" in lowered or "mode of payment account is mapped" in lowered:
		_set_error("configuration_error", message)
	elif "only draft" in lowered or "only submitted" in lowered:
		_set_error("invalid_lifecycle", message)
	elif "payment entry" in lowered or "outstanding" in lowered or "amount exceeds" in lowered:
		_set_error("accounting_payment_entry_failure", message)
	elif isinstance(exc, frappe.ValidationError):
		_set_error("validation", message)
	else:
		frappe.log_error(title="Supplier Payment API unexpected error", message=frappe.get_traceback())
		payload = _set_error("unexpected_error", _("Unexpected error while processing Supplier Payment"))
		frappe.throw(payload["message"], exc=frappe.ValidationError)
	raise exc


def _status_label(docstatus):
	return STATUS_LABELS.get(cint(docstatus), "Unknown")


def _require_payment(name):
	if not frappe.db.exists(PAYMENT_DOCTYPE, name):
		_error("not_found", _("Supplier Payment {0} was not found").format(name), exc=frappe.DoesNotExistError)
	doc = frappe.get_doc(PAYMENT_DOCTYPE, name)
	doc.check_permission("read")
	return doc


def _supplier_names(names):
	if not names:
		return {}
	rows = frappe.get_list(SUPPLIER_DOCTYPE, filters={"name": ["in", list(names)]}, fields=["name", "supplier_name"])
	return {row.name: row.supplier_name or row.name for row in rows}


def _default_mode_of_payment(required=False):
	mode = frappe.db.get_single_value(SETTINGS_DOCTYPE, "default_mode_of_payment")
	if not mode:
		if required:
			_error("configuration_error", _("Configure Default Mode of Payment in Cardboard Dashboard Settings"))
		return None
	company = frappe.db.get_single_value(SETTINGS_DOCTYPE, "company")
	if not company:
		_error("configuration_error", _("Configure Company in Cardboard Dashboard Settings"))
	try:
		get_mapped_payment_account(mode, company)
	except frappe.ValidationError as exc:
		_error("configuration_error", str(exc), field="default_mode_of_payment")
	return mode


def _capabilities(doc=None):
	if not doc:
		return {"can_create": bool(frappe.has_permission(PAYMENT_DOCTYPE, "create"))}
	draft = doc.docstatus == 0
	submitted = doc.docstatus == 1
	return {
		"can_read": bool(doc.has_permission("read")),
		"can_edit": bool(draft and doc.has_permission("write")),
		"can_submit": bool(draft and doc.has_permission("submit")),
		"can_cancel": bool(submitted and doc.has_permission("cancel")),
	}


def _serialize(doc, *, detail=False):
	payload = {
		"name": doc.name,
		"posting_date": doc.posting_date,
		"supplier": doc.supplier,
		"supplier_name": frappe.db.get_value(SUPPLIER_DOCTYPE, doc.supplier, "supplier_name") or doc.supplier,
		"amount": doc.amount,
		"mode_of_payment": doc.mode_of_payment,
		"status": _status_label(doc.docstatus),
		"docstatus": doc.docstatus,
	}
	if not detail:
		return payload
	payload.update({
		"reference_no": doc.reference_no,
		"reference_date": doc.reference_date,
		"notes": doc.notes,
		"payment_status": doc.payment_status,
		"current_supplier_outstanding": doc.current_supplier_outstanding,
		"expected_remaining_outstanding": doc.expected_remaining_outstanding,
		"capabilities": _capabilities(doc),
	})
	return payload


def _editable_values(values):
	values = without_transport_metadata(values)
	unknown = set(values) - EDITABLE_FIELDS
	if unknown:
		_error("validation", _("Unsupported Supplier Payment fields: {0}").format(", ".join(sorted(unknown))))
	return {key: value for key, value in values.items() if key in EDITABLE_FIELDS}


def _validate_draft(doc, values):
	if doc.docstatus != 0:
		_error("invalid_lifecycle", _("Only Draft supplier payments can be changed"))
	doc.check_permission("write")
	doc.update(_editable_values(values))
	doc.save()
	return _serialize(doc, detail=True)


def _filters(from_date=None, to_date=None, supplier=None, mode_of_payment=None, status=None):
	filters = {}
	if from_date and to_date:
		filters["posting_date"] = ["between", [getdate(from_date), getdate(to_date)]]
	elif from_date:
		filters["posting_date"] = [">=", getdate(from_date)]
	elif to_date:
		filters["posting_date"] = ["<=", getdate(to_date)]
	if supplier:
		filters["supplier"] = supplier
	if mode_of_payment:
		filters["mode_of_payment"] = mode_of_payment
	if status:
		if status not in STATUS_MAP:
			_error("validation", _("Invalid Supplier Payment status"), field="status")
		filters["docstatus"] = STATUS_MAP[status]
	return filters


def _search_filters(search):
	if not search:
		return None
	needle = f"%{search}%"
	return {"name": ["like", needle], "supplier": ["like", needle], "mode_of_payment": ["like", needle]}


@frappe.whitelist()
def list_supplier_payments(from_date=None, to_date=None, supplier=None, mode_of_payment=None, status=None, search=None, page=1, page_size=DEFAULT_PAGE_SIZE, sort=None):
	_clear_error()
	try:
		frappe.has_permission(PAYMENT_DOCTYPE, "read", throw=True)
		page = max(cint(page), 1)
		page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
		if sort:
			field, _unused, direction = sort.partition(" ")
			field = SORT_FIELDS.get(field, "posting_date")
			direction = "asc" if direction.lower() == "asc" else "desc"
			order_by = f"{field} {direction}, creation desc, name desc"
		else:
			order_by = "posting_date desc, creation desc, name desc"
		filters = _filters(from_date, to_date, supplier, mode_of_payment, status)
		or_filters = _search_filters(search)
		rows = frappe.get_list(PAYMENT_DOCTYPE, filters=filters, or_filters=or_filters, fields=LIST_FIELDS, order_by=order_by, start=(page - 1) * page_size, page_length=page_size)
		counts = frappe.get_list(PAYMENT_DOCTYPE, filters=filters, or_filters=or_filters, fields=["count(name) as count"], page_length=1)
		total = cint(counts[0].count if counts else 0)
		names = _supplier_names({row.supplier for row in rows})
		return {"data": [{**dict(row), "supplier_name": names.get(row.supplier, row.supplier), "status": _status_label(row.docstatus)} for row in rows], "page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_supplier_payment(name):
	_clear_error()
	try:
		return _serialize(_require_payment(name), detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def lookup_suppliers(search=None, page_size=DEFAULT_PAGE_SIZE):
	_clear_error()
	try:
		frappe.has_permission(SUPPLIER_DOCTYPE, "read", throw=True)
		page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
		or_filters = {"name": ["like", f"%{search}%"], "supplier_name": ["like", f"%{search}%"]} if search else None
		rows = frappe.get_list(SUPPLIER_DOCTYPE, filters={"disabled": 0}, or_filters=or_filters, fields=["name", "supplier_name", "disabled"], order_by="supplier_name asc, name asc", page_length=page_size)
		return {"data": [{"supplier": row.name, "supplier_name": row.supplier_name or row.name, "disabled": bool(row.disabled)} for row in rows]}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def lookup_modes_of_payment(search=None, page_size=DEFAULT_PAGE_SIZE):
	_clear_error()
	try:
		frappe.has_permission(MODE_DOCTYPE, "read", throw=True)
		company = frappe.db.get_single_value(SETTINGS_DOCTYPE, "company")
		if not company:
			_error("configuration_error", _("Configure Company in Cardboard Dashboard Settings"))
		page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
		filters = {"enabled": 1}
		if search:
			filters["name"] = ["like", f"%{search}%"]
		candidates = frappe.get_list(MODE_DOCTYPE, filters=filters, fields=["name"], order_by="name asc", page_length=MAX_PAGE_SIZE)
		data = []
		for row in candidates:
			try:
				get_mapped_payment_account(row.name, company)
			except frappe.ValidationError:
				frappe.clear_last_message()
				continue
			data.append({"name": row.name})
			if len(data) >= page_size:
				break
		return {"data": data}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_new_supplier_payment_schema():
	_clear_error()
	try:
		frappe.has_permission(PAYMENT_DOCTYPE, "create", throw=True)
		return {"editable_fields": ["supplier", "amount", "mode_of_payment", "posting_date", "reference_no", "reference_date", "notes"], "required_fields": ["supplier", "amount", "mode_of_payment", "posting_date"], "optional_fields": ["reference_no", "reference_date", "notes"], "server_owned_fields": ["company", "payment_entry", "payment_status", "current_supplier_outstanding", "expected_remaining_outstanding"], "default_posting_date": nowdate(), "default_mode_of_payment": _default_mode_of_payment(), "capabilities": _capabilities()}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_supplier_payment_context(supplier):
	_clear_error()
	try:
		if not frappe.db.exists(SUPPLIER_DOCTYPE, supplier):
			_error("invalid_supplier", _("Supplier {0} was not found").format(supplier), field="supplier", exc=frappe.DoesNotExistError)
		frappe.get_doc(SUPPLIER_DOCTYPE, supplier).check_permission("read")
		context = get_wrapper_payment_context(supplier)
		return {"company": context.get("company"), "current_supplier_outstanding": context.get("outstanding")}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def create_supplier_payment(**values):
	_clear_error()
	try:
		frappe.has_permission(PAYMENT_DOCTYPE, "create", throw=True)
		doc = frappe.get_doc({"doctype": PAYMENT_DOCTYPE, **_editable_values(values)})
		doc.insert()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def update_supplier_payment(name, **values):
	_clear_error()
	try:
		return _validate_draft(_require_payment(name), values)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def submit_supplier_payment(name):
	_clear_error()
	try:
		doc = _require_payment(name)
		if doc.docstatus != 0:
			_error("invalid_lifecycle", _("Only Draft supplier payments can be submitted"))
		doc.check_permission("submit")
		doc.submit()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def cancel_supplier_payment(name):
	_clear_error()
	try:
		doc = _require_payment(name)
		if doc.docstatus != 1:
			_error("invalid_lifecycle", _("Only Submitted supplier payments can be cancelled"))
		doc.check_permission("cancel")
		doc.cancel()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_supplier_payment_capabilities(name=None):
	_clear_error()
	try:
		if name:
			doc = _require_payment(name)
			return {"name": doc.name, "capabilities": _capabilities(doc)}
		frappe.has_permission(PAYMENT_DOCTYPE, "read", throw=True)
		return {"capabilities": _capabilities()}
	except Exception as exc:
		_normalize_exception(exc)
