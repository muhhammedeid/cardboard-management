"""Business Query Engine for the Semantic layer (AI V3).

Executes one *validated* semantic query through the existing trusted
Cardboard/ERP read services and returns an authoritative result DTO
(facts, records, disambiguation, sources). Entity resolution, period
resolution, aggregation, ranking, comparison, and unit conversion are all
server-owned. This module never trusts the model beyond the validated query.
"""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from cardboard_management import reporting
from cardboard_management.cardboard_management.api import expenses, sales, supplier_payments, supply
from cardboard_management.cardboard_management.api.ai_semantic import (
    CONTRACT_VERSION,
    SemanticError,
    validate_query,
)
from cardboard_management.inventory import get_inventory_context, get_inventory_overview

AI_READ_ROLES = frozenset({"Cardboard Manager", "Cardboard Operator"})
MAX_DISAMBIGUATION = 5

_ARABIC_MARKS = re.compile(r"[\u064b-\u065f\u0670]")
_ARABIC_NORMALIZE = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"})
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_MONTH_NAME_TO_NUMBER = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5, "يونيو": 6,
    "يوليو": 7, "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10,
    "نوفمبر": 11, "ديسمبر": 12,
}


def _normalize(value: Any) -> str:
    return _ARABIC_MARKS.sub("", str(value or "")).translate(_ARABIC_NORMALIZE).casefold()


def _clean_text(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(value or ""))).strip()[:limit]


def _display_number(value: float) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:g}"


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


def require_ai_read_access():
    if frappe.session.user == "Guest":
        frappe.throw(_("يلزم تسجيل الدخول لاستخدام مساعد البيانات."), frappe.AuthenticationError)
    if not AI_READ_ROLES.intersection(frappe.get_roles(frappe.session.user)):
        frappe.throw(_("مش مسموح لي أعرض البيانات دي لحسابك."), frappe.PermissionError)
    frappe.has_permission("Cardboard Dashboard Settings", "read", throw=True)


# ------------------------------------------------------------ period dates --
def resolve_period_dates(period: Mapping[str, Any] | None, *, today: str | date | None = None) -> tuple[str, str | None]:
    """Resolve one validated period spec to server dates.

    Returns ``(from_date, to_date)``; ``to_date is None`` means "to today"
    (month_to_date / open aggregates). Validates: no future dates.
    """
    day = date.fromisoformat(today) if isinstance(today, str) else (today or getdate(nowdate()))
    if not period:
        return None, None
    ptype = period.get("type")
    if ptype == "today":
        return day.isoformat(), day.isoformat()
    if ptype == "yesterday":
        y = day - timedelta(days=1)
        return y.isoformat(), y.isoformat()
    if ptype == "last_7_days":
        return (day - timedelta(days=6)).isoformat(), day.isoformat()
    if ptype == "last_30_days":
        return (day - timedelta(days=29)).isoformat(), day.isoformat()
    if ptype in ("current_month", "month_to_date"):
        start = date(day.year, day.month, 1)
        return start.isoformat(), day.isoformat()
    if ptype == "previous_month":
        if day.month == 1:
            start = date(day.year - 1, 12, 1)
        else:
            start = date(day.year, day.month - 1, 1)
        end = date(day.year, day.month, 1) - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    if ptype == "current_week":  # operational weeks run Saturday..Friday
        start = day - timedelta(days=(day.weekday() + 2) % 7)
        return start.isoformat(), day.isoformat()
    if ptype == "previous_week":
        start = day - timedelta(days=(day.weekday() + 2) % 7 + 7)
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if ptype == "current_year":
        return date(day.year, 1, 1).isoformat(), day.isoformat()
    if ptype == "month_name":
        number = _MONTH_NAME_TO_NUMBER[_normalize(period.get("name"))]
        year = day.year
        if number > day.month:
            # The latest completed month with this name in the past.
            year -= 1
        start = date(year, number, 1)
        end = date(year + (number == 12), 1 if number == 12 else number + 1, 1) - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    if "from" in period and "to" in period:
        start, end = getdate(period["from"]), getdate(period["to"])
        if start > end or end > getdate(nowdate()):
            raise SemanticError("INVALID_PERIOD", "الفترة المطلوبة غير مسموحة.")
        if end - start > timedelta(days=3660):
            raise SemanticError("INVALID_PERIOD", "الفترة أطول من الحد المسموح.")
        return period["from"], period["to"]
    raise SemanticError("INVALID_PERIOD", "الفترة غير معروفة.")


