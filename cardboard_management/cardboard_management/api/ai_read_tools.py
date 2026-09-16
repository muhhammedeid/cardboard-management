"""Internal operational read-tool wrappers for the Cardboard AI assistant.

V3: these are no longer model-visible. DeepSeek calls only the six semantic
domain tools (ai_domain_tools); this module stays as the shared backend-service
wrapper layer used by tests and internal callers. It is not exposed to the model.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from cardboard_management import reporting
from cardboard_management.cardboard_management.api import expenses, sales, supplier_payments, supply
from cardboard_management.inventory import get_inventory_context, get_inventory_overview

MAX_DISAMBIGUATION = 5
AI_READ_ROLES = frozenset({"Cardboard Manager", "Cardboard Operator"})
TRANSACTION_ROUTES = {"supply": "/supplies", "sale": "/sales", "expense": "/expenses", "payment": "/payments"}

# A bounded policy belongs to each business question. Searches expose a small page;
# aggregates can safely cover a longer period because they never dump raw records.
TOOL_POLICIES = {
    "get_operations_summary": {"max_rows": 0, "max_date_range_days": 3660},
    "get_sales_summary": {"max_rows": 0, "max_date_range_days": 3660},
    "get_inventory_snapshot": {"max_rows": 25, "max_date_range_days": 0},
    "get_inventory_movement": {"max_rows": 0, "max_date_range_days": 3660},
    "search_suppliers": {"max_rows": 5, "max_date_range_days": 0},
    "get_supplier_balance": {"max_rows": 0, "max_date_range_days": 3660},
    "get_supplier_statement": {"max_rows": 25, "max_date_range_days": 3660},
    "get_supplier_latest_supply": {"max_rows": 1, "max_date_range_days": 0},
    "get_expense_summary": {"max_rows": 0, "max_date_range_days": 3660},
    "list_recent_transactions": {"max_rows": 25, "max_date_range_days": 366},
    "get_supplier_supply_history": {"max_rows": 25, "max_date_range_days": 3660},
    "compare_supplier_supply_periods": {"max_rows": 0, "max_date_range_days": 3660},
    "get_supplier_payment_history": {"max_rows": 25, "max_date_range_days": 3660},
    "list_suppliers_with_balances": {"max_rows": 25, "max_date_range_days": 0},
    "get_supplier_dues_summary": {"max_rows": 10, "max_date_range_days": 3660},
    "get_supply_summary": {"max_rows": 0, "max_date_range_days": 3660},
    "search_supplies": {"max_rows": 25, "max_date_range_days": 3660},
    "compare_supply_periods": {"max_rows": 0, "max_date_range_days": 3660},
    "search_sales": {"max_rows": 25, "max_date_range_days": 3660},
    "compare_sales_periods": {"max_rows": 0, "max_date_range_days": 3660},
    "compare_inventory_periods": {"max_rows": 25, "max_date_range_days": 3660},
    "search_expenses": {"max_rows": 25, "max_date_range_days": 3660},
    "compare_expense_periods": {"max_rows": 0, "max_date_range_days": 3660},
}


def _result(*, source_label: str, facts=None, records=None, disambiguation=None):
    return {"facts": list(facts or []), "records": list(records or []), "disambiguation": list(disambiguation or []), "source_label": source_label}


def _clean_text(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(value or ""))).strip()[:limit]


def _require_ai_read_access():
    if frappe.session.user == "Guest":
        frappe.throw(_("يلزم تسجيل الدخول لاستخدام مساعد البيانات."), frappe.AuthenticationError)
    if not AI_READ_ROLES.intersection(frappe.get_roles(frappe.session.user)):
        frappe.throw(_("مش مسموح لي أعرض البيانات دي لحسابك."), frappe.PermissionError)
    frappe.has_permission("Cardboard Dashboard Settings", "read", throw=True)


def _date_range(arguments: Mapping[str, Any], tool_name: str) -> tuple[str | None, str | None]:
    from_date, to_date = arguments.get("from_date"), arguments.get("to_date")
    aliases = {"today": nowdate(), "اليوم": nowdate(), "yesterday": str(getdate(nowdate()) - timedelta(days=1)), "امبارح": str(getdate(nowdate()) - timedelta(days=1))}
    from_date = aliases.get(str(from_date).strip().casefold(), from_date) if from_date else None
    to_date = aliases.get(str(to_date).strip().casefold(), to_date) if to_date else None
    if not from_date and not to_date:
        return None, None
    start, end = getdate(from_date or to_date), getdate(to_date or from_date)
    maximum = TOOL_POLICIES[tool_name]["max_date_range_days"]
    if start > end or end > getdate(nowdate()) or (maximum and end - start > timedelta(days=maximum)):
        frappe.throw(_("الفترة المطلوبة غير مسموح بها لمساعد البيانات."), frappe.ValidationError)
    return str(start), str(end)


def _limit(arguments: Mapping[str, Any], tool_name: str) -> int:
    maximum = TOOL_POLICIES[tool_name]["max_rows"]
    return min(max(cint(arguments.get("limit")) or maximum, 1), maximum)


def _fact(identifier: str, value: Any, source: dict[str, str], *, currency=None, unit=None):
    fact = {"id": identifier, "value": value, "source": source}
    if currency:
        fact["currency"] = currency
    if unit:
        fact["unit"] = unit
    return fact


def _numeric_facts(payload: Any, source: dict[str, str], prefix: str = "", output=None):
    output = output if output is not None else []
    if len(output) >= 100:
        return output
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            _numeric_facts(value, source, f"{prefix}.{key}" if prefix else str(key), output)
    elif isinstance(payload, (int, float)) and not isinstance(payload, bool):
        output.append(_fact(prefix, flt(payload), source))
    return output


def _supplier_route(name: str) -> dict[str, str]:
    return {"route": f"/suppliers/{name}", "label": "Supplier"}


def _item_route(item_code: str | None = None) -> dict[str, str]:
    return {"route": "/inventory" + (f"?item={item_code}" if item_code else ""), "label": "Inventory"}


def _period_route(area: str) -> dict[str, str]:
    return {"route": area, "label": area.strip("/").title()}


def search_suppliers(query: str, limit: int = MAX_DISAMBIGUATION):
    _require_ai_read_access()
    query = _clean_text(query)
    if not query:
        frappe.throw(_("اكتب اسم المورد أو كوده للتحديد."), frappe.ValidationError)
    limit = min(max(cint(limit) or MAX_DISAMBIGUATION, 1), MAX_DISAMBIGUATION)
    rows = frappe.get_list("Supplier", filters={"disabled": 0}, or_filters={"name": ["like", f"%{query}%"], "supplier_name": ["like", f"%{query}%"]}, fields=["name", "supplier_name"], order_by="supplier_name asc, name asc", limit_page_length=limit)
    records = [{"id": row.name, "label": _clean_text(row.supplier_name or row.name), "source": _supplier_route(row.name)} for row in rows]
    return _result(source_label="supplier_search", records=records, disambiguation=records if len(records) != 1 else [])


def _resolve_supplier(value: str):
    matches = search_suppliers(value, MAX_DISAMBIGUATION)["records"]
    if len(matches) != 1:
        return None, _result(source_label="supplier_resolution", disambiguation=matches)
    return matches[0]["id"], None


def _resolve_item(value: str | None):
    if not value:
        return None, None
    context = get_inventory_context()
    needle = _clean_text(value).casefold()
    matches = [item for item in context["items"] if needle in item.name.casefold() or needle in (item.item_name or "").casefold()]
    if len(matches) == 1:
        return matches[0].name, None
    choices = [{"id": item.name, "label": _clean_text(item.item_name or item.name), "source": _item_route(item.name)} for item in matches[:MAX_DISAMBIGUATION]]
    return None, _result(source_label="item_resolution", disambiguation=choices)


def _report_dates(tool_name: str, from_date=None, to_date=None):
    return _date_range({"from_date": from_date, "to_date": to_date}, tool_name)


def get_operations_summary(from_date=None, to_date=None, item=None):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_operations_summary", from_date, to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    payload = reporting.get_operations_summary(from_date, to_date, item_code)
    return _result(source_label="operations_summary", facts=_numeric_facts(payload, _period_route("/operations")))


def get_sales_summary(from_date=None, to_date=None, item=None):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_sales_summary", from_date, to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    payload = reporting.get_sales_summary(from_date, to_date, item_code)
    return _result(source_label="sales_summary", facts=_numeric_facts(payload, _period_route("/sales")))


def get_inventory_snapshot(item=None, selected_date=None):
    _require_ai_read_access()
    if selected_date: _date_range({"from_date": selected_date, "to_date": selected_date}, "get_inventory_snapshot")
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    payload = get_inventory_overview(item_code, selected_date)
    records = [{"id": row["item_code"], "label": _clean_text(row["item_name"]), "quantity": flt(row["quantity"]), "uom": row["stock_uom"], "stock_value": flt(row["stock_value"]), "source": _item_route(row["item_code"])} for row in payload.get("rows", [])[:TOOL_POLICIES["get_inventory_snapshot"]["max_rows"]]]
    facts = _numeric_facts(payload.get("summary", {}), _item_route(item_code))
    for row in records:
        facts.extend((_fact(f"item.{row['id']}.quantity", row["quantity"], row["source"], unit=row["uom"]), _fact(f"item.{row['id']}.stock_value", row["stock_value"], row["source"], currency="EGP")))
    return _result(source_label="inventory_snapshot", facts=facts, records=records)


def get_inventory_movement(from_date=None, to_date=None, item=None):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_inventory_movement", from_date, to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    payload = reporting.get_inventory_movement(from_date, to_date, item_code)
    return _result(source_label="inventory_movement", facts=_numeric_facts(payload, _item_route(item_code)))


def get_supplier_balance(supplier: str, from_date=None, to_date=None):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_supplier_balance", from_date, to_date)
    supplier_name, ambiguity = _resolve_supplier(supplier)
    if ambiguity: return ambiguity
    payload = reporting.get_supplier_summary(supplier_name, from_date, to_date)
    return _result(source_label="supplier_balance", facts=_numeric_facts(payload, _supplier_route(supplier_name)))


def _supplier_history(supplier: str, from_date, to_date, kind: str, limit: int):
    supplier_name, ambiguity = _resolve_supplier(supplier)
    if ambiguity: return ambiguity
    payload = reporting.get_supplier_summary(supplier_name, from_date, to_date)
    route = _supplier_route(supplier_name)
    if kind == "supply":
        rows = payload.get("supply_history", [])[:limit]
        records = [{"id": row["supply"], "type": "supply", "date": row["posting_date"], "item": row["item"], "label": _clean_text(row["item_name"]), "quantity": flt(row["payable_weight"]), "quantity_tons": float((Decimal(str(flt(row["payable_weight"]))) / Decimal("1000")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)), "amount": flt(row["value"]), "source": {"route": f"/supplies/{row['supply']}", "label": "Supply"}} for row in rows]
    else:
        rows = payload.get("payment_history", [])[:limit]
        records = [{"id": row["payment"], "type": "payment", "date": row["posting_date"], "label": _clean_text(row.get("mode_of_payment")), "amount": flt(row["amount"]), "source": {"route": f"/payments/{row['payment']}", "label": "Payment"}} for row in rows]
    facts = _numeric_facts({"count": len(records), "outstanding": payload.get("outstanding", 0)}, route)
    for row in records:
        facts.append(_fact(f"{kind}.{row['id']}.amount", row["amount"], row["source"], currency="EGP"))
        if "quantity" in row:
            facts.append(_fact(f"{kind}.{row['id']}.quantity", row["quantity"], row["source"], unit="Kg"))
            facts.append(_fact(f"{kind}.{row['id']}.quantity_tons", row["quantity_tons"], row["source"], unit="Ton"))
    if kind == "supply":
        total_amount = sum(flt(row["amount"]) for row in records)
        total_weight_kg = sum(flt(row["quantity"]) for row in records)
        total_weight_tons = float((Decimal(str(total_weight_kg)) / Decimal("1000")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
        facts.extend((
            _fact("supply_history.total_amount", total_amount, route, currency="EGP"),
            _fact("supply_history.total_payable_weight_kg", total_weight_kg, route, unit="Kg"),
            _fact("supply_history.total_payable_weight_tons", total_weight_tons, route, unit="Ton"),
        ))
    return _result(source_label=f"supplier_{kind}_history", facts=facts, records=records)


def get_supplier_statement(supplier: str, from_date=None, to_date=None, limit=25):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_supplier_statement", from_date, to_date)
    supplier_name, ambiguity = _resolve_supplier(supplier)
    if ambiguity: return ambiguity
    payload = reporting.get_supplier_statement(supplier_name, from_date, to_date, page=1, page_size=_limit({"limit": limit}, "get_supplier_statement"))
    records = [{"id": row["name"], "type": row["type"], "date": str(row["posting_date"]), "amount": flt(row.get("amount")), "source": _supplier_route(supplier_name)} for row in payload.get("entries", [])]
    facts = _numeric_facts({"outstanding": payload.get("outstanding", 0)}, _supplier_route(supplier_name))
    facts.extend(_fact(f"statement.{row['id']}.amount", row["amount"], row["source"], currency="EGP") for row in records)
    return _result(source_label="supplier_statement", facts=facts, records=records)


def get_supplier_supply_history(supplier: str, from_date=None, to_date=None, limit=25):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_supplier_supply_history", from_date, to_date)
    return _supplier_history(supplier, from_date, to_date, "supply", _limit({"limit": limit}, "get_supplier_supply_history"))


def compare_supplier_supply_periods(supplier: str, from_date: str, to_date: str, compare_from_date: str, compare_to_date: str):
    _require_ai_read_access()
    supplier_name, ambiguity = _resolve_supplier(supplier)
    if ambiguity: return ambiguity
    from_date, to_date = _report_dates("compare_supplier_supply_periods", from_date, to_date)
    compare_from_date, compare_to_date = _report_dates("compare_supplier_supply_periods", compare_from_date, compare_to_date)
    route = _supplier_route(supplier_name)
    def totals(start, end):
        payload = reporting.get_supplier_summary(supplier_name, start, end)
        rows = payload.get("supply_history", [])
        return sum(flt(row.get("payable_weight")) for row in rows), sum(flt(row.get("value")) for row in rows)
    current_weight, current_amount = totals(from_date, to_date)
    previous_weight, previous_amount = totals(compare_from_date, compare_to_date)
    facts = [
        _fact("current.total_payable_weight_kg", current_weight, route, unit="Kg"),
        _fact("comparison.total_payable_weight_kg", previous_weight, route, unit="Kg"),
        _fact("change.total_payable_weight_kg", current_weight - previous_weight, route, unit="Kg"),
        _fact("current.total_amount", current_amount, route, currency="EGP"),
        _fact("comparison.total_amount", previous_amount, route, currency="EGP"),
        _fact("change.total_amount", current_amount - previous_amount, route, currency="EGP"),
    ]
    return _result(source_label="supplier_supply_period_comparison", facts=facts)


def get_supplier_payment_history(supplier: str, from_date=None, to_date=None, limit=25):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_supplier_payment_history", from_date, to_date)
    return _supplier_history(supplier, from_date, to_date, "payment", _limit({"limit": limit}, "get_supplier_payment_history"))


def get_supplier_latest_supply(supplier: str):
    _require_ai_read_access(); supplier_name, ambiguity = _resolve_supplier(supplier)
    if ambiguity: return ambiguity
    page = supply.list_supplies(supplier=supplier_name, status="Submitted", page=1, page_size=1, sort="modified desc")
    rows = page.get("data", [])
    if not rows: return _result(source_label="supplier_latest_supply")
    detail = supply.get_supply(rows[0]["name"]); posting_date = getdate(detail["posting_date"])
    amount, weight_kg = flt(detail.get("total_amount")), flt(detail.get("payable_weight"))
    weight_tons = float((Decimal(str(weight_kg)) / Decimal("1000")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    source = {"route": f"/supplies/{detail['name']}", "label": "Supply"}
    record = {"id": detail["name"], "type": "supply", "date": str(posting_date), "amount": amount, "payable_weight_kg": weight_kg, "payable_weight_tons": weight_tons, "source": source}
    facts = [_fact("latest_supply.amount", amount, source, currency="EGP"), _fact("latest_supply.payable_weight_kg", weight_kg, source, unit="Kg"), _fact("latest_supply.payable_weight_tons", weight_tons, source, unit="Ton")]
    return _result(source_label="supplier_latest_supply", facts=facts, records=[record])


def _dues_payload(limit: int):
    payload = reporting.get_outstanding_report(); route = _period_route("/suppliers")
    records = [{"id": row["supplier"], "label": _clean_text(row["supplier_name"]), "rank": index, "outstanding": flt(row["outstanding"]), "supply_value": flt(row["supply_value"]), "paid_amount": flt(row["paid_amount"]), "source": _supplier_route(row["supplier"])} for index, row in enumerate(payload.get("suppliers", [])[:limit], start=1)]
    facts = [_fact("total_outstanding", flt(payload.get("total_outstanding")), route, currency="EGP"), _fact("supplier_count", len(payload.get("suppliers", [])), route)]
    for row in records: facts.append(_fact(f"supplier.{row['id']}.outstanding", row["outstanding"], row["source"], currency="EGP"))
    top = next((row for row in records if row["outstanding"] > 0), None)
    if top: facts.append(_fact("top_supplier_outstanding", top["outstanding"], top["source"], currency="EGP"))
    return records, facts


def list_suppliers_with_balances(limit=25):
    _require_ai_read_access(); records, facts = _dues_payload(_limit({"limit": limit}, "list_suppliers_with_balances"))
    return _result(source_label="suppliers_with_balances", facts=facts, records=records)


def get_supplier_dues_summary(limit=10):
    _require_ai_read_access(); records, facts = _dues_payload(_limit({"limit": limit}, "get_supplier_dues_summary"))
    return _result(source_label="supplier_dues_summary", facts=facts, records=records)


def get_expense_summary(from_date=None, to_date=None):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_expense_summary", from_date, to_date)
    payload = reporting.get_expense_summary(from_date, to_date)
    return _result(source_label="expense_summary", facts=_numeric_facts(payload, _period_route("/expenses")))


def get_supply_summary(from_date=None, to_date=None, item=None):
    _require_ai_read_access(); from_date, to_date = _report_dates("get_supply_summary", from_date, to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    payload = reporting.get_operations_summary(from_date, to_date, item_code).get("supplies", {})
    return _result(source_label="supply_summary", facts=_numeric_facts(payload, _period_route("/supplies")))


def _search_records(tool_name: str, method: Callable[..., Mapping[str, Any]], route: str, **kwargs):
    page = method(page=1, page_size=_limit(kwargs, tool_name), **{key: value for key, value in kwargs.items() if key != "limit" and value not in (None, "")})
    records = []
    for row in page.get("data", []):
        name = row["name"]; source = {"route": f"{route}/{name}", "label": route.strip("/").title()}
        record = {"id": name, "date": str(row.get("posting_date") or ""), "label": _clean_text(row.get("supplier_name") or row.get("item_name") or row.get("buyer_name") or row.get("expense_category_name") or name), "amount": flt(row.get("total_amount") or row.get("informational_value") or row.get("amount") or 0), "source": source}
        if row.get("payable_weight") is not None: record["quantity"] = flt(row["payable_weight"])
        if row.get("quantity") is not None: record["quantity"] = flt(row["quantity"])
        records.append(record)
    facts = [_fact("total_matches", cint(page.get("total")), _period_route(route))]
    for row in records:
        facts.append(_fact(f"record.{row['id']}.amount", row["amount"], row["source"], currency="EGP"))
        if "quantity" in row: facts.append(_fact(f"record.{row['id']}.quantity", row["quantity"], row["source"], unit="Kg"))
    return _result(source_label=f"{tool_name}_results", facts=facts, records=records)


def search_supplies(from_date=None, to_date=None, supplier=None, item=None, limit=25):
    _require_ai_read_access(); from_date, to_date = _report_dates("search_supplies", from_date, to_date)
    supplier_name, ambiguity = _resolve_supplier(supplier) if supplier else (None, None)
    if ambiguity: return ambiguity
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    return _search_records("search_supplies", supply.list_supplies, "/supplies", date_from=from_date, date_to=to_date, supplier=supplier_name, item=item_code, status="Submitted", limit=limit, sort="posting_date desc")


def search_sales(from_date=None, to_date=None, item=None, buyer=None, limit=25):
    _require_ai_read_access(); from_date, to_date = _report_dates("search_sales", from_date, to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    return _search_records("search_sales", sales.list_sales, "/sales", from_date=from_date, to_date=to_date, item=item_code, buyer=buyer, status="Submitted", limit=limit, sort="posting_date desc")


def search_expenses(from_date=None, to_date=None, limit=25):
    _require_ai_read_access(); from_date, to_date = _report_dates("search_expenses", from_date, to_date)
    return _search_records("search_expenses", expenses.list_expenses, "/expenses", from_date=from_date, to_date=to_date, status="Submitted", limit=limit, sort="posting_date desc")


def _comparison(current: Mapping[str, Any], previous: Mapping[str, Any], source: dict[str, str]):
    facts = []
    for key in sorted(set(current) & set(previous)):
        if isinstance(current[key], (int, float)) and not isinstance(current[key], bool) and isinstance(previous[key], (int, float)) and not isinstance(previous[key], bool):
            facts.extend((_fact(f"current.{key}", flt(current[key]), source), _fact(f"comparison.{key}", flt(previous[key]), source), _fact(f"change.{key}", flt(current[key]) - flt(previous[key]), source)))
    return facts


def _comparison_dates(tool_name, from_date, to_date, compare_from_date, compare_to_date):
    current = _date_range({"from_date": from_date, "to_date": to_date}, tool_name)
    previous = _date_range({"from_date": compare_from_date, "to_date": compare_to_date}, tool_name)
    return current, previous


def compare_supply_periods(from_date, to_date, compare_from_date, compare_to_date, item=None):
    _require_ai_read_access(); (start, end), (old_start, old_end) = _comparison_dates("compare_supply_periods", from_date, to_date, compare_from_date, compare_to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    current = reporting.get_operations_summary(start, end, item_code).get("supplies", {}); previous = reporting.get_operations_summary(old_start, old_end, item_code).get("supplies", {})
    return _result(source_label="supply_period_comparison", facts=_comparison(current, previous, _period_route("/supplies")))


def compare_sales_periods(from_date, to_date, compare_from_date, compare_to_date, item=None):
    _require_ai_read_access(); (start, end), (old_start, old_end) = _comparison_dates("compare_sales_periods", from_date, to_date, compare_from_date, compare_to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    current = reporting.get_sales_summary(start, end, item_code); previous = reporting.get_sales_summary(old_start, old_end, item_code)
    return _result(source_label="sales_period_comparison", facts=_comparison(current, previous, _period_route("/sales")))


def compare_inventory_periods(from_date, to_date, compare_from_date, compare_to_date, item=None):
    _require_ai_read_access(); (_start, end), (_old_start, old_end) = _comparison_dates("compare_inventory_periods", from_date, to_date, compare_from_date, compare_to_date)
    item_code, ambiguity = _resolve_item(item)
    if ambiguity: return ambiguity
    current = get_inventory_overview(item_code, end).get("summary", {}); previous = get_inventory_overview(item_code, old_end).get("summary", {})
    return _result(source_label="inventory_period_comparison", facts=_comparison(current, previous, _item_route(item_code)))


def compare_expense_periods(from_date, to_date, compare_from_date, compare_to_date):
    _require_ai_read_access(); (start, end), (old_start, old_end) = _comparison_dates("compare_expense_periods", from_date, to_date, compare_from_date, compare_to_date)
    current = reporting.get_expense_summary(start, end); previous = reporting.get_expense_summary(old_start, old_end)
    return _result(source_label="expense_period_comparison", facts=_comparison(current, previous, _period_route("/expenses")))


def list_recent_transactions(from_date=None, to_date=None, limit=25):
    _require_ai_read_access(); from_date, to_date = _report_dates("list_recent_transactions", from_date, to_date); limit = _limit({"limit": limit}, "list_recent_transactions")
    responses = [("supply", supply.list_supplies(date_from=from_date, date_to=to_date, page=1, page_size=limit)), ("sale", sales.list_sales(from_date=from_date, to_date=to_date, page=1, page_size=limit)), ("expense", expenses.list_expenses(from_date=from_date, to_date=to_date, page=1, page_size=limit)), ("payment", supplier_payments.list_supplier_payments(from_date=from_date, to_date=to_date, page=1, page_size=limit))]
    records = []
    for kind, response in responses:
        for row in response.get("data", []): records.append({"id": row["name"], "type": kind, "date": str(row.get("posting_date") or ""), "amount": flt(row.get("total_amount") or row.get("amount") or row.get("paid_amount") or 0), "source": {"route": f"{TRANSACTION_ROUTES[kind]}/{row['name']}", "label": kind}})
    records.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    return _result(source_label="recent_transactions", records=records[:limit])


TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {name: globals()[name] for name in TOOL_POLICIES}
TOOL_ARGUMENTS = {
    "get_operations_summary": {"from_date", "to_date", "item"}, "get_sales_summary": {"from_date", "to_date", "item"}, "get_inventory_snapshot": {"item", "selected_date"}, "get_inventory_movement": {"from_date", "to_date", "item"}, "search_suppliers": {"query", "limit"}, "get_supplier_balance": {"supplier", "from_date", "to_date"}, "get_supplier_statement": {"supplier", "from_date", "to_date", "limit"}, "get_supplier_latest_supply": {"supplier"}, "get_expense_summary": {"from_date", "to_date"}, "list_recent_transactions": {"from_date", "to_date", "limit"},
    "get_supplier_supply_history": {"supplier", "from_date", "to_date", "limit"}, "get_supplier_payment_history": {"supplier", "from_date", "to_date", "limit"}, "compare_supplier_supply_periods": {"supplier", "from_date", "to_date", "compare_from_date", "compare_to_date"}, "list_suppliers_with_balances": {"limit"}, "get_supplier_dues_summary": {"limit"}, "get_supply_summary": {"from_date", "to_date", "item"}, "search_supplies": {"from_date", "to_date", "supplier", "item", "limit"}, "compare_supply_periods": {"from_date", "to_date", "compare_from_date", "compare_to_date", "item"}, "search_sales": {"from_date", "to_date", "item", "buyer", "limit"}, "compare_sales_periods": {"from_date", "to_date", "compare_from_date", "compare_to_date", "item"}, "compare_inventory_periods": {"from_date", "to_date", "compare_from_date", "compare_to_date", "item"}, "search_expenses": {"from_date", "to_date", "limit"}, "compare_expense_periods": {"from_date", "to_date", "compare_from_date", "compare_to_date"},
}
TOOL_REQUIRED = {"search_suppliers": ["query"], "get_supplier_balance": ["supplier"], "get_supplier_statement": ["supplier"], "get_supplier_latest_supply": ["supplier"], "get_supplier_supply_history": ["supplier"], "get_supplier_payment_history": ["supplier"], "compare_supplier_supply_periods": ["supplier", "from_date", "to_date", "compare_from_date", "compare_to_date"], "compare_supply_periods": ["from_date", "to_date", "compare_from_date", "compare_to_date"], "compare_sales_periods": ["from_date", "to_date", "compare_from_date", "compare_to_date"], "compare_inventory_periods": ["from_date", "to_date", "compare_from_date", "compare_to_date"], "compare_expense_periods": ["from_date", "to_date", "compare_from_date", "compare_to_date"]}
TOOL_DESCRIPTIONS = {
    "get_operations_summary": "Read aggregate operations totals for a bounded date period.",
    "get_sales_summary": "Read aggregate submitted sales totals for a bounded date period.",
    "get_inventory_snapshot": "Read current or selected-date inventory quantities and values.",
    "get_inventory_movement": "Read aggregate inventory movement for a bounded date period.",
    "search_suppliers": "Find a supplier by an explicit user-provided name fragment.",
    "get_supplier_balance": "Read one supplier's authoritative balance and period summary.",
    "get_supplier_statement": "Read one supplier's bounded statement entries and outstanding balance.",
    "get_supplier_latest_supply": "Read the latest submitted supply for one explicitly identified supplier.",
    "get_expense_summary": "Read aggregate submitted expense totals for a bounded date period.",
    "list_recent_transactions": "Read a bounded recent operational transaction list.",
    "get_supplier_supply_history": "Read one supplier's bounded supply history with server-calculated period aggregates.",
    "get_supplier_payment_history": "Read one supplier's bounded payment history.",
    "compare_supplier_supply_periods": "Compare server-calculated supply weight and amount totals for one supplier across two explicit periods.",
    "list_suppliers_with_balances": "Read ranked suppliers with outstanding balances and a total outstanding aggregate.",
    "get_supplier_dues_summary": "Read ranked suppliers due summary including the top supplier and total outstanding aggregate.",
    "get_supply_summary": "Read aggregate submitted supply totals for a bounded date period.",
    "search_supplies": "Search bounded submitted supplies by approved supplier, item, and date filters.",
    "compare_supply_periods": "Compare server-calculated supply aggregates between two explicit date periods.",
    "search_sales": "Search bounded submitted sales by approved item, buyer, and date filters.",
    "compare_sales_periods": "Compare server-calculated sales aggregates between two explicit date periods.",
    "compare_inventory_periods": "Compare server-calculated inventory movement aggregates between two explicit date periods.",
    "search_expenses": "Search bounded submitted expenses for an explicit date period.",
    "compare_expense_periods": "Compare server-calculated expense aggregates between two explicit date periods.",
}
TOOL_SCHEMAS = [{"type": "function", "function": {"name": name, "description": TOOL_DESCRIPTIONS[name], "parameters": {"type": "object", "properties": {key: {"type": "integer" if key == "limit" else "string"} for key in sorted(allowed)}, "required": TOOL_REQUIRED.get(name, []), "additionalProperties": False}}} for name, allowed in TOOL_ARGUMENTS.items()]


def execute_tool(name: str, arguments: Mapping[str, Any] | None = None):
    if name not in TOOL_REGISTRY: frappe.throw(_("Unknown AI read tool."), frappe.ValidationError)
    arguments = arguments or {}
    if not isinstance(arguments, Mapping) or set(arguments) - TOOL_ARGUMENTS[name]: frappe.throw(_("Unsupported AI tool arguments."), frappe.ValidationError)
    if any(key not in arguments or arguments[key] in (None, "") for key in TOOL_REQUIRED.get(name, [])): frappe.throw(_("Missing required AI tool arguments."), frappe.ValidationError)
    return TOOL_REGISTRY[name](**dict(arguments))
