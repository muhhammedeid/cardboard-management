import frappe
from frappe import _
from frappe.utils import cint
from cardboard_management.cardboard_management.api import without_transport_metadata
from cardboard_management.cardboard_management.api.supplier_payments import lookup_modes_of_payment as _payment_modes

SETTINGS="Cardboard Dashboard Settings"
EDITABLE_FIELDS={"company","default_warehouse","cardboard_item_group","default_supplier_group","default_mode_of_payment"}
MAX=100

def _clear(): frappe.local.response.pop("operational_settings_error",None)
def _fail(code,msg,field=None,exc=frappe.ValidationError):
 frappe.local.response.operational_settings_error={"code":code,"message":str(msg),**({"field":field}if field else {})};frappe.throw(str(msg),exc=exc)
def _wrap(e):
 if frappe.local.response.get("operational_settings_error"):raise e
 code="permission_denied" if isinstance(e,frappe.PermissionError) else "validation" if isinstance(e,frappe.ValidationError) else "unexpected_error"
 if code=="unexpected_error":frappe.log_error(title="Operational settings API unexpected error",message=frappe.get_traceback());_fail(code,_("Unexpected error while processing settings"))
 frappe.local.response.operational_settings_error={"code":code,"message":str(e)};raise e
def _doc():
 d=frappe.get_doc(SETTINGS);d.check_permission("read");return d
def _serialize(d):return {f:d.get(f) for f in EDITABLE_FIELDS}
def _caps(d=None):return {"can_read":bool((d or _doc()).has_permission("read")),"can_edit":bool(frappe.has_permission(SETTINGS,"write"))}
def _lookup(doctype,search,page_size,filters=None,fields=None):
 size=min(max(cint(page_size)or 25,1),MAX);f=filters or {}
 if search:f["name"]=["like",f"%{search}%"]
 rows=frappe.get_list(doctype,filters=f,fields=fields or ["name"],order_by="name asc",page_length=size);return {"data":[{"name":r.name,"display_name":getattr(r,"display_name",None)or r.name}for r in rows]}
@frappe.whitelist()
def get_operational_settings():
 _clear()
 try:return {**_serialize(_doc()),"capabilities":_caps()}
 except Exception as e:_wrap(e)
@frappe.whitelist()
def update_operational_settings(**values):
 _clear()
 try:
  values=without_transport_metadata(values)
  unknown=set(values)-EDITABLE_FIELDS
  if unknown:_fail("validation",_("Unsupported settings fields: {0}").format(", ".join(sorted(unknown))))
  settings=_doc();settings.check_permission("write");settings.update(values);settings.save();return {**_serialize(settings),"capabilities":_caps(settings)}
 except Exception as e:_wrap(e)
@frappe.whitelist()
def get_operational_settings_capabilities():
 _clear()
 try:return {"capabilities":_caps()}
 except Exception as e:_wrap(e)
@frappe.whitelist()
def lookup_companies(search=None,page_size=25):
 _clear()
 try:return _lookup("Company",search,page_size,{"is_group":0})
 except Exception as e:_wrap(e)
@frappe.whitelist()
def lookup_warehouses(company=None,search=None,page_size=25):
 _clear()
 try:return _lookup("Warehouse",search,page_size,{"company":company or _doc().company,"disabled":0,"is_group":0})
 except Exception as e:_wrap(e)
@frappe.whitelist()
def lookup_cardboard_item_groups(search=None,page_size=25):
 _clear()
 try:return _lookup("Item Group",search,page_size)
 except Exception as e:_wrap(e)
@frappe.whitelist()
def lookup_supplier_groups(search=None,page_size=25):
 _clear()
 try:return _lookup("Supplier Group",search,page_size,{"is_group":0})
 except Exception as e:_wrap(e)
@frappe.whitelist()
def lookup_modes_of_payment(search=None,page_size=25):
 _clear()
 try:return _payment_modes(search=search,page_size=page_size)
 except Exception as e:_wrap(e)