# -------------------------------------------------------- entity resolution --
def resolve_supplier(text: str):
    """Backend-owned entity resolution with Arabic normalization.

    Returns ``(supplier_id, ambiguity_records)``; ambiguity_records is a
    candidates list when 0 matches -> ENTITY_NOT_FOUND (empty) or multiple
    matches -> clarification candidates (non-empty, >1)."""
    query = _clean_text(text)
    if not query:
        return None, []
    needle = _normalize(query)
    rows = frappe.get_list(
        "Supplier",
        filters={"disabled": 0},
        fields=["name", "supplier_name"],
        order_by="supplier_name asc, name asc",
        limit_page_length=200,
    )
    matches = []
    for row in rows:
        if needle in _normalize(row.supplier_name or row.name) or needle in _normalize(row.name):
            matches.append(row)
    if len(matches) == 1:
        return matches[0].name, []
    if len(matches) > 1:
        candidates = [
            {"id": row.name, "label": _clean_text(row.supplier_name or row.name),
             "source": {"route": f"/suppliers/{row.name}", "label": "Supplier"}}
            for row in matches[:MAX_DISAMBIGUATION]
        ]
        return None, candidates
    raise SemanticError("ENTITY_NOT_FOUND", f"مفيش مورد بالاسم ده: {query}.")


def _resolve_item(text: str | None):
    if not text:
        return None, []
    needle = _normalize(text)
    matches = [
        item for item in get_inventory_context()["items"]
        if needle in _normalize(item.item_name or item.name) or needle in _normalize(item.name)
    ]
    if len(matches) == 1:
        return matches[0].name, []
    if len(matches) > 1:
        return None, [
            {"id": item.name, "label": _clean_text(item.item_name or item.name),
             "source": {"route": f"/inventory?item={item.name}", "label": "Inventory"}}
            for item in matches[:MAX_DISAMBIGUATION]
        ]
    raise SemanticError("ENTITY_NOT_FOUND", f"مفيش صنف بالاسم ده: {text}.")


def _supplier_route(name: str):
    return {"route": f"/suppliers/{name}", "label": "Supplier"}


def _supply_route(name: str):
    return {"route": f"/supplies/{name}", "label": "Supply"}


def _sale_route(name: str):
    return {"route": f"/sales/{name}", "label": "Sale"}


def _expense_route(name: str):
    return {"route": f"/expenses/{name}", "label": "Expense"}


def _payment_route(name: str):
    return {"route": f"/payments/{name}", "label": "Payment"}


