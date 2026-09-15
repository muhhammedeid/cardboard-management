import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from cardboard_management.cardboard_management.api import without_transport_metadata

EXPENSE_DOCTYPE = "Quick Expense"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
EDITABLE_FIELDS = {"posting_date", "expense_category", "amount", "payment_source", "payment_mode", "supplier_or_party", "description", "attachment", "reference_no", "reference_date"}
STATUS = {"Draft": 0, "Submitted": 1, "Cancelled": 2, "draft": 0, "submitted": 1, "cancelled": 2}


def _clear(): frappe.local.response.pop("expense_error", None)
def _fail(code, message, field=None, exc=frappe.ValidationError):
    frappe.local.response.expense_error = {"code": code, "message": str(message), **({"field": field} if field else {})}
    frappe.throw(str(message), exc=exc)
def _wrap(exc):
    if frappe.local.response.get("expense_error"): raise exc
    code = "permission_denied" if isinstance(exc, frappe.PermissionError) else "not_found" if isinstance(exc, frappe.DoesNotExistError) else "validation" if isinstance(exc, frappe.ValidationError) else "unexpected_error"
    if code == "unexpected_error":
        frappe.log_error(title="Expense API unexpected error", message=frappe.get_traceback())
        _fail(code, _("Unexpected error while processing expense"))
    frappe.local.response.expense_error = {"code": code, "message": str(exc)}; raise exc
def _label(ds): return {0:"Draft",1:"Submitted",2:"Cancelled"}.get(cint(ds),"Unknown")
def _doc(name):
    if not frappe.db.exists(EXPENSE_DOCTYPE,name): _fail("not_found",_("Expense was not found"),exc=frappe.DoesNotExistError)
    d=frappe.get_doc(EXPENSE_DOCTYPE,name); d.check_permission("read"); return d
def _caps(d=None):
    if not d: return {"can_create":bool(frappe.has_permission(EXPENSE_DOCTYPE,"create"))}
    return {"can_read":bool(d.has_permission("read")),"can_edit":bool(d.docstatus==0 and d.has_permission("write")),"can_submit":bool(d.docstatus==0 and d.has_permission("submit")),"can_cancel":bool(d.docstatus==1 and d.has_permission("cancel"))}
def _account_names(names):
    rows=frappe.get_list("Account",filters={"name":["in",list(names)]},fields=["name","account_name"])
    return {r.name:r.account_name or r.name for r in rows}
def _serialize(d,detail=False):
    names=_account_names({d.expense_account,d.payment_account})
    out={"name":d.name,"posting_date":d.posting_date,"expense_category":d.expense_account,"expense_category_name":names.get(d.expense_account,d.expense_account),"amount":d.amount,"payment_source":d.payment_account,"payment_source_name":names.get(d.payment_account,d.payment_account),"payment_mode":d.payment_mode,"status":_label(d.docstatus),"docstatus":d.docstatus}
    if detail: out.update({"supplier_or_party":d.supplier_or_party,"description":d.description,"attachment":d.attachment,"reference_no":d.reference_no,"reference_date":d.reference_date,"accounting_status":d.accounting_status,"capabilities":_caps(d)})
    return out
def _values(values):
    values = without_transport_metadata(values)
    unknown=set(values)-EDITABLE_FIELDS
    if unknown: _fail("validation",_("Unsupported Expense fields: {0}").format(", ".join(sorted(unknown))))
    p={k:v for k,v in values.items() if k in EDITABLE_FIELDS}; p["expense_account"]=p.pop("expense_category",None); p["payment_account"]=p.pop("payment_source",None); return p

