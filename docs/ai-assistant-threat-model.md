# AI Read-Only Assistant Threat Model

## Trust model

The model is an untrusted language interface. Cardboard/ERPNext services are the sole source of truth. All tools are server-owned, schema-validated read tools; no tool registry entry may mutate state.

| Asset / entry point | Threat | Mandatory control | Evidence / failure behavior |
|---|---|---|---|
| User message | Prompt injection, arbitrary tool/method/SQL request | Immutable system instructions, strict tool registry, server schemas | Refuse safely; never execute a named method or raw SQL. |
| Stored supplier/item/note/reference/comment/imported text | stored prompt injection | Treat as untrusted data, narrow DTOs, sanitize HTML, label result data | Instructions in data never alter system/tool protocol. |
| Tool arguments | Scope override, broad export, cost abuse | Server-derived Company/Warehouse/Cardboard Item Group scope and fixed fields/filters/limits | Reject/narrow broad data or date requests. |
| Entity names | Wrong record inference | Deterministic backend lookup | Exactly one authorized match continues; multiple matches ask one clarification question. |
| Numeric facts | Hallucinated calculation, substitution, inconsistent rounding | Structured authoritative `facts`; backend-only business calculation; final-answer grounding validation | No fact means no number in answer. |
| Session / feature availability | Unauthorized use or record enumeration | authenticated Frappe session and `can_use_ai_assistant` flag | No disclosure whether inaccessible record exists. |
| Provider request | Secret leakage or privacy-routing downgrade | Server-only secret, Zero Data Retention compatible routing, data collection disabled, provider allowlist | Fail closed if configured privacy routing cannot be honored. |
| Audit log | Storage of business content/audio | 30-day metadata allowlist | Do not persist prompt, transcript, answer, tool arguments/results, audio, supplier names, or business values by default. |
| Voice input | Oversize/MIME abuse/persisted audio | strict MIME, duration, and byte-size allowlists; no Frappe File | Reject safely and do not persist audio. |
| Transport | SSE buffering/disconnect/cancellation failure | SSE spike before dependency; standard request/response JSON fallback | Streaming cannot block V1 delivery. |

## Required adversarial suite

The suite must cover user and stored attempts to:

- claim manager status to bypass scope;
- execute `frappe.delete_doc`, submit, cancel, or change warehouse;
- disclose raw tool response, system prompt, tool arguments, or arbitrary methods;
- repeat tool calls for a different answer;
- retrieve a known but unauthorized record;
- retrieve every record from system start;
- use a supplier name or supply note that says to ignore previous instructions.

Expected behavior is deterministic: refusal, bounded result, no-result response, or one clarification question. No test may result in a write or raw-data disclosure.

## Cost and availability controls

The server enforces maximum messages per request, maximum tool steps = 4, maximum rows/page/date range, maximum tokens, per-user rate limit, maximum concurrent requests per user, and a global daily AI budget. Provider-side budget controls are a second line of defense, not the only one.

## Telemetry and retention

Retain approved metadata for 30 days only:

- user, timestamp, status, tool names, correlation id;
- model, provider, tool count, input tokens, output tokens, estimated cost, error code;
- `stt_latency_ms`, `planner_latency_ms`, `tool_latency_ms`, `final_answer_latency_ms`, `tts_latency_ms`, and `total_latency_ms` where applicable.

Production logging does not retain user prompt, transcript, assistant answer, tool arguments, raw tool results, audio, supplier/customer names, or business values. Expanded diagnostics require an explicit debug setting and are never the production default.

## Delivery safeguards

Text Assistant Before Voice Dependency is mandatory: text → tools → facts → grounded Arabic answer passes acceptance before voice acceptance depends on it. Voice Input + Text Output remains available if TTS/playback fails; Text Input + Text Output remains the baseline if microphone/STT fails.

An SSE spike must prove authenticated session, CSRF, buffering, timeout, disconnect, cancellation, worker, and proxy behavior. Standard request/response JSON is the fallback when SSE adds disproportionate infrastructure complexity.
