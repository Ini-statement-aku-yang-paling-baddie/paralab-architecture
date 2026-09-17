"""Unit tests for the local F5 faster-whisper transcription boundary."""
import sys
import types
import unittest
from unittest.mock import patch

from scripts.f5_stt import model_config_for, transcribe_audio


class ModelConfigTests(unittest.TestCase):
    def test_cpu_uses_int8(self):
        config = model_config_for("cpu")

        self.assertEqual(config.device, "cpu")
        self.assertEqual(config.compute_type, "int8")

    def test_gpu_uses_float16(self):
        config = model_config_for("gpu")

        self.assertEqual(config.device, "cuda")
        self.assertEqual(config.compute_type, "float16")

    def test_rejects_unknown_device(self):
        with self.assertRaisesRegex(ValueError, "device"):
            model_config_for("tpu")


class TranscribeAudioTests(unittest.TestCase):
    def test_returns_auditable_confirmation_record(self):
        class FakeWhisperModel:
            init_calls = []

            def __init__(self, model_name, *, device, compute_type):
                self.init_calls.append((model_name, device, compute_type))

            def transcribe(self, audio_path, *, language):
                self.audio_path = audio_path
                self.language = language
                segments = [
                    types.SimpleNamespace(start=0.0, end=1.2, text="  pH lima koma lima  "),
                    types.SimpleNamespace(start=1.2, end=2.0, text=" stabil "),
                ]
                return iter(segments), types.SimpleNamespace(language="id", duration=2.0)

        fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            record = transcribe_audio(
                "C:/recordings/trial-01.wav",
                trial_id="TRIAL-01",
                language="id",
                model_name="small",
                device="cpu",
            )

        self.assertEqual(record.trial_id, "TRIAL-01")
        self.assertEqual(record.audio_path, "C:/recordings/trial-01.wav")
        self.assertEqual(record.transcript, "pH lima koma lima stabil")
        self.assertEqual(record.requested_language, "id")
        self.assertEqual(record.detected_language, "id")
        self.assertEqual(record.duration_seconds, 2.0)
        self.assertEqual(record.stt_model, "faster-whisper-small")
        self.assertEqual(record.device, "cpu")
        self.assertEqual(record.compute_type, "int8")
        self.assertEqual(record.segments, ((0.0, 1.2, "pH lima koma lima"), (1.2, 2.0, "stabil")))
        self.assertIs(record.requires_confirmation, True)
        self.assertEqual(FakeWhisperModel.init_calls, [("small", "cpu", "int8")])

    def test_rejects_empty_transcript_before_downstream_extraction(self):
        class FakeWhisperModel:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, *args, **kwargs):
                return iter([types.SimpleNamespace(start=0.0, end=0.5, text="   ")]), types.SimpleNamespace(
                    language="id", duration=0.5
                )

        fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            with self.assertRaisesRegex(ValueError, "empty transcript"):
                transcribe_audio("C:/recordings/silence.wav", trial_id="TRIAL-01")


if __name__ == "__main__":
    unittest.main()