@frappe.whitelist()
def list_expenses(from_date=None,to_date=None,expense_category=None,status=None,search=None,page=1,page_size=25,sort=None):
 _clear()
 try:
  frappe.has_permission(EXPENSE_DOCTYPE,"read",throw=True); f={}
  if from_date and to_date:f["posting_date"]=["between",[getdate(from_date),getdate(to_date)]]
  elif from_date:f["posting_date"]=[">=",getdate(from_date)]
  elif to_date:f["posting_date"]=["<=",getdate(to_date)]
  if expense_category:f["expense_account"]=expense_category
  if status:
   if status not in STATUS:_fail("validation",_("Invalid expense status"),"status")
   f["docstatus"]=STATUS[status]
  n=f"%{search}%" if search else None; o={"name":["like",n],"expense_account":["like",n],"description":["like",n]} if n else None
  page=max(cint(page),1); size=min(max(cint(page_size) or 25,1),MAX_PAGE_SIZE); field=(sort or "posting_date").split()[0]; field={"posting_date":"posting_date","amount":"amount","expense_category":"expense_account","name":"name"}.get(field,"posting_date")
  rows=frappe.get_list(EXPENSE_DOCTYPE,filters=f,or_filters=o,fields=["name","posting_date","expense_account","amount","payment_account","payment_mode","docstatus"],order_by=f"{field} desc, name desc",start=(page-1)*size,page_length=size); count=frappe.get_list(EXPENSE_DOCTYPE,filters=f,or_filters=o,fields=["count(name) as count"],page_length=1); names=_account_names({x for r in rows for x in (r.expense_account,r.payment_account)})
  data=[{"name":r.name,"posting_date":r.posting_date,"expense_category":r.expense_account,"expense_category_name":names.get(r.expense_account,r.expense_account),"amount":r.amount,"payment_source":r.payment_account,"payment_source_name":names.get(r.payment_account,r.payment_account),"payment_mode":r.payment_mode,"status":_label(r.docstatus),"docstatus":r.docstatus} for r in rows]; total=cint(count[0].count if count else 0); return {"data":data,"page":page,"page_size":size,"total":total,"has_more":page*size<total}
 except Exception as e:_wrap(e)
@frappe.whitelist()
def get_expense(name):
 _clear()
 try:return _serialize(_doc(name),True)
 except Exception as e:_wrap(e)
@frappe.whitelist()
def lookup_expense_categories(search=None,page_size=25): return _lookup_accounts(search,page_size,{"root_type":"Expense"},"expense_error")
@frappe.whitelist()
def lookup_expense_payment_sources(search=None,page_size=25): return _lookup_accounts(search,page_size,{"account_type":["in",["Cash","Bank"]]},"expense_error")
def _lookup_accounts(search,size,filters,error_key):
 _clear()
 try:
  frappe.has_permission("Account","read",throw=True); company=frappe.db.get_single_value("Cardboard Dashboard Settings","company"); filters={**filters,"company":company,"disabled":0,"is_group":0};
  if search:filters["name"]=["like",f"%{search}%"]
  rows=frappe.get_list("Account",filters=filters,fields=["name","account_name"],order_by="account_name asc,name asc",page_length=min(max(cint(size)or 25,1),MAX_PAGE_SIZE)); return {"data":[{"name":r.name,"display_name":r.account_name or r.name} for r in rows]}
 except Exception as e:_wrap(e)
@frappe.whitelist()
def get_new_expense_schema():
 _clear()
 try:
  frappe.has_permission(EXPENSE_DOCTYPE,"create",throw=True); return {"editable_fields":sorted(EDITABLE_FIELDS),"required_fields":["posting_date","expense_category","amount","payment_source"],"optional_fields":["payment_mode","supplier_or_party","description","attachment","reference_no","reference_date"],"server_owned_fields":["company","accounting_document","accounting_status"],"default_posting_date":nowdate(),"capabilities":_caps()}
 except Exception as e:_wrap(e)
@frappe.whitelist()
def create_expense(**values):
 _clear()
 try: frappe.has_permission(EXPENSE_DOCTYPE,"create",throw=True); return _serialize(frappe.get_doc({"doctype":EXPENSE_DOCTYPE,**_values(values)}).insert(),True)
 except Exception as e:_wrap(e)
@frappe.whitelist()
def update_expense(name,**values):
 _clear()
 try:
  d=_doc(name)
  if d.docstatus!=0:_fail("invalid_lifecycle",_("Only Draft expenses can be changed"))
  d.check_permission("write");d.update(_values(values));d.save();return _serialize(d,True)
 except Exception as e:_wrap(e)
@frappe.whitelist()
def submit_expense(name):
 _clear()
 try:
  doc=_doc(name)
  if doc.docstatus!=0:_fail("invalid_lifecycle",_("Only Draft expenses can be submitted"))
  doc.check_permission("submit");doc.submit();return _serialize(doc,True)
 except Exception as e:_wrap(e)
@frappe.whitelist()
def cancel_expense(name):
 _clear()
 try:
  doc=_doc(name)
  if doc.docstatus!=1:_fail("invalid_lifecycle",_("Only Submitted expenses can be cancelled"))
  doc.check_permission("cancel");doc.cancel();return _serialize(doc,True)
 except Exception as e:_wrap(e)
@frappe.whitelist()
def get_expense_capabilities(name=None):
 _clear()
 try:return {"name":name,"capabilities":_caps(_doc(name))} if name else {"capabilities":_caps()}
 except Exception as e:_wrap(e)
