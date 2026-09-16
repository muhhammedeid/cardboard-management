"""DB-free contracts for ephemeral AI voice and safe telemetry boundaries."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "cardboard_management" / "api"


class TestAiVoiceContracts(unittest.TestCase):
    def setUp(self):
        self.voice = (ROOT / "ai_voice.py").read_text(encoding="utf-8")
        self.telemetry = (ROOT / "ai_telemetry.py").read_text(encoding="utf-8")

    def test_voice_is_ephemeral_and_bounded(self):
        self.assertIn("MAX_AUDIO_BYTES = 2 * 1024 * 1024", self.voice)
        self.assertIn("uploaded.read(MAX_AUDIO_BYTES + 1)", self.voice)
        self.assertNotIn("save_file", self.voice)
        self.assertNotIn("File(", self.voice)

    def test_voice_uses_approved_provider_and_mime_allowlist(self):
        self.assertIn("MIME_FORMATS", self.voice)
        self.assertIn('split(";", 1)', self.voice)
        self.assertIn('"audio/webm"', self.voice)
        self.assertIn("get_provider().transcribe_audio", self.voice)
        self.assertIn("get_provider().synthesize_speech", self.voice)
        self.assertIn("can_use_ai_assistant", self.voice)

    def test_stt_diagnostics_record_only_safe_transport_metadata(self):
        for field in ("recording_duration_ms", "recording_byte_size", "browser_mime", "normalized_mime", "multipart_filename_extension", "stt_http_status", "transcript_character_count"):
            self.assertIn(field, self.voice)
            self.assertIn(f'"{field}"', self.telemetry)
        self.assertNotIn('uploaded.filename', self.telemetry)

    def test_tts_only_accepts_bounded_final_text(self):
        self.assertIn("MAX_TTS_CHARS = 600", self.voice)
        self.assertIn("len(answer) > MAX_TTS_CHARS", self.voice)
        self.assertIn("audio_base64", self.voice)
        self.assertIn("pcm_s16le_24000_mono", self.voice)

    def test_telemetry_allowlist_excludes_sensitive_content(self):
        for forbidden in ("prompt", "transcript", "answer", "audio", "supplier", "arguments", "raw"):
            self.assertNotIn(f'"{forbidden}"', self.telemetry)
        self.assertIn("SAFE_FIELDS", self.telemetry)
        self.assertIn("frappe.logger", self.telemetry)


if __name__ == "__main__":
    unittest.main()
