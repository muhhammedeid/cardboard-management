"""Bounded server-side conversational state for AI V3.

Stores primarily the last *validated* semantic query (plus bounded entity
references). No raw business values, no transcripts. Follow-up turns are
QUERY_PATCHes against last_semantic_query; the merged query is revalidated
by ai_semantic before execution.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import frappe

STATE_VERSION = 3
QUERY_MAX_CHARS = 2000


def empty_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "last_semantic_query": None,
        "last_resolved_entities": {},
    }


def _clean_state(value: Any) -> dict[str, Any]:
    base = empty_state()
    if not isinstance(value, Mapping):
        return base
    query = value.get("last_semantic_query")
    if isinstance(query, Mapping):
        try:
            from cardboard_management.cardboard_management.api.ai_semantic import validate_query
            base["last_semantic_query"] = validate_query(_budget_query(query))
        except Exception:
            base["last_semantic_query"] = None
    entities = value.get("last_resolved_entities")
    if isinstance(entities, Mapping):
        base["last_resolved_entities"] = {
            key: str(item)[:140] for key, item in entities.items()
            if key in {"supplier", "item", "supplier_id", "item_id"} and isinstance(item, str) and item.strip()
        }
    return base


def _budget_query(query: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(query)
    filters = dict(cleaned.get("filters") or {})
    for key, value in filters.items():
        filters[key] = str(value)[:140]
    cleaned["filters"] = filters
    return cleaned


def _cache_key() -> str:
    sid = str(getattr(frappe.session, "sid", "") or frappe.session.user)
    return f"cardboard_ai_v3_state:{frappe.session.user}:{sid}"


def load_state() -> dict[str, Any]:
    try:
        return _clean_state(frappe.cache().get_value(_cache_key()))
    except (AttributeError, TypeError):
        return empty_state()


def save_state(state: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = _clean_state(state)
    try:
        frappe.cache().set_value(_cache_key(), cleaned, expires_in_sec=8 * 60 * 60)
    except (AttributeError, TypeError):
        pass
    return cleaned


def semantic_prompt(state: Mapping[str, Any]) -> str:
    """Compact, value-free echo of the previous query for tool prompts (unused
    by chat; kept for semantics-completeness and tests)."""
    clean = _clean_state(state)
    query = clean.get("last_semantic_query")
    if not isinstance(query, Mapping):
        return ""
    return "previous semantic query: " + str({
        "domain": query.get("domain"),
        "operation": query.get("operation"),
        "period": query.get("period"),
        "fields": query.get("fields"),
    })
