"""DB-free contract tests for the server-only OpenRouter provider adapter."""

import importlib
import unittest
from collections import deque
from pathlib import Path


class FakeResponse:
	def __init__(self, status_code, payload=None, content=b"audio", headers=None):
		self.status_code = status_code
		self._payload = payload or {}
		self.content = content
		self.headers = headers or {}
		self.text = "provider error"

	def json(self):
		return self._payload


class TestOpenRouterProviderContract(unittest.TestCase):
	def setUp(self):
		self.module = importlib.import_module("cardboard_management.cardboard_management.api.ai_provider")
		self.config = {
			"openrouter_api_key": "test-key",
			"openrouter_chat_routing": {
				"zdr": True,
				"data_collection": "deny",
				"require_parameters": True,
				"provider_only": None,
			},
			"openrouter_tts_voice": "Zephyr",
		}

	def test_approved_models_are_fixed_and_server_only(self):
		self.assertEqual(self.module.STT_MODEL, "openai/whisper-large-v3")
		self.assertEqual(self.module.CHAT_MODEL, "deepseek/deepseek-v4-flash-0731")
		self.assertEqual(self.module.TTS_MODEL, "google/gemini-3.1-flash-tts-preview")
		self.assertNotEqual(self.module.TTS_MODEL, "openai/gpt-4o-mini-tts-2025-12-15")
		source = Path(self.module.__file__).read_text(encoding="utf-8")
		self.assertNotIn("frappe.whitelist", source)

	def test_chat_request_uses_dynamic_privacy_filtered_routing_without_vendor_pinning(self):
		calls = []

		def request(**kwargs):
			calls.append(kwargs)
			return FakeResponse(200, {"choices": [{"message": {"content": "إجابة تجريبية"}}], "usage": {"cost": 0.001}})

		provider = self.module.OpenRouterProvider(self.config, request=request, monotonic=lambda: 1.0)
		result = provider.chat_completion(
			[{"role": "user", "content": "رصيد المخزون التجريبي كام؟"}],
			tools=[],
			tool_choice="required",
			max_tokens=180,
		)

		self.assertEqual(result["text"], "إجابة تجريبية")
		self.assertEqual(calls[0]["url"], self.module.CHAT_ENDPOINT)
		payload = calls[0]["json"]
		self.assertEqual(payload["model"], self.module.CHAT_MODEL)
		self.assertEqual(payload["tool_choice"], "required")
		self.assertEqual(payload["max_tokens"], 180)
		self.assertEqual(payload["provider"], {
			"data_collection": "deny",
			"zdr": True,
			"require_parameters": True,
		})
		self.assertNotIn("only", payload["provider"])
		self.assertNotIn("allow_fallbacks", payload["provider"])
		self.assertEqual(result["telemetry"]["model"], self.module.CHAT_MODEL)
		self.assertEqual(result["telemetry"]["estimated_cost_usd"], 0.001)

	def test_transcription_sends_only_encoded_audio_and_never_persists_it(self):
		calls = []

		def request(**kwargs):
			calls.append(kwargs)
			return FakeResponse(200, {"text": "رصيد المخزون التجريبي كام؟", "usage": {"cost": 0.0001}})

		provider = self.module.OpenRouterProvider(self.config, request=request, monotonic=lambda: 1.0)
		result = provider.transcribe_audio(b"synthetic-webm", "webm")

		self.assertEqual(result["text"], "رصيد المخزون التجريبي كام؟")
		self.assertEqual(calls[0]["url"], self.module.TRANSCRIPTION_ENDPOINT)
		payload = calls[0]["json"]
		self.assertEqual(payload["model"], self.module.STT_MODEL)
		self.assertEqual(payload["language"], "ar")
		self.assertEqual(payload["input_audio"]["format"], "webm")
		self.assertEqual(payload["provider"], {"data_collection": "deny", "zdr": True})
		self.assertNotIn("synthetic-webm", str(payload))

	def test_chat_requests_are_transcription_not_translation_and_pinned_to_arabic(self):
		source = Path(self.module.__file__).read_text(encoding="utf-8")
		self.assertIn('"language": "ar"', source)
		self.assertIn("audio/transcriptions", source)
		self.assertNotIn("audio/translations", source)
		self.assertNotIn('"translation"', source)
		self.assertNotIn('"mode": "translate"', source)

	def test_tts_is_model_specific_pcm_without_openai_voice_assumptions(self):
		calls = []

		def request(**kwargs):
			calls.append(kwargs)
			return FakeResponse(200, content=b"synthetic-pcm", headers={"Content-Type": "audio/pcm"})

		config_without_tts_allowlist = {
			"openrouter_api_key": "test-key",
			"openrouter_tts_voice": "Zephyr",
		}
		provider = self.module.OpenRouterProvider(config_without_tts_allowlist, request=request, monotonic=lambda: 1.0)
		result = provider.synthesize_speech("النتيجة التجريبية جاهزة", voice="Zephyr")

		self.assertEqual(result["audio"], b"synthetic-pcm")
		self.assertEqual(result["content_type"], "audio/pcm")
		payload = calls[0]["json"]
		self.assertEqual(payload["model"], self.module.TTS_MODEL)
		self.assertEqual(payload["response_format"], "pcm")
		self.assertEqual(payload["provider"], {"data_collection": "deny", "zdr": True})
		self.assertNotIn("only", payload["provider"])
		self.assertNotIn("allow_fallbacks", payload["provider"])

	def test_missing_secret_or_channel_allowlist_fails_closed(self):
		with self.assertRaises(self.module.ProviderConfigurationError):
			self.module.OpenRouterProvider({}).chat_completion([])
		with self.assertRaises(self.module.ProviderConfigurationError):
			self.module.OpenRouterProvider({"openrouter_api_key": "key"}).synthesize_speech("نص")

	def test_rate_limit_retries_once_and_reports_a_safe_error_when_exhausted(self):
		responses = deque([
			FakeResponse(429, headers={"Retry-After": "0"}),
			FakeResponse(200, {"choices": [{"message": {"content": "تم"}}]}),
		])
		attempts = []
		provider = self.module.OpenRouterProvider(
			self.config,
			request=lambda **kwargs: (attempts.append(kwargs), responses.popleft())[1],
			monotonic=lambda: 1.0,
			sleep=lambda _seconds: None,
		)

		self.assertEqual(provider.chat_completion([{"role": "user", "content": "اختبار"}])["text"], "تم")
		self.assertEqual(len(attempts), 2)

	def test_stream_chat_requests_upstream_streaming_and_preserves_privacy_route(self):
		calls = []

		class StreamResponse(FakeResponse):
			def iter_lines(self, decode_unicode=False):
				return iter(["data: synthetic", "data: [DONE]"])

		provider = self.module.OpenRouterProvider(
			self.config,
			request=lambda **kwargs: (calls.append(kwargs), StreamResponse(200))[1],
			monotonic=lambda: 1.0,
		)

		self.assertEqual(
			list(provider.stream_chat([{"role": "user", "content": "اختبار"}])),
			["data: synthetic", "data: [DONE]"],
		)
		self.assertTrue(calls[0]["stream"])
		self.assertEqual(calls[0]["json"]["provider"], {
			"data_collection": "deny", "zdr": True, "require_parameters": True,
		})
		self.assertNotIn("only", calls[0]["json"]["provider"])

	def test_explicit_future_provider_pin_is_preserved_without_weakening_privacy_filters(self):
		config = dict(self.config)
		config["openrouter_chat_routing"] = {
			"zdr": True, "data_collection": "deny", "require_parameters": True,
			"provider_only": ["future-approved-provider"],
		}
		provider = self.module.OpenRouterProvider(config, request=lambda **kwargs: FakeResponse(200, {"choices": [{"message": {"content": "تم"}}]}), monotonic=lambda: 1.0)
		self.assertEqual(provider.chat_completion([{"role": "user", "content": "اختبار"}])["text"], "تم")
		self.assertEqual(provider._provider_route("chat"), {
			"only": ["future-approved-provider"], "data_collection": "deny", "zdr": True, "require_parameters": True,
		})

	def test_chat_routing_rejects_any_attempt_to_weaken_required_privacy_or_capability_filters(self):
		config = dict(self.config)
		config["openrouter_chat_routing"] = {"zdr": False, "data_collection": "deny", "require_parameters": True, "provider_only": None}
		with self.assertRaises(self.module.ProviderConfigurationError):
			self.module.OpenRouterProvider(config)._provider_route("chat")

	def test_sse_probe_explicitly_selects_json_until_a_real_sse_transport_is_verified(self):
		self.assertEqual(self.module.delivery_mode(), "json")
		self.assertEqual(self.module.SSE_PROBE_EVENTS, ("one", "two", "three", "done"))


if __name__ == "__main__":
	unittest.main()
