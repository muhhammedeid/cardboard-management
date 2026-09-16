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
        "operations": ("get", "list", "aggregate", "compare"),
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
        "operations": ("get", "list", "aggregate", "compare"),
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
        "operations": ("get", "list", "aggregate", "compare"),
        "fields": ("date", "amount", "expense_account", "account_name", "source"),
        "numeric_fields": ("amount",),
        "aggregations": ("sum", "count", "avg", "max", "min"),
        "rank_metrics": (),
        "filters": ("expense_account",),
        "sort_fields": ("date", "amount"),
        "default_limit": {"list": 5, "rank": 10, "get": 1},
    },
    "payments": {
        "operations": ("get", "list", "aggregate", "compare"),
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
    if not isinstance(query, Mapping):
        raise _bad("INVALID_QUERY", "الاستعلام غير صالح.")
    _reject_unknown(query, "query")
    version = query.get("version", CONTRACT_VERSION)
    if version != CONTRACT_VERSION:
        raise _bad("INVALID_QUERY", "إصدار الاستعلام غير مدعوم.")

    domain = query.get("domain")
    if domain not in DOMAIN_REGISTRY:
        raise _bad("UNSUPPORTED_DOMAIN", "النطاق المطلوب غير مدعوم.")
    spec = DOMAIN_REGISTRY[domain]

    operation = query.get("operation")
    if operation not in spec["operations"]:
        if operation == "aggregate" and spec.get("numeric_fields"):
            raise _bad("UNSUPPORTED_METRIC", "التجميع مش متاح بالمقاييس دي في النطاق ده.")
        if operation == "rank" and spec.get("rank_metrics"):
            raise _bad("UNSUPPORTED_METRIC", "مقياس الترتيب ده غير متاح في النطاق ده.")
        raise _bad("UNSUPPORTED_OPERATION", "العملية ممنوعة على النطاق ده.")

    fields = query.get("fields")
    if fields is not None:
        if not isinstance(fields, list) or not all(isinstance(f, str) and f for f in fields):
            raise _bad("INVALID_QUERY", "قائمة الحقول غير صالحة.")
        if fields:
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
    if isinstance(period, Mapping) and period.get("from") and period.get("to") and str(period["from"]) > str(period["to"]):
        raise _bad("INVALID_PERIOD", "الفترة الصريحة معكوسة.")

    compare_period = query.get("compare_period")
    if compare_period is not None and not _is_period(compare_period):
        raise _bad("INVALID_PERIOD", "فترة المقارنة غير صالحة.")
    if compare_period is not None and operation != "compare":
        raise _bad("INVALID_QUERY", "فترة المقارنة مسموحة فقط في المقارنة.")

    if operation == "compare" and not compare_period:
        raise _bad("INVALID_QUERY", "المقارنة تحتاج فترة مقارنة.")

    aggregation = query.get("aggregation") or {}
    if not _is_aggregation(aggregation):
        from cardboard_management.cardboard_management.api.ai_semantic import SemanticError as _se
        unsupported_ops = [name for name, agg in (aggregation or {}).items()
                           if isinstance(name, str) and isinstance(agg, str) and agg not in ("sum", "count", "avg", "max", "min")]
        if unsupported_ops and all(k in spec["numeric_fields"] for k in (aggregation or {})):
            raise _bad("UNSUPPORTED_METRIC", "نوع التجميع غير مدعوم.")
        raise _bad("INVALID_QUERY", "طريقة التجميع غير صالحة.")
    if aggregation:
        if operation not in ("aggregate", "compare"):
            raise _bad("INVALID_QUERY", "التجميع مسموح فقط مع عملية aggregate أو compare.")
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
    if previous is None:
        raise _bad("INVALID_QUERY", "لا يوجد استعلام سابق لتعديله.")
    if isinstance(patch, Mapping) and not patch:
        # Empty patch: nothing to change. Revalidate and re-execute the stored query.
        return validate_query(previous)
    unknown = set(patch) - PATCH_KEYS
    if unknown:
        raise _bad("INVALID_QUERY", f"مفاتيح تعديل غير مسموحة: {sorted(unknown)}")
    if previous is None:
        raise _bad("INVALID_QUERY", "لا يوجد استعلام سابق لتعديله.")
    merged = dict(previous)
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
    ``new_query`` | ``query_patch`` | ``clarify`` | ``refuse``.

    Canonical envelope: {"type": "new_query"|"query_patch"|"clarify"|"refuse", ...}.
    A bare query mapping without the envelope (model omission) binds as a new query.
    """
    if isinstance(payload, Mapping):
        top_query_keys = {"version", "domain", "operation", "fields", "filters", "period", "aggregation", "sort", "limit", "offset", "group_by"}
        if "type" not in payload and any(key in payload for key in ("domain", "operation")):
            payload = {"type": "new_query", "query": {k: v for k, v in payload.items()}}
        elif payload.get("type") == "new_query" and not isinstance(payload.get("query"), Mapping) and (top_query_keys & set(payload)):
            query_part = {k: v for k, v in payload.items() if k not in ("type", "patch", "question", "reason")}
            payload = {"type": "new_query", "query": query_part}
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

# --------------------------------------------------- canonical model schema --
def semantic_output_schema() -> dict[str, Any]:
    """THE canonical structured-output schema for the DeepSeek interpreter.

    Generated from the same constants that drive the validator, so the
    model-facing schema and the server validation can never drift apart.
    The model returns one of: new_query | query_patch | clarify | refuse.
    """
    domains = sorted(DOMAIN_REGISTRY)
    operations = sorted({op for spec in DOMAIN_REGISTRY.values() for op in spec["operations"]}) + "rank".split()
    all_operations = sorted(set(op for spec in DOMAIN_REGISTRY.values() for op in spec["operations"]))
    query_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "version": {"type": "string", "enum": [CONTRACT_VERSION]},
            "domain": {"type": "string", "enum": domains},
            "operation": {"type": "string", "enum": sorted({op for spec in DOMAIN_REGISTRY.values() for op in spec["operations"]})},
            "fields": {"type": "array", "items": {"type": "string", "enum": sorted({f for spec in DOMAIN_REGISTRY.values() for f in spec["fields"]})}},
            "filters": {
                "type": "object",
                "properties": {
                    "supplier": {"type": "string"},
                    "item": {"type": "string"},
                    "buyer": {"type": "string"},
                    "expense_account": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "period": {"$ref": "#/$defs/period"},
            "compare_period": {"$ref": "#/$defs/period"},
            "aggregation": {"type": "object"},
            "group_by": {"type": "array", "items": {"type": "string", "enum": ["supplier", "item"]}},
            "sort": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": sorted({f for spec in DOMAIN_REGISTRY.values() for f in spec["sort_fields"]})},
                    "direction": {"type": "string", "enum": ["asc", "desc"]},
                },
                "additionalProperties": False,
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            "offset": {"type": "integer", "minimum": 0, "maximum": 50},
        },
        "$defs": {
            "period": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": sorted(PERIOD_TYPES) + ["month_name"]},
                            "name": {"type": "string", "enum": [m for m in ARABIC_MONTHS if m]},
                        },
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                            "to": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        },
                        "required": ["from", "to"],
                        "additionalProperties": False,
                    },
                ],
            },
        },
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "semantic_output",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["new_query", "query_patch", "clarify", "refuse"]},
                    "query": query_schema,
                    "patch": {"type": "object"},
                    "question": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["type"],
                "additionalProperties": False,
            },
        },
    }


def period_type_list() -> list[str]:
    return sorted(PERIOD_TYPES) + ["month_name"]
