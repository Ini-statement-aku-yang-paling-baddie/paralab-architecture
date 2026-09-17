"""Deterministic adapter from Arlen's F5 canonical examples to V4 F5 output.

This module never invents lab measurements. It copies canonical source values,
derives only the V4 envelope and deterministic extraction confidence, and keeps
all outputs as drafts requiring user confirmation.
"""
from __future__ import annotations

from typing import Any

MEASUREMENT_FIELDS = ("ph", "viscosity_cp")
QUALITY_CONFIDENCE = {
    "observed": 0.95,
    "uncertain": 0.65,
    "missing": None,
    "invalid": None,
}


def trial_id_from_checkpoint(checkpoint_id: str) -> str:
    """Return trial ID from V4 checkpoint ID, e.g. FULL-P-001-T1-SERIES-W00."""
    marker = "-SERIES-"
    if not isinstance(checkpoint_id, str) or marker not in checkpoint_id:
        raise ValueError("checkpoint_id must include '-SERIES-'")
    trial_id, week_part = checkpoint_id.split(marker, 1)
    if not trial_id or not week_part.startswith("W"):
        raise ValueError("checkpoint_id has invalid V4 checkpoint format")
    return trial_id


def _measurement_patch(target: dict[str, Any]) -> tuple[dict[str, float | int], dict[str, float | None]]:
    measurements = target.get("measurements")
    quality = target.get("quality")
    if not isinstance(measurements, dict) or not isinstance(quality, dict):
        raise ValueError("target must contain measurements and quality objects")

    patch: dict[str, float | int] = {}
    confidence: dict[str, float | None] = {}
    for field in MEASUREMENT_FIELDS:
        state = quality.get(field)
        if state not in QUALITY_CONFIDENCE:
            raise ValueError(f"unsupported quality state for {field}: {state!r}")
        value = measurements.get(field)
        confidence[field] = QUALITY_CONFIDENCE[state]
        if state in {"observed", "uncertain"}:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"{field} must be numeric when quality is {state}")
            patch[field] = value
        elif value is not None:
            raise ValueError(f"{field} must be null when quality is {state}")
    return patch, confidence


def adapt_f5_example(row: dict[str, Any]) -> dict[str, Any]:
    """Return the exact V4 F5 student target for one canonical source row."""
    if row.get("requires_confirmation") is not True:
        raise ValueError("source row must set requires_confirmation=true")

    checkpoint_id = row.get("checkpoint_id")
    derived_trial_id = trial_id_from_checkpoint(checkpoint_id)
    declared_trial_id = row.get("trial_id")
    if declared_trial_id is not None and declared_trial_id != derived_trial_id:
        raise ValueError("trial_id does not match checkpoint_id")

    target = row.get("target")
    if not isinstance(target, dict):
        raise ValueError("source row must contain target object")
    appearance = target.get("appearance")
    if not isinstance(appearance, str) or not appearance:
        raise ValueError("target.appearance must be a non-empty string")

    measurements, confidence = _measurement_patch(target)
    # 'uncertain' is a permitted observation label, but it needs lower confidence.
    confidence["appearance"] = 0.60 if appearance == "uncertain" else 0.90

    return {
        "trial_id": derived_trial_id,
        "proposed_checkpoint_patch": {
            "measurements": measurements,
            "observations": {"appearance": appearance},
        },
        "field_confidence": confidence,
        "requires_confirmation": True,
    }
