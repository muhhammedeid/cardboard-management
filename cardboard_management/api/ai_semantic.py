"""Semantic Business Query contract, registry, and validator (AI V3).

The model never sees SQL, DocType internals, or this module's table names.
It emits a bounded ``SemanticQuery``; this module is the security boundary:
schema validation, domain/field/operation/metric/filter allowlists from the
server-owned registry, period resolution on server time, and row limits.
Nothing here reads the database; entity resolution belongs to the executor.
"""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Mapping

CONTRACT_VERSION = "1"

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ARABIC_MONTHS = ("", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")
PERIOD_TYPES = frozenset({
    "today", "yesterday", "current_week", "previous_week", "current_month",
    "previous_month", "month_to_date", "last_7_days", "last_30_days", "current_year",
})

# ---------------------------------------------------------------- registry --
# Server-owned description of every allowed business query capability.
# aggregation lists are per numeric field; sort lists name valid fields.
DOMAIN_REGISTRY: dict[str, dict[str, Any]] = {
    "suppliers": {
        "operations": ("list", "rank", "get"),
        "fields": (
            "name", "supplier_name", "outstanding", "supply_value",
            "supplied_weight_tons", "supply_count", "payment_count",
        ),
        "numeric_fields": ("outstanding", "supply_value", "supplied_weight_tons", "supply_count", "payment_count"),
        "aggregations": ("sum", "count", "max", "min", "avg"),
        "rank_metrics": ("outstanding", "supply_value"),
        "filters": ("supplier",),
        "sort_fields": ("outstanding", "supply_value", "supplier_name"),
        "default_limit": {"list": 25, "rank": 10, "get": 1},
    },
    "supplies": {
        "operations": ("get", "list", "aggregate"),
        "fields": (
            "date", "net_weight_kg", "payable_weight_kg", "payable_weight_tons",
            "rate_per_kg", "total_amount", "supplier", "item", "source",
        ),
        "numeric_fields": ("net_weight_kg", "payable_weight_kg", "payable_weight_tons", "rate_per_kg", "total_amount"),
        "aggregations": ("sum", "count", "avg", "max", "min"),
        "rank_metrics": (),
        "filters": ("supplier", "item"),
        "sort_fields": ("date", "total_amount", "payable_weight_kg", "payable_weight_tons"),
        "default_limit": {"list": 5, "rank": 10, "get": 1},
    },
    "sales": {
        "operations": ("get", "list", "aggregate"),
        "fields": ("date", "quantity", "rate_per_kg", "total_amount", "item", "buyer_name", "source"),
        "numeric_fields": ("quantity", "rate_per_kg", "total_amount"),
        "aggregations": ("sum", "count", "avg", "max", "min"),
        "rank_metrics": (),
        "filters": ("item", "buyer"),
        "sort_fields": ("date", "total_amount", "quantity"),
        "default_limit": {"list": 5, "rank": 10, "get": 1},
    },
    "inventory": {
        "operations": ("get",),
        "fields": ("item", "item_name", "quantity", "stock_uom", "stock_value"),
        "numeric_fields": ("quantity", "stock_value"),
        "aggregations": ("sum",),
        "rank_metrics": (),
        "filters": ("item",),
        "sort_fields": (),
        "default_limit": {"get": 1, "list": 25, "rank": 10},
    },
    "expenses": {
        "operations": ("get", "list", "aggregate"),
        "fields": ("date", "amount", "expense_account", "account_name", "source"),
        "numeric_fields": ("amount",),
        "aggregations": ("sum", "count", "avg", "max", "min"),
        "rank_metrics": (),
        "filters": ("expense_account",),
        "sort_fields": ("date", "amount"),
        "default_limit": {"list": 5, "rank": 10, "get": 1},
    },
    "payments": {
        "operations": ("get", "list", "aggregate"),
        "fields": ("date", "amount", "mode_of_payment", "supplier", "source"),
        "numeric_fields": ("amount",),
        "aggregations": ("sum", "count", "avg", "max", "min"),
        "rank_metrics": (),
        "filters": ("supplier",),
        "sort_fields": ("date", "amount"),
        "default_limit": {"list": 5, "rank": 10, "get": 1},
    },
}

WRITE_KEYS = frozenset({
    "fields", "filters", "period", "compare_period", "aggregation",
    "group_by", "sort", "limit", "offset", "domain", "operation",
})
PATCH_KEYS = WRITE_KEYS
LIST_LIMIT_MAX = 25
RANK_LIMIT_MAX = 10
OFFSET_MAX = 50
MAX_INTEGER = 10 ** 9  # numeric sanity bound for model-supplied values


class SemanticError(Exception):
    """Stable semantic error; ``code`` is one of the Goal's failure types."""

    def __init__(self, code: str, message_ar: str):
        super().__init__(code)
        self.code = code
        self.message_ar = message_ar


def _bad(code: str, message_ar: str) -> SemanticError:
    return SemanticError(code, message_ar)


# --------------------------------------------------------------- validation --
def _is_period(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    if set(value) - {"type", "from", "to", "name"}:
        return False
    ptype = value.get("type")
    if ptype:
        if not isinstance(ptype, str):
            return False
        if ptype == "month_name":
            return isinstance(value.get("name"), str) and value["name"].strip() in ARABIC_MONTHS
        return ptype in PERIOD_TYPES
        # named explicit-month form below
    return "from" in value and "to" in value and all(isinstance(value[k], str) and _ISO.match(value[k]) for k in ("from", "to"))


def _is_sort(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) <= {"field", "direction"}
        and isinstance(value.get("field"), str)
        and value.get("direction", "desc") in ("asc", "desc")
    )


def _is_filter_map(value: Any) -> bool:
    return isinstance(value, Mapping) and all(
        isinstance(key, str) and isinstance(item, str) and item.strip() for key, item in value.items()
    )


def _is_aggregation(value: Any) -> bool:
    return isinstance(value, Mapping) and all(
        isinstance(key, str) and isinstance(item, str) and item in ("sum", "count", "avg", "max", "min")
        for key, item in value.items()
    )


def _bounded_int(value: Any, low: int, high: int):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _reject_unknown(query: Mapping[str, Any], context: str):
    allowed = {  # top-level writable keys everything may carry
        "version", "domain", "operation", "fields", "filters", "period",
        "compare_period", "aggregation", "group_by", "sort", "limit", "offset",
    }
    unknown = set(query) - allowed
    if unknown:
        raise _bad("INVALID_QUERY", f"{context}: مفاتيح غير مسموحة {sorted(unknown)}")


def validate_query(query: Any) -> dict[str, Any]:
    """Validate one full semantic query against the registry. Returns the
    normalized query or raises SemanticError. Pure — no data access."""
    _reject_unknown(query or {}, "query")
    if not isinstance(query, Mapping):
        raise _bad("INVALID_QUERY", "الاستعلام غير صالح.")
    version = query.get("version", CONTRACT_VERSION)
    if version != CONTRACT_VERSION:
        raise _bad("INVALID_QUERY", "إصدار الاستعلام غير مدعوم.")

    domain = query.get("domain")
    if domain not in DOMAIN_REGISTRY:
        raise _bad("UNSUPPORTED_DOMAIN", "النطاق المطلوب غير مدعوم.")
    spec = DOMAIN_REGISTRY[domain]

    operation = query.get("operation")
    if operation not in spec["operations"]:
        raise _bad("UNSUPPORTED_OPERATION", "العملية ممنوعة على النطاق ده.")

    fields = query.get("fields")
    if fields is not None:
        if not isinstance(fields, list) or not fields or not all(isinstance(f, str) and f for f in fields):
            raise _bad("INVALID_QUERY", "قائمة الحقول غير صالحة.")
        if set(fields) - set(spec["fields"]):
            raise _bad("UNSUPPORTED_FIELD", "حقل أو أكثر غير مدعوم في النطاق ده.")

    filters = query.get("filters") or {}
    if not _is_filter_map(filters):
        raise _bad("INVALID_QUERY", "المرشحات غير صالحة.")
    if set(filters) - set(spec["filters"]):
        raise _bad("UNSUPPORTED_FIELD", "مرشح غير مدعوم في النطاق ده.")

    period = query.get("period")
    if period is not None and not _is_period(period):
        raise _bad("INVALID_PERIOD", "الفترة غير صالحة.")

    compare_period = query.get("compare_period")
    if compare_period is not None and not _is_period(compare_period):
        raise _bad("INVALID_PERIOD", "فترة المقارنة غير صالحة.")
    if compare_period is not None and operation != "compare":
        raise _bad("INVALID_QUERY", "فترة المقارنة مسموحة فقط في المقارنة.")

    if operation == "compare" and not compare_period:
        raise _bad("INVALID_QUERY", "المقارنة تحتاج فترة مقارنة.")

    aggregation = query.get("aggregation") or {}
    if not _is_aggregation(aggregation):
        raise _bad("INVALID_QUERY", "طريقة التجميع غير صالحة.")
    if aggregation:
        if operation != "aggregate":
            raise _bad("INVALID_QUERY", "التجميع مسموح فقط مع عملية aggregate.")
        if set(aggregation) - set(spec["numeric_fields"]):
            raise _bad("UNSUPPORTED_METRIC", "مقياس غير مدعوم للتجميع.")
        bad_ops = [key for key, agg in aggregation.items() if agg not in spec["aggregations"]]
        if bad_ops:
            raise _bad("UNSUPPORTED_METRIC", "نوع تجميع غير مدعوم.")
    if operation == "aggregate" and not aggregation:
        raise _bad("INVALID_QUERY", "عملية aggregate تحتاج تجميعًا محددًا.")

    group_by = query.get("group_by") or []
    if not isinstance(group_by, list) or set(group_by) - {"supplier", "item"}:
        raise _bad("INVALID_QUERY", "تجميد قيم group_by غير صالحة.")
    if group_by and operation not in ("aggregate", "compare"):
        raise _bad("INVALID_QUERY", "group_by مسموح فقط في aggregate/compare.")

    sort = query.get("sort")
    if sort is not None:
        if not _is_sort(sort):
            raise _bad("INVALID_QUERY", "الترتيب غير صالح.")
        if sort["field"] not in spec["sort_fields"]:
            raise _bad("UNSUPPORTED_FIELD", "حقل الترتيب غير مدعوم.")
        if operation == "rank" and sort["field"] not in spec["rank_metrics"]:
            raise _bad("UNSUPPORTED_METRIC", "مقياس الترتيب غير مدعوم.")

    limit = query.get("limit", spec["default_limit"].get(operation, 1))
    if limit is not None and not _bounded_int(limit, 1, LIMIT_FOR(operation)):
        raise _bad("INVALID_QUERY", "حد الصفوف غير مسموح.")
    offset = query.get("offset")
    if offset is not None and not _bounded_int(offset, 0, OFFSET_MAX):
        raise _bad("INVALID_QUERY", "الإزاحة غير مسموحة.")

    if operation == "rank":
        if not sort or sort["field"] not in spec["rank_metrics"] or sort.get("direction") not in ("desc", "asc"):
            raise _bad("INVALID_QUERY", "الترتيب مطلوب للترتيب rank.")
        if not query.get("fields"):
            # ranking returns the metric plus identity columns server-side.
            pass

    resolved = {
        "version": CONTRACT_VERSION,
        "domain": domain,
        "operation": operation,
        "fields": fields,
        "filters": {key: value.strip() for key, value in filters.items()},
        "period": dict(period) if isinstance(period, Mapping) else None,
        "compare_period": dict(compare_period) if isinstance(compare_period, Mapping) else None,
        "aggregation": dict(aggregation) if aggregation else None,
        "group_by": group_by,
        "sort": dict(sort) if isinstance(sort, Mapping) else None,
        "limit": limit,
        "offset": offset or 0,
    }
    return resolved


def LIMIT_FOR(operation: str) -> int:
    return LIST_LIMIT_MAX if operation in ("list", "get", "aggregate") else RANK_LIMIT_MAX


def group_by_present(query: Mapping[str, Any]) -> bool:
    return bool(query.get("group_by"))


def apply_patch(previous: Mapping[str, Any], patch: Any) -> dict[str, Any]:
    """Apply a bounded sparse patch to the last validated query; ALWAYS
    revalidate the merged result. Never mutates the previous mapping."""
    if not isinstance(patch, Mapping) or not patch:
        raise _bad("INVALID_QUERY", "التعديل المطلوب غير صالح.")
    unknown = set(patch) - PATCH_KEYS
    if unknown:
        raise _bad("INVALID_QUERY", f"مفاتيح تعديل غير مسموحة: {sorted(unknown)}")
    merged = dict(previous or {})
    merged.pop("message", None)
    for key, value in patch.items():
        if key in ("domain", "operation") and value not in (None, ""):
            if key == "domain" and value not in DOMAIN_REGISTRY:
                raise _bad("UNSUPPORTED_DOMAIN", "نطاق غير مدعوم.")
            if key == "operation":
                return _renavigate(merged, value)
        merged[key] = value
    return validate_query(merged)


def _renavigate(merged: Mapping[str, Any], new_operation: Any) -> dict[str, Any]:
    candidate = dict(merged)
    candidate.pop("aggregation", None)
    candidate.pop("group_by", None)
    candidate.pop("compare_period", None)
    candidate["operation"] = new_operation
    return validate_query(candidate)


def interpret_output(payload: Any, previous_query: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize one model output into an executable intent:
    ``new_query`` | ``query_patch`` | ``clarify`` | ``refuse``."""
    if not isinstance(payload, Mapping):
        raise _bad("INVALID_QUERY", "تعذر فهم طلب المساعد.")
    output_type = payload.get("type")
    if output_type == "new_query":
        query = payload.get("query")
        if not isinstance(query, Mapping):
            raise _bad("INVALID_QUERY", "استعلام غير صالح.")
        return {"type": "new_query", "query": validate_query(query)}
    if output_type == "query_patch":
        patch = payload.get("patch")
        if previous_query is None:
            raise _bad("INVALID_QUERY", "لا يوجد استعلام سابق لتعديله.")
        return {"type": "query_patch", "query": apply_patch(previous_query, patch), "patch": dict(patch)}
    if output_type == "clarify":
        question = str(payload.get("question") or "").strip()[:300]
        if not question:
            return {"type": "clarify", "question": "ممكن توضح السؤال؟"}
        return {"type": "clarify", "question": question}
    if output_type == "refuse":
        return {"type": "refuse", "reason": str(payload.get("reason") or "out_of_scope")[:60]}
    raise _bad("INVALID_QUERY", "تعذر تفسير نوع الطلب.")
