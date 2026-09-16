# AI Assistant Provider Setup (unchanged for V3)

## Approved configuration

These model/provider keys are unchanged by the V3 semantic engine — only the
orchestration above them changed (oneDeepSeek interpretation call, semantic
validator, six domain tools).

| Responsibility | Site configuration key | Default |
|---|---|---|
| Chat / planner | `ai_chat_model` | `deepseek/deepseek-v4-flash-0731` |
| Speech-to-text | `ai_stt_model` | `openai/whisper-large-v3` |
| Text-to-speech | existing TTS keys | `google/gemini-3.1-flash-tts-preview` |
| Chat output budget | `ai_chat_max_output_tokens` | `384`, bounded to 128–512 |

`ai_provider.py` resolves chat and STT models from server-only site configuration, with these defaults if the site keys are absent. Nova never receives provider secrets or model routing configuration.

## Required site configuration

```text
openrouter_api_key: <server secret>
openrouter_chat_routing:
  zdr: true
  data_collection: deny
  require_parameters: true
  provider_only: null
ai_chat_model: deepseek/deepseek-v4-flash-0731
ai_stt_model: openai/whisper-large-v3
ai_chat_max_output_tokens: 384
openrouter_tts_model: google/gemini-3.1-flash-tts-preview
openrouter_tts_voice: Zephyr
```

Keep the existing TTS configuration unchanged. There is no automatic quality fallback: an unavailable approved chat/STT model returns the safe provider failure response.

## Privacy, transport, and voice boundary

DeepSeek chat uses privacy-filtered dynamic routing: `zdr: true`, `data_collection: deny`, and `require_parameters: true`. `provider_only: null` means OpenRouter may fail over only among endpoints satisfying every filter; no vendor tag is guessed or pinned. A future explicit `provider_only` list remains supported but must not weaken these filters. STT and TTS retain their documented `data_collection: deny` / `zdr: true` request policy where endpoint routing supports it.

Voice remains: MediaRecorder → bounded in-memory upload → Arabic transcription (`language: ar`) → editable transcript → explicit Send. No audio File is created; 60 seconds, 2 MiB, MIME normalization, and the existing format allowlist remain binding. JSON request/response remains the supported V2 delivery mode.

## Required pre-production connectivity checks

Use synthetic content only and verify:

1. DeepSeek accepts the tool schema, chooses an approved tool, and returns valid JSON arguments.
2. Whisper Large V3 returns Arabic text from a synthetic Arabic sample.
3. The configured TTS still returns playable audio.

These are connectivity checks, not model comparisons. Do not enable a substitute model if either approved model is unavailable.
