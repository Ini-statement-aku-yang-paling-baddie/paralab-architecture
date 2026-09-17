"""Local, auditable faster-whisper transcription boundary for F5."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    """Execution configuration selected for a local faster-whisper model."""

    device: str
    compute_type: str


def model_config_for(device: str) -> ModelConfig:
    """Return the supported local execution configuration for *device*."""
    if device == "cpu":
        return ModelConfig(device="cpu", compute_type="int8")
    if device in {"cuda", "gpu"}:
        return ModelConfig(device="cuda", compute_type="float16")
    raise ValueError("device must be 'cpu', 'cuda', or 'gpu'")


@dataclass(frozen=True)
class TranscriptionRecord:
    """Auditable local-STT output; downstream extraction still needs review."""

    trial_id: str
    audio_path: str
    transcript: str
    requested_language: str | None
    detected_language: str | None
    segments: tuple[tuple[float, float, str], ...]
    duration_seconds: float | None
    stt_model: str
    device: str
    compute_type: str
    requires_confirmation: bool = True


def transcribe_audio(
    audio_path: str,
    *,
    trial_id: str,
    language: str | None = "id",
    model_name: str = "small",
    device: str = "cpu",
) -> TranscriptionRecord:
    """Transcribe local audio without writing any canonical journal fields."""
    from faster_whisper import WhisperModel

    config = model_config_for(device)
    model = WhisperModel(model_name, device=config.device, compute_type=config.compute_type)
    raw_segments, info = model.transcribe(audio_path, language=language)
    segments = tuple(
        (float(segment.start), float(segment.end), " ".join(segment.text.split()))
        for segment in raw_segments
    )
    transcript = " ".join(text for _, _, text in segments if text)
    if not transcript:
        raise ValueError("empty transcript; audio quality is insufficient for extraction")
    return TranscriptionRecord(
        trial_id=trial_id,
        audio_path=audio_path,
        transcript=transcript,
        requested_language=language,
        detected_language=getattr(info, "language", None),
        segments=segments,
        duration_seconds=getattr(info, "duration", None),
        stt_model=f"faster-whisper-{model_name}",
        device=config.device,
        compute_type=config.compute_type,
    )
