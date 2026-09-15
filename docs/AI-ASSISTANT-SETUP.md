# AI Assistant Provider Setup

## Approved model identifiers

| Responsibility | Model |
|---|---|
| Speech-to-text | `openai/whisper-large-v3-turbo` |
| Conversation and tool calling | `google/gemini-2.5-flash-lite` |
| Text-to-speech | `openai/gpt-4o-mini-tts-2025-12-15` |

`google/gemini-2.5-flash-lite` is the only V1 default conversation model. Do not configure `google/gemini-2.5-flash` as the default or automatic fallback.

## Server-only configuration

The OpenRouter API credential is read only by the Cardboard server adapter from environment or site configuration. Nova/browser code never receives a provider key, model credential, or provider-routing configuration. Missing configuration returns a concise safe error and does not enable a degraded client-side path.

Feature code depends only on the dedicated adapter interface:

```text
transcribe_audio(...)
chat(...) / stream_chat(...)
synthesize_speech(...)
```

No feature module owns OpenRouter HTTP details, model-specific SDK behavior, or secrets.

## Privacy routing policy

For each STT, chat, and TTS request, use the strongest practical provider path supported by the selected model:

1. Zero Data Retention compatible routing;
2. data collection disabled;
3. explicit provider allowlist;
4. no silent routing through a provider that cannot preserve this policy.

If the required provider-routing policy is unavailable for an endpoint, fail closed for that request and surface a concise Arabic provider error. Record the exact selected provider and routing options in the live probe artifact, but never record prompts, audio, transcripts, answers, tool arguments, raw results, supplier names, or business values.

## Audio and transport probes

Before feature UI work, the provider adapter must prove:

- the actual browser recording MIME (`audio/webm` or `audio/webm;codecs=opus`, as observed) is accepted by STT;
- strict MIME allowlist, maximum duration, and maximum bytes;
- Arabic Egyptian acceptance sample transcription;
- selected TTS voice output is valid playable MP3 and acceptable for Arabic;
- a minimal authenticated SSE spike emits `one`, `two`, `three`, `done` without buffering or session/CSRF/proxy breakage.

Do not introduce FFmpeg or transcoding speculatively. Add a media dependency only if the live MIME probe proves it necessary. If SSE is not reliable without disproportionate complexity, use standard request/response JSON in V1.

## Budgets, failure behavior, and audit metadata

The server enforces maximum messages per request, maximum tool steps = 4, maximum rows/page/date range, maximum tokens, per-user request rate, maximum concurrent requests per user, and a global daily AI budget. Use provider-side/OpenRouter budget controls as an additional limit.

Retry provider failures only within bounded timeout/retry policy. Preserve successful text when TTS fails. Voice input/output failure must not break text chat.

Approved audit metadata is retained for 30 days: user, timestamp, status, tool names, correlation id, model, provider, latency, tool count, input tokens, output tokens, estimated cost, and error code. Debug logging is disabled by default and is the only mode allowed to collect additional diagnostics temporarily.