def _tons(kg: float) -> float:
    return float((Decimal(str(flt(kg))) / Decimal("1000")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _ambiguity(candidates: list[dict[str, str]], label: str = "entity_resolution"):
    return {
        "status": "ambiguity", "facts": [], "records": [],
        "disambiguation": candidates, "source_label": label,
    }


# ------------------------------------------------------------------ engine --
def execute_query(query: Mapping[str, Any]) -> dict[str, Any]:
    """Validate && run one semantic query. The ONLY execution entry point."""
    require_ai_read_access()
    query = validate_query(query)
    domain = query["domain"]

    from_dt, to_dt = resolve_period_dates(query.get("period"))
    filters = dict(query.get("filters") or {})

    supplier_id, supplier_candidates = (None, [])
    if "supplier" in filters:
        supplier_id, supplier_candidates = resolve_supplier(filters["supplier"])
        if supplier_candidates:
            return _ambiguity(supplier_candidates, "supplier_resolution")
    item_id, item_candidates = (None, [])
    if "item" in filters:
        item_id, item_candidates = _resolve_item(filters["item"])
        if item_candidates:
            return _ambiguity(item_candidates, "item_resolution")

    engine = _EXECUTORS.get(query["domain"])
    if engine is None:
        raise SemanticError("UNSUPPORTED_DOMAIN", "النطاق مفقود.")
    return engine(query, filters, from_dt, to_dt, supplier_id, item_id)


def _supplier_supplied_weight_tons(payload: Mapping[str, Any]) -> float:
    return _tons(payload.get("supplied_payable_weight", 0))


def _run_suppliers(query, filters, from_dt, to_dt, supplier_id, item_id):
    operation = query["operation"]
    if operation == "get" and query.get("fields"):
        pass  # fields included below
    if operation == "get":
        if not supplier_id:
            raise SemanticError("ENTITY_NOT_FOUND", "حدد مورد أولًا.")
        payload = reporting.get_supplier_summary(supplier_id, from_dt, to_dt)
        route = _supplier_route(supplier_id)
        facts = [
            _fact("outstanding", flt(payload.get("outstanding")), route, currency="EGP"),
            _fact("supply_value", flt(payload.get("supply_value")), route, currency="EGP"),
            _fact("supplied_weight_tons", _supplier_supplied_weight_tons(payload), route, unit="Ton"),
            _fact("supply_count", payload.get("supply_count", 0), route),
        ]
        records = [{"id": payload["supplier"]["name"], "label": _clean_text(payload["supplier"]["supplier_name"]),
                    "supplier_name": _clean_text(payload["supplier"]["supplier_name"]), "source": route}]
        return {"status": "ok", "facts": facts, "records": records, "disambiguation": [], "source_label": "supplier_balance"}

    if operation == "rank":
        metric = (query.get("sort") or {}).get("field")
        direction = (query.get("sort") or {}).get("direction", "desc")
        payload = reporting.get_outstanding_report()
        rows = list(payload.get("suppliers", []))
        if metric == "supply_value":
            rows.sort(key=lambda row: (flt(row["supply_value"]), flt(row["outstanding"])), reverse=(direction == "desc"))
        else:  # outstanding is the default metric
            rows.sort(key=lambda row: (flt(row["outstanding"]), flt(row["supply_value"])), reverse=(direction == "desc"))
        limit = cint(query.get("limit")) or 10
        records, facts = [], []
        for position, row in enumerate(rows[:limit], start=1):
            value = flt(row["outstanding"] if metric == "outstanding" else row["supply_value"])
            if value <= 0:
                break
            route = _supplier_route(row["supplier"])
            records.append({
                "id": row["supplier"], "rank": position, "label": _clean_text(row["supplier_name"]),
                "metric": metric, "value": value, "source": route,
            })
            facts.append(_fact(f"record.{row['supplier']}.{metric}", value, route, currency="EGP"))
        if not records and metric == "outstanding":
            pass  # genuine 'everyone paid up' NO_DATA answerable below
        if not records:
            raise SemanticError("NO_DATA", "مفيش موردين بمستحقات ظاهرة دلوقتي.")
        facts.append(_fact("total_outstanding", flt(payload.get("total_outstanding")), _supplier_route("suppliers"), currency="EGP"))
        return {"status": "ok", "facts": facts, "records": records, "disambiguation": [], "source_label": "supplier_ranking"}

    # list
    payload = reporting.get_outstanding_report()
    rows = payload.get("suppliers", [])
    records = []
    for row in rows[: cint(query.get("limit")) or 25]:
        records.append({
            "id": row["supplier"], "label": _clean_text(row["supplier_name"]),
            "outstanding": flt(row["outstanding"]), "supply_value": flt(row["supply_value"]),
            "source": _supplier_route(row["supplier"]),
        })
    return {
        "status": "ok",
        "facts": [_fact("total_outstanding", flt(payload.get("total_outstanding")), _supplier_route(str(rows[0].get("supplier") if rows else "suppliers")), currency="EGP") if records else _fact("total_outstanding", 0.0, {"route": "/suppliers", "label": "Suppliers"}, currency="EGP")],
        "records": records, "disambiguation": [], "source_label": "supplier_list",
    }


def _supply_history_rows(supplier_id, from_dt, to_dt, limit):
    summary = reporting.get_supplier_summary(supplier_id, from_dt, to_dt)
    rows = summary.get("supply_history", [])
    return summary, rows[:limit]


def _run_supplies(query, filters, from_dt, to_dt, supplier_id, item_id):
    operation = query["operation"]
    fields = set(query.get("fields") or [])
    limit = cint(query.get("limit")) or 5
    offset = cint(query.get("offset")) or 0

    if supplier_id and operation in ("list", "get"):
        summary, rows = _supply_history_rows(supplier_id, from_dt, to_dt, limit + offset)
        window = rows[offset: offset + limit]
        records = [_supply_record(row["supply"], row, _supply_route(row["supply"])) for row in window]
        facts = []
        if records:
            facts.append(_fact("count", len(summary.get("supply_history", [])), _supply_route(str(rows[0]["supply"] if rows else "supplies"))))
        if not records:
            raise SemanticError("NO_DATA", "مفيش توريدات في الفترة دي.")
        return {"status": "ok", "facts": facts, "records": records, "disambiguation": [], "source_label": "supplier_supply_history"}

    # Period aggregates for supplies as a whole / per supplier
    payload = reporting.get_operations_summary(from_dt, to_dt, item_id).get("supplies", {})
    route = {"route": "/supplies", "label": "Supplies"}
    kg_rows = {
        "net_weight_kg": flt(payload.get("quantity", 0)),
        "payable_weight_kg": flt(payload.get("payable_weight", 0)),
        "total_amount": flt(payload.get("value", 0)),
        "count": payload.get("count", 0),
    }
    kg_rows["payable_weight_tons"] = _tons(kg_rows["payable_weight_kg"])
    facts = []
    for field, agg in (query.get("aggregation") or {}).items():
        if agg == "sum":
            if field == "payable_weight_tons":
                facts.append(_fact(f"total.{field}", kg_rows["payable_weight_tons"], route, unit="Ton"))
            elif field == "payable_weight_kg":
                facts.append(_fact(f"total.{field}", kg_rows["payable_weight_kg"], route, unit="Kg"))
            elif field == "net_weight_kg":
                facts.append(_fact(f"total.{field}", kg_rows["net_weight_kg"], route, unit="Kg"))
            elif field == "total_amount":
                facts.append(_fact(f"total.{field}", kg_rows["total_amount"], route, currency="EGP"))
        elif agg == "count":
            facts.append(_fact("total.count", kg_rows["count"], route))
        elif agg == "avg" and kg_rows["count"]:
            source_field = {"payable_weight_kg": "payable_weight_kg", "payable_weight_tons": "payable_weight_kg", "net_weight_kg": "net_weight_kg", "total_amount": "total_amount"}[field]
            facts.append(_fact(f"average.{field}", flt(kg_rows[source_field]) / kg_rows["count"], route))
    return {"status": "ok", "facts": facts, "records": [], "disambiguation": [], "source_label": "supply_period_totals"}


def _supply_record(name: str, row: Mapping[str, Any], source: dict[str, str]):
    return {
        "id": name, "type": "supply", "date": row["posting_date"], "item": row["item"],
        "supplier": None, "label": _clean_text(row["item_name"]), "amount": flt(row["value"]),
        "payable_weight_kg": flt(row["payable_weight"]), "source": source,
    }


def _run_sales(query, filters, from_dt, to_dt, supplier_id, item_id):
    operation = query["operation"]
    limit = cint(query.get("limit")) or 5
    if operation in ("list", "get") and item_id is None:
        item_id = None
    payload = reporting.get_sales_summary(from_dt, to_dt, item_id) if operation in ("list", "get") else None
    route = {"route": "/sales", "label": "Sales"}
    if operation == "aggregate":
        payload = reporting.get_sales_summary(from_dt, to_dt, item_id)
        facts = []
        for field, agg in (query.get("aggregation") or {}).items():
            if agg == "sum" and field == "total_amount":
                facts.append(_fact("total.total_amount", flt(payload.get("total_informational_value")), route, currency="EGP"))
            elif agg == "sum" and field == "quantity":
                facts.append(_fact("total.quantity", flt(payload.get("total_quantity")), route, unit="Kg"))
            elif agg == "count":
                facts.append(_fact("total.count", payload.get("sale_count"), route))
        return {"status": "ok", "facts": facts, "records": [], "disambiguation": [], "source_label": "sales_period_totals"}
    return {
        "status": "ok",
        "facts": [_fact("total_matches", payload.get("sale_count"), route)],
        "records": [_sale_record(item, route) for item in (payload.get("by_item", [])[:limit])],
        "disambiguation": [], "source_label": "sales_summary",
    }


def _sale_record(row: Mapping[str, Any], route: dict[str, str]):
    return {"id": row["item"], "type": "sale", "label": _clean_text(row["item_name"]), "quantity": flt(row["quantity"]), "amount": flt(row["value"]), "count": row["count"], "source": route}


def _run_inventory(query, filters, from_dt, to_dt, supplier_id, item_id):
    # inventory op is get; snapshot via the stock read model.
    from cardboard_management.inventory import get_inventory_overview
    selected = to_dt
    overview = get_inventory_overview(item_id, selected)
    route = _item_route(item_id)
    facts, records = [], []
    if overview.get("rows"):
        for row in overview["rows"][:25]:
            rec_route = _item_route(row["item_code"])
            records.append({
                "id": row["item_code"], "label": _clean_text(row["item_name"]),
                "quantity": flt(row["quantity"]), "uom": row["stock_uom"],
                "stock_value": flt(row["stock_value"]), "source": rec_route,
            })
            facts.append(_fact(f"item.{row['item_code']}.quantity", flt(row["quantity"]), rec_route, unit=row["stock_uom"]))
            facts.append(_fact(f"item.{row['item_code']}.stock_value", flt(row["stock_value"]), rec_route, currency="EGP"))
        summary = overview.get("summary", {})
        if summary.get("quantity") is not None:
            facts.append(_fact("total.quantity", flt(summary["quantity"]), route, unit=summary.get("uom")))
        facts.append(_fact("total.stock_value", flt(summary.get("stock_value", 0)), route, currency="EGP"))
    else:
        raise SemanticError("NO_DATA", "مفيش مخزون ظاهر للفترة دي.")
    return {"status": "ok", "facts": facts, "records": records, "disambiguation": [], "source_label": "inventory_snapshot"}


def _item_route(item_code: str | None):
    return {"route": "/inventory" + (f"?item={item_code}" if item_code else ""), "label": "Inventory"}


def _run_expenses(query, filters, from_dt, to_dt, supplier_id, item_id):
    payload = reporting.get_expense_summary(from_dt, to_dt)
    route = {"route": "/expenses", "label": "Expenses"}
    facts = []
    for field, agg in (query.get("aggregation") or {}).items():
        if field != "amount":
            continue
        if agg == "sum":
            facts.append(_fact("total.amount", flt(payload.get("total_expense_amount")), route, currency="EGP"))
        elif agg == "count":
            facts.append(_fact("total.count", payload.get("expense_count"), route))
    if not facts and query["operation"] in ("list", "get"):
        for row in payload.get("by_account", [])[: cint(query.get("limit")) or 5]:
            account_route = dict(route, route=f"/expenses?account={row['account']}")
            facts.extend([
                _fact(f"account.{row['account']}.amount", flt(row["amount"]), account_route, currency="EGP"),
                _fact(f"account.{row['account']}.count", row["count"], account_route),
            ])
    records = [
        {
            "id": row["account"], "type": "expense", "label": _clean_text(row["account_name"]),
            "amount": flt(row["amount"]), "count": row["count"], "source": dict(route, route=f"/expenses?account={row['account']}"),
        }
        for row in payload.get("by_account", [])[: cint(query.get("limit")) or 5]
    ]
    return {"status": "ok", "facts": facts, "records": records, "disambiguation": [], "source_label": "expense_summary"}




def _run_payments(query, filters, from_dt, to_dt, supplier_id, item_id):
    from datetime import datetime
    payload = reporting.get_supplier_summary(supplier_id, from_dt, to_dt) if supplier_id else None
    route = _supplier_route(supplier_id) if supplier_id else {"route": "/payments", "label": "Payments"}
    if supplier_id:
        rows = payload.get("payment_history", [])[: cint(query.get("limit")) or 5]
        if not rows:
            raise SemanticError("NO_DATA", "مفيش دفعات مسجلة للمورد ده في الفترة دي.")
        records = [{
            "id": row["payment"], "type": "payment", "date": row["posting_date"],
            "label": _clean_text(row.get("mode_of_payment")), "amount": flt(row["amount"]),
            "source": _payment_route(row["payment"]),
        } for row in rows]
        facts = [
            _fact("supplied_total_amount", flt(sum(flt(row["amount"]) for row in rows)), _supplier_route(supplier_id), currency="EGP"),
        ]
        facts.extend(_fact(f"record.{row['id']}.amount", flt(row["amount"]), _payment_route(row["id"]), currency="EGP") for row in records)
        return {"status": "ok", "facts": facts, "records": records, "disambiguation": [], "source_label": "supplier_payment_history"}
    raise SemanticError("ENTITY_NOT_FOUND", "حدد موردًا لعرض دفعاته.")


_EXECUTORS = {
    "suppliers": _run_suppliers,
    "supplies": _run_supplies,
    "sales": _run_sales,
    "inventory": _run_inventory,
    "expenses": _run_expenses,
    "payments": _run_payments,
}
