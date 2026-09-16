"""Ephemeral voice ingress/egress for the read-only AI assistant."""
from __future__ import annotations

import base64
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from cardboard_management.cardboard_management.api.ai_chat import can_use_ai_assistant
from cardboard_management.cardboard_management.api.ai_provider import ProviderError, get_provider
from cardboard_management.cardboard_management.api.ai_telemetry import record

MAX_AUDIO_BYTES = 2 * 1024 * 1024
MAX_TTS_CHARS = 600
MIME_FORMATS = {
    "audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/x-wav": "wav",
    "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/aac": "aac", "audio/flac": "flac",
}


def _require_voice_access() -> None:
    if not can_use_ai_assistant():
        frappe.throw(_("مش مسموح لي أعرض البيانات دي لحسابك."), frappe.PermissionError)


def _safe_error() -> dict[str, Any]:
    return {"status": "error", "message": "تعذر فهم التسجيل. جرب مرة أخرى أو اكتب السؤال.", "code": "stt_provider_error"}


def _recording_metadata(uploaded, content_type: str, audio_size: int) -> dict[str, Any]:
    """Safe transport-only metadata; never include filename, bytes, or text."""
    duration = cint(frappe.form_dict.get("recording_duration_ms") or 0)
    browser_mime = str(frappe.form_dict.get("browser_mime") or "").split(";", 1)[0].lower()[:80]
    extension = str(getattr(uploaded, "filename", "") or "").rsplit(".", 1)[-1].lower()[:12]
    return {
        "recording_duration_ms": min(max(duration, 0), 60_000),
        "recording_byte_size": audio_size,
        "browser_mime": browser_mime,
        "normalized_mime": content_type,
        "multipart_filename_extension": extension,
        "stt_language_hint_present": True,
    }


@frappe.whitelist(methods=["POST"])
def transcribe_audio() -> dict[str, Any]:
    """Accept one bounded multipart upload in memory; never create File records."""
    _require_voice_access()
    uploaded = frappe.request.files.get("audio")
    content_type = str(getattr(uploaded, "mimetype", "") or "").split(";", 1)[0].lower()
    audio_format = MIME_FORMATS.get(content_type)
    if not uploaded or not audio_format:
        frappe.throw(_("صيغة التسجيل غير مدعومة."), frappe.ValidationError)
    audio = uploaded.read(MAX_AUDIO_BYTES + 1)
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        frappe.throw(_("حجم التسجيل أكبر من الحد المسموح."), frappe.ValidationError)
    diagnostic = _recording_metadata(uploaded, content_type, len(audio))
    try:
        result = get_provider().transcribe_audio(audio, audio_format)
    except ProviderError:
        record("voice_stt", {**diagnostic, "status": "error", "error_code": "stt_provider_error"})
        return _safe_error()
    telemetry = result["telemetry"]
    diagnostic.update({
        "stt_model": telemetry.get("model"), "stt_http_status": telemetry.get("status"),
        "transcript_character_count": len(result["text"]), "stt_latency_ms": telemetry.get("latency_ms"),
    })
    record("voice_stt", {**telemetry, **diagnostic, "status": "ok"})
    return {"status": "ok", "transcript": result["text"][:1000], "telemetry": {"stt_latency_ms": telemetry.get("latency_ms"), "model": telemetry.get("model"), "provider": telemetry.get("provider")}}


@frappe.whitelist(methods=["POST"])
def synthesize_answer(answer: str | None = None) -> dict[str, Any]:
    """Return ephemeral PCM for a bounded, final user-facing answer only."""
    _require_voice_access()
    if not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_TTS_CHARS:
        frappe.throw(_("النص الصوتي غير صالح."), frappe.ValidationError)
    try:
        result = get_provider().synthesize_speech(answer.strip())
    except ProviderError:
        record("voice_tts", {"status": "error"})
        return _safe_error()
    telemetry = result["telemetry"]
    record("voice_tts", {**telemetry, "tts_latency_ms": telemetry.get("latency_ms"), "status": "ok"})
    return {"status": "ok", "audio_base64": base64.b64encode(result["audio"]).decode("ascii"), "format": "pcm_s16le_24000_mono", "telemetry": {"tts_latency_ms": telemetry.get("latency_ms"), "model": telemetry.get("model"), "provider": telemetry.get("provider")}}
