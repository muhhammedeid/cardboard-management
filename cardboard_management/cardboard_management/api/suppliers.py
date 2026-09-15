import frappe
from frappe import _
from frappe.utils import cint

from cardboard_management.cardboard_management.api import without_transport_metadata


SUPPLIER_DOCTYPE = "Supplier"
SETTINGS_DOCTYPE = "Cardboard Dashboard Settings"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
SORT_FIELDS = {
	"supplier_name": "supplier_name",
	"name": "name",
	"supplier_group": "supplier_group",
	"modified": "modified",
	"creation": "creation",
}
CREATE_FIELDS = {"supplier_name", "supplier_type", "tax_id", "supplier_details"}
DETAIL_FIELDS = [
	"name",
	"supplier_name",
	"supplier_group",
	"supplier_type",
	"disabled",
	"mobile_no",
	"email_id",
	"primary_address",
	"tax_id",
	"supplier_details",
]
LIST_FIELDS = ["name", "supplier_name", "supplier_group", "disabled"]


def _clear_error():
	frappe.local.response.pop("supplier_error", None)


def _set_error(code, message, *, field=None):
	payload = {"code": code, "message": str(message)}
	if field:
		payload["field"] = field
	frappe.local.response["supplier_error"] = payload
	return payload


def _error(code, message, *, field=None, exc=frappe.ValidationError):
	payload = _set_error(code, message, field=field)
	frappe.throw(payload["message"], exc=exc)


def _normalize_exception(exc):
	if frappe.local.response.get("supplier_error"):
		raise exc
	message = str(exc)
	if isinstance(exc, frappe.PermissionError):
		_set_error("permission_denied", message)
	elif isinstance(exc, frappe.DoesNotExistError):
		_set_error("not_found", message)
	elif isinstance(exc, frappe.DuplicateEntryError):
		_set_error("duplicate_supplier", message, field="supplier_name")
	elif isinstance(exc, frappe.ValidationError):
		_set_error("validation", message)
	else:
		frappe.log_error(title="Supplier API unexpected error", message=frappe.get_traceback())
		payload = _set_error("unexpected_error", _("Unexpected error while processing Supplier"))
		frappe.throw(payload["message"], exc=frappe.ValidationError)
	raise exc


def _require_read(name):
	if not frappe.db.exists(SUPPLIER_DOCTYPE, name):
		_error("not_found", _("Supplier {0} was not found").format(name), exc=frappe.DoesNotExistError)
	doc = frappe.get_doc(SUPPLIER_DOCTYPE, name)
	doc.check_permission("read")
	return doc


def _default_supplier_group():
	settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
	group = getattr(settings, "default_supplier_group", None)
	if not group:
		_error("configuration_error", _("Configure Default Supplier Group in Cardboard Dashboard Settings before creating suppliers"))
	group_doc = frappe.db.get_value("Supplier Group", group, ["name", "is_group"], as_dict=True)
	if not group_doc or group_doc.is_group:
		_error("configuration_error", _("Default Supplier Group in Cardboard Dashboard Settings must be a valid leaf group"))
	return group_doc.name


def _capabilities(doc=None):
	return {
		"can_read": bool(doc.has_permission("read")) if doc else bool(frappe.has_permission(SUPPLIER_DOCTYPE, "read")),
		"can_create": bool(frappe.has_permission(SUPPLIER_DOCTYPE, "create")),
		# Editing a supplier is a real right now: the field allowlist below is what
		# keeps it inside the data captured at creation time.
		"can_edit": bool(doc.has_permission("write")) if doc else bool(frappe.has_permission(SUPPLIER_DOCTYPE, "write")),
	}


def _serialize(doc, *, detail=False):
	payload = {
		"name": doc.name,
		"supplier_name": doc.supplier_name or doc.name,
		"supplier_group": doc.supplier_group,
		"disabled": bool(doc.disabled),
	}
	if not detail:
		return payload
	for field in DETAIL_FIELDS:
		payload[field] = doc.get(field)
	payload["disabled"] = bool(doc.disabled)
	payload["capabilities"] = _capabilities(doc)
	return payload


def _validated_create_values(values):
	values = without_transport_metadata(values)
	unknown = set(values) - CREATE_FIELDS
	if unknown:
		_error("validation", _("Unsupported Supplier fields: {0}").format(", ".join(sorted(unknown))))
	payload = {field: values.get(field) for field in CREATE_FIELDS if values.get(field) not in (None, "")}
	name = (payload.get("supplier_name") or "").strip()
	if not name:
		_error("validation", _("Supplier Name is required"), field="supplier_name")
	payload["supplier_name"] = name
	payload["supplier_type"] = payload.get("supplier_type") or "Company"
	if payload["supplier_type"] not in {"Company", "Individual", "Partnership"}:
		_error("validation", _("Invalid Supplier Type"), field="supplier_type")
	return payload


