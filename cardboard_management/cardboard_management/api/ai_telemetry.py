"""Safe operational telemetry for the AI assistant; no conversational data."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import frappe

SAFE_FIELDS = frozenset({
    "model", "provider", "status", "tool_count", "input_tokens", "output_tokens",
    "estimated_cost_usd", "planner_latency_ms", "tool_latency_ms", "final_answer_latency_ms",
    "stt_latency_ms", "tts_latency_ms", "total_latency_ms", "delivery_mode", "error_code",
    "recording_duration_ms", "recording_byte_size", "browser_mime", "normalized_mime",
    "multipart_filename_extension", "stt_http_status", "transcript_character_count",
    "stt_language_hint_present", "stt_model", "correlation_id", "stage", "selected_tool",
    "tool_step", "argument_validation", "termination_reason", "planner_latency_ms",
    "tool_latency_ms", "final_latency_ms",
})


def record(event: str, telemetry: Mapping[str, Any] | None = None) -> None:
    """Emit allowlisted metrics only; never prompt, answer, DTO, identity, or audio."""
    payload = {key: value for key, value in dict(telemetry or {}).items() if key in SAFE_FIELDS}
    payload["event"] = event
    frappe.logger("cardboard_ai").info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
