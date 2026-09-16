"""Server-only OpenRouter adapter for the Cardboard read-only AI assistant.

This module is deliberately not whitelisted. Later read tools and the chat
orchestrator call this adapter; browser clients never receive provider secrets.
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

import frappe
import requests

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CHAT_ENDPOINT = f"{OPENROUTER_BASE_URL}/chat/completions"
TRANSCRIPTION_ENDPOINT = f"{OPENROUTER_BASE_URL}/audio/transcriptions"
TTS_ENDPOINT = f"{OPENROUTER_BASE_URL}/audio/speech"

DEFAULT_STT_MODEL = "openai/whisper-large-v3"
DEFAULT_CHAT_MODEL = "deepseek/deepseek-v4-flash-0731"
# Compatibility aliases remain public for the provider contract and always reflect
# the configuration defaults; individual requests call the resolvers below.
STT_MODEL = DEFAULT_STT_MODEL
CHAT_MODEL = DEFAULT_CHAT_MODEL
TTS_MODEL = "google/gemini-3.1-flash-tts-preview"
APPROVED_TTS_MODELS = {TTS_MODEL: {"default_format": "pcm", "formats": frozenset({"pcm"})}}

SUPPORTED_AUDIO_FORMATS = frozenset({"aac", "flac", "m4a", "mp3", "ogg", "wav", "webm"})
MAX_ATTEMPTS = 2
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRY_AFTER_SECONDS = 2

# Frappe v15's response dispatcher has no SSE response type. Task 2 records a
# JSON fallback until a separate authenticated browser/worker transport spike
# proves SSE end-to-end without bypassing Frappe's response lifecycle.
SSE_PROBE_EVENTS = ("one", "two", "three", "done")


class ProviderError(Exception):
	"""A safe error intended for the future chat orchestrator."""


class ProviderConfigurationError(ProviderError):
	pass


class ProviderRateLimitError(ProviderError):
	pass


class ProviderUnavailableError(ProviderError):
	pass


class ProviderResponseError(ProviderError):
	pass


def delivery_mode() -> str:
	"""Return the approved V1 delivery mode until SSE is independently proven."""
	return "json"


def _as_config(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
	return value if value is not None else frappe.conf


def _configured_model(config: Mapping[str, Any], key: str, default: str) -> str:
	value = config.get(key, default)
	if not isinstance(value, str) or not value.strip():
		raise ProviderConfigurationError(f"{key} is not configured.")
	return value.strip()


def chat_model_for(config: Mapping[str, Any] | None = None) -> str:
	return _configured_model(_as_config(config), "ai_chat_model", DEFAULT_CHAT_MODEL)


def stt_model_for(config: Mapping[str, Any] | None = None) -> str:
	return _configured_model(_as_config(config), "ai_stt_model", DEFAULT_STT_MODEL)


def _positive_cost(usage: Any) -> float | None:
	if not isinstance(usage, Mapping):
		return None
	try:
		cost = float(usage.get("cost"))
	except (TypeError, ValueError):
		return None
	return cost if cost >= 0 else None


class OpenRouterProvider:
	"""Bounded HTTP client with server-configured privacy routing."""

	def __init__(
		self,
		config: Mapping[str, Any] | None = None,
		*,
		request: Callable[..., Any] | None = None,
		monotonic: Callable[[], float] = time.monotonic,
		sleep: Callable[[float], None] = time.sleep,
	):
		self.config = _as_config(config)
		self.request = request or requests.post
		self.monotonic = monotonic
		self.sleep = sleep

	def _api_key(self) -> str:
		key = self.config.get("openrouter_api_key")
		if not isinstance(key, str) or not key.strip():
			raise ProviderConfigurationError("OpenRouter is not configured on this site.")
		return key.strip()

	def _headers(self) -> dict[str, str]:
		headers = {
			"Authorization": f"Bearer {self._api_key()}",
			"Content-Type": "application/json",
			"X-OpenRouter-Title": str(self.config.get("openrouter_title") or "Cardboard Management"),
		}
		referer = self.config.get("openrouter_http_referer")
		if isinstance(referer, str) and referer.strip():
			headers["HTTP-Referer"] = referer.strip()
		return headers

	def _provider_route(self, channel: str) -> dict[str, Any]:
		"""Return capability/privacy routing for the selected chat model family.

		The default deliberately permits OpenRouter provider failover, but only
		between endpoints satisfying the required ZDR, no-collection, and tool
		parameter filters.  A future deployment may explicitly pin compatible
		providers through ``provider_only``; this model family is unpinned.
		"""
		if channel != "chat":
			raise ProviderConfigurationError(f"OpenRouter {channel} routing is not supported.")
		routing = self.config.get("openrouter_chat_routing", {})
		if routing is None:
			routing = {}
		if not isinstance(routing, Mapping):
			raise ProviderConfigurationError("OpenRouter chat routing is invalid.")
		if routing.get("zdr", True) is not True:
			raise ProviderConfigurationError("OpenRouter chat routing must require ZDR.")
		if routing.get("data_collection", "deny") != "deny":
			raise ProviderConfigurationError("OpenRouter chat routing must deny data collection.")
		if routing.get("require_parameters", True) is not True:
			raise ProviderConfigurationError("OpenRouter chat routing must require parameters.")
		provider_only = routing.get("provider_only")
		result: dict[str, Any] = {
			"data_collection": "deny",
			"zdr": True,
			"require_parameters": True,
		}
		if provider_only is None:
			return result
		if not isinstance(provider_only, Sequence) or isinstance(provider_only, str) or not provider_only:
			raise ProviderConfigurationError("OpenRouter chat provider_only is invalid.")
		if not all(isinstance(provider, str) and provider.strip() for provider in provider_only):
			raise ProviderConfigurationError("OpenRouter chat provider_only is invalid.")
		result["only"] = [provider.strip() for provider in provider_only]
		return result

	def _tts_model(self) -> tuple[str, Mapping[str, Any]]:
		model = self.config.get("openrouter_tts_model") or TTS_MODEL
		if not isinstance(model, str) or model not in APPROVED_TTS_MODELS:
			raise ProviderConfigurationError("OpenRouter TTS model is not approved.")
		return model, APPROVED_TTS_MODELS[model]

	def _retry_after_seconds(self, response: Any) -> float:
		try:
			seconds = float((getattr(response, "headers", {}) or {}).get("Retry-After", 0))
		except (TypeError, ValueError):
			return 0
		return min(max(seconds, 0), MAX_RETRY_AFTER_SECONDS)

	def _post(self, url: str, payload: Mapping[str, Any], *, stream: bool = False) -> tuple[Any, int]:
		started = self.monotonic()
		for attempt in range(MAX_ATTEMPTS):
			try:
				response = self.request(
					url=url,
					headers=self._headers(),
					json=dict(payload),
					timeout=REQUEST_TIMEOUT_SECONDS,
					stream=stream,
				)
			except requests.RequestException as error:
				if attempt + 1 == MAX_ATTEMPTS:
					raise ProviderUnavailableError("AI provider is temporarily unavailable.") from error
				self.sleep(0)
				continue

			status = int(getattr(response, "status_code", 0) or 0)
			if status == 429:
				if attempt + 1 == MAX_ATTEMPTS:
					raise ProviderRateLimitError("AI provider rate limit reached.")
				self.sleep(self._retry_after_seconds(response))
				continue
			if status >= 500:
				if attempt + 1 == MAX_ATTEMPTS:
					raise ProviderUnavailableError("AI provider is temporarily unavailable.")
				self.sleep(self._retry_after_seconds(response))
				continue
			if status < 200 or status >= 300:
				raise ProviderResponseError("AI provider rejected the request.")
			return response, round((self.monotonic() - started) * 1000)
		raise ProviderUnavailableError("AI provider is temporarily unavailable.")

	@staticmethod
	def _telemetry(model: str, status: int, latency_ms: int, usage: Any = None) -> dict[str, Any]:
		return {
			"provider": "openrouter",
			"model": model,
			"status": status,
			"latency_ms": latency_ms,
			"estimated_cost_usd": _positive_cost(usage),
		}

	def transcribe_audio(self, audio_bytes: bytes, audio_format: str) -> dict[str, Any]:
		format_name = str(audio_format or "").lower().strip()
		if not isinstance(audio_bytes, bytes) or not audio_bytes:
			raise ProviderResponseError("Audio input is required.")
		if format_name not in SUPPORTED_AUDIO_FORMATS:
			raise ProviderResponseError("Unsupported audio format.")
		model = stt_model_for(self.config)
		payload = {
			"model": model,
			"input_audio": {"data": base64.b64encode(audio_bytes).decode("ascii"), "format": format_name},
			"language": "ar",
			"response_format": "json",
			# OpenRouter documents data-policy routing here, but not per-request
			# `only` provider filtering for transcription endpoints.
			"provider": {"data_collection": "deny", "zdr": True},
		}
		response, latency_ms = self._post(TRANSCRIPTION_ENDPOINT, payload)
		try:
			body = response.json()
			text = body["text"].strip()
		except (AttributeError, KeyError, TypeError, ValueError) as error:
			raise ProviderResponseError("AI provider returned an invalid transcription.") from error
		if not text:
			raise ProviderResponseError("AI provider returned an empty transcription.")
		return {"text": text, "telemetry": self._telemetry(model, response.status_code, latency_ms, body.get("usage"))}

	def chat_completion(
		self,
		messages: list[dict[str, Any]],
		tools: list[dict[str, Any]] | None = None,
		tool_choice: str | dict[str, Any] | None = None,
		max_tokens: int | None = None,
		response_format: Mapping[str, Any] | None = None,
	) -> dict[str, Any]:
		# Validate server configuration before inspecting caller-controlled content.
		self._api_key()
		if not isinstance(messages, list) or not messages:
			raise ProviderResponseError("Chat messages are required.")
		model = chat_model_for(self.config)
		payload: dict[str, Any] = {
			"model": model,
			"messages": messages,
			"stream": False,
			"provider": self._provider_route("chat"),
		}
		if tools is not None:
			payload["tools"] = tools
		if tool_choice is not None:
			payload["tool_choice"] = tool_choice
		if response_format is not None:
			if not isinstance(response_format, Mapping) or "json_schema" not in response_format:
				raise ProviderResponseError("Invalid response_format.")
			payload["response_format"] = dict(response_format)
		if max_tokens is not None:
			if not isinstance(max_tokens, int) or not 1 <= max_tokens <= 4096:
				raise ProviderResponseError("Invalid chat token budget.")
			payload["max_tokens"] = max_tokens
		response, latency_ms = self._post(CHAT_ENDPOINT, payload)
		try:
			body = response.json()
			content = body["choices"][0]["message"].get("content") or ""
		except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
			raise ProviderResponseError("AI provider returned an invalid chat response.") from error
		return {"text": str(content).strip(), "raw": body, "telemetry": self._telemetry(model, response.status_code, latency_ms, body.get("usage"))}

	def stream_chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Iterator[str]:
		"""Yield raw provider SSE payload lines for the future isolated transport layer."""
		model = chat_model_for(self.config)
		payload: dict[str, Any] = {
			"model": model,
			"messages": messages,
			"stream": True,
			"provider": self._provider_route("chat"),
		}
		if tools is not None:
			payload["tools"] = tools
		response, _latency_ms = self._post(CHAT_ENDPOINT, payload, stream=True)
		for line in response.iter_lines(decode_unicode=True):
			if line:
				yield line

	def synthesize_speech(self, text: str, voice: str | None = None, audio_format: str | None = None) -> dict[str, Any]:
		if not isinstance(text, str) or not text.strip():
			raise ProviderResponseError("Speech input is required.")
		model, capabilities = self._tts_model()
		format_name = str(audio_format or capabilities["default_format"]).lower().strip()
		if format_name not in capabilities["formats"]:
			raise ProviderResponseError("Unsupported speech format for the configured TTS model.")
		voice_name = voice or self.config.get("openrouter_tts_voice")
		if not isinstance(voice_name, str) or not voice_name.strip():
			raise ProviderConfigurationError("OpenRouter TTS voice is not configured.")
		payload = {
			"model": model,
			"input": text.strip(),
			"voice": voice_name.strip(),
			"response_format": format_name,
			# Dedicated TTS endpoint routing does not document `only` provider
			# pinning; preserve only the documented privacy controls.
			"provider": {"data_collection": "deny", "zdr": True},
		}
		response, latency_ms = self._post(TTS_ENDPOINT, payload)
		audio = getattr(response, "content", b"")
		if not isinstance(audio, bytes) or not audio:
			raise ProviderResponseError("AI provider returned empty speech audio.")
		content_type = str((getattr(response, "headers", {}) or {}).get("Content-Type") or "").split(";", 1)[0]
		return {
			"audio": audio,
			"content_type": content_type,
			"telemetry": self._telemetry(model, response.status_code, latency_ms),
		}


def get_provider() -> OpenRouterProvider:
	"""Construct the adapter from the current site's server-only configuration."""
	return OpenRouterProvider()


def run_provider_probes(audio_bytes: bytes, audio_format: str = "webm") -> dict[str, Any]:
	"""Run explicitly supplied synthetic probes; never persist probe media or text."""
	provider = get_provider()
	transcription = provider.transcribe_audio(audio_bytes, audio_format)
	chat = provider.chat_completion([{"role": "user", "content": "رصيد المخزون التجريبي كام؟"}], tools=[])
	speech = provider.synthesize_speech("النتيجة التجريبية جاهزة")
	return {
		"transcription": transcription["telemetry"],
		"chat": chat["telemetry"],
		"speech": speech["telemetry"],
		"delivery_mode": delivery_mode(),
	}