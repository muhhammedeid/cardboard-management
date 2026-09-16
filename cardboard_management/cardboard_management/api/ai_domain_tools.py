""""AI-facing domain query tools (V3).

The model sees exactly six coherent domain tools over the shared semantic
query contract. There is no path to SQL, generic DocType access, arbitrary
Frappe methods, or the raw services from the model surface.
"""
from __future__ import annotations

from typing import Any, Mapping

from cardboard_management.cardboard_management.api.ai_query_engine import (
    execute_query as _engine_execute_query,
)
from cardboard_management.cardboard_management.api.ai_semantic import (
    CONTRACT_VERSION,
    DOMAIN_REGISTRY,
    SemanticError,
    LIMIT_FOR,
    LIST_LIMIT_MAX,
    RANK_LIMIT_MAX,
    validate_query,
)

TOOL_NAMES = ("query_suppliers", "query_supplies", "query_sales", "query_inventory", "query_expenses", "query_payments")
_DOMAIN_BY_TOOL = {f"query_{domain}": domain for domain in DOMAIN_REGISTRY}


def tool_schemas() -> list[dict[str, Any]]:
    """OpenAI-function JSON schemas published to DeepSeek for the 6 tools."""
    schemas = []
    for name in TOOL_NAMES:
        domain = _DOMAIN_BY_TOOL[name]
        spec = DOMAIN_REGISTRY[domain]
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "object", "description": "Semantic query for the __domain__ domain."}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        })
    return schemas


def execute_tool(name: str, arguments: Mapping[str, Any] | None = None):
    """Dispatch one model-chosen domain tool through the bounded engine."""
    if name not in TOOL_NAMES:
        raise SemanticError("UNSUPPORTED_OPERATION", "أداة غير معروفة.")
    arguments = arguments or {}
    query = arguments.get("query")
    if not isinstance(query, Mapping):
        raise SemanticError("INVALID_QUERY", "استعلام غير صالح.")
    query = dict(query)
    query.setdefault("domain", _DOMAIN_BY_TOOL[name])
    query.setdefault("version", CONTRACT_VERSION)
    return _engine_execute_query(query)


def execute_query(query: Mapping[str, Any]):
    """Direct server-side path for tests and the orchestrator's patch flow."""
    return _engine_execute_query(query)