def _validated_update_values(values):
	"""Partial update: only the fields offered at creation may change."""
	values = without_transport_metadata(values)
	unknown = set(values) - CREATE_FIELDS
	if unknown:
		_error("validation", _("Unsupported Supplier fields: {0}").format(", ".join(sorted(unknown))))
	payload = {}
	for field in CREATE_FIELDS:
		if field not in values:
			continue
		value = values.get(field)
		if isinstance(value, str):
			value = value.strip()
		if field == "supplier_name":
			if not value:
				_error("validation", _("Supplier Name is required"), field="supplier_name")
			payload[field] = value
		elif field == "supplier_type":
			if value and value not in {"Company", "Individual", "Partnership"}:
				_error("validation", _("Invalid Supplier Type"), field="supplier_type")
			payload[field] = value or "Company"
		else:
			payload[field] = value or None
	return payload


@frappe.whitelist()
def list_suppliers(page=1, page_size=DEFAULT_PAGE_SIZE, search=None, status=None, sort="supplier_name asc"):
	_clear_error()
	try:
		frappe.has_permission(SUPPLIER_DOCTYPE, "read", throw=True)
		filters = {}
		if status is not None and status != "":
			status_map = {"enabled": 0, "disabled": 1, "active": 0, "inactive": 1}
			if str(status).lower() not in status_map:
				_error("validation", _("Invalid Supplier status"), field="status")
			filters["disabled"] = status_map[str(status).lower()]
		or_filters = None
		if search:
			needle = f"%{search}%"
			or_filters = {"name": ["like", needle], "supplier_name": ["like", needle]}
		page = max(cint(page), 1)
		page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
		sort_field, _unused, direction = (sort or "supplier_name asc").partition(" ")
		sort_field = SORT_FIELDS.get(sort_field, "supplier_name")
		direction = "desc" if direction.lower() == "desc" else "asc"
		rows = frappe.get_list(
			SUPPLIER_DOCTYPE,
			filters=filters,
			or_filters=or_filters,
			fields=LIST_FIELDS,
			order_by=f"{sort_field} {direction}, name asc",
			start=(page - 1) * page_size,
			page_length=page_size,
		)
		count_rows = frappe.get_list(
			SUPPLIER_DOCTYPE,
			filters=filters,
			or_filters=or_filters,
			fields=["count(name) as count"],
			page_length=1,
		)
		total = cint(count_rows[0].count if count_rows else 0)
		return {
			"data": [{**dict(row), "disabled": bool(row.disabled)} for row in rows],
			"page": page,
			"page_size": page_size,
			"total": total,
			"has_more": page * page_size < total,
		}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_supplier(name):
	_clear_error()
	try:
		return _serialize(_require_read(name), detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_new_supplier_schema():
	_clear_error()
	try:
		frappe.has_permission(SUPPLIER_DOCTYPE, "create", throw=True)
		return {
			"required_fields": ["supplier_name"],
			"optional_fields": ["supplier_type", "tax_id", "supplier_details"],
			"read_only_fields": ["name", "supplier_group", "disabled", "mobile_no", "email_id", "primary_address"],
			"system_managed_fields": ["supplier_group", "accounts", "default_currency", "default_bank_account", "payment_terms", "company"],
			"default_supplier_group": _default_supplier_group(),
			"supplier_type_default": "Company",
		}
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def create_supplier(**values):
	_clear_error()
	try:
		frappe.has_permission(SUPPLIER_DOCTYPE, "create", throw=True)
		payload = _validated_create_values(values)
		if frappe.db.exists(SUPPLIER_DOCTYPE, {"supplier_name": payload["supplier_name"]}):
			_error("duplicate_supplier", _("Supplier {0} already exists").format(payload["supplier_name"]), field="supplier_name")
		doc = frappe.get_doc(
			{
				"doctype": SUPPLIER_DOCTYPE,
				**payload,
				"supplier_group": _default_supplier_group(),
			}
		)
		doc.insert()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def update_supplier(name, **values):
	"""Edit exactly the data captured when the supplier was created."""
	_clear_error()
	try:
		doc = _require_read(name)
		doc.check_permission("write")
		payload = _validated_update_values(values)
		if not payload:
			_error("validation", _("No editable Supplier field was provided"))
		if "supplier_name" in payload and frappe.db.exists(
			SUPPLIER_DOCTYPE,
			{"supplier_name": payload["supplier_name"], "name": ["!=", doc.name]},
		):
			_error(
				"duplicate_supplier",
				_("Supplier {0} already exists").format(payload["supplier_name"]),
				field="supplier_name",
			)
		for field, value in payload.items():
			doc.set(field, value)
		doc.save()
		return _serialize(doc, detail=True)
	except Exception as exc:
		_normalize_exception(exc)


@frappe.whitelist()
def get_capabilities(name=None):
	_clear_error()
	try:
		if name:
			return {"name": name, "capabilities": _capabilities(_require_read(name))}
		frappe.has_permission(SUPPLIER_DOCTYPE, "read", throw=True)
		return {"capabilities": _capabilities()}
	except Exception as exc:
		_normalize_exception(exc)
