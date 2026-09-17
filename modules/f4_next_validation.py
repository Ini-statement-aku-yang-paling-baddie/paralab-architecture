"""Deterministic F4: risk-aware next-best validation step for ParaLab.

F4 prioritizes what to measure or review next. It never recommends a formula,
concentration, ingredient, or processing change.
"""
from __future__ import annotations

from typing import Any, Mapping

LIMITATION = (
    "Rekomendasi ini adalah heuristic prototype untuk prioritisasi observasi, "
    "bukan instruksi reformulasi atau approval stabilitas."
)
ALL_CHECKPOINT_FIELDS = ("ph", "viscosity_cp", "appearance")


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _missing_checkpoint_fields(checkpoint: Mapping[str, Any] | None) -> list[str]:
    if not checkpoint:
        return []
    measurements = checkpoint.get("measurements", {})
    missing = [field for field in ("ph", "viscosity_cp") if measurements.get(field) is None]
    if checkpoint.get("appearance") in {None, "", "missing", "invalid"}:
        missing.append("appearance")
    return missing


def recommend_next_validation(
    f3_forecast: Mapping[str, Any], checkpoint: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return one auditable validation/review step from structured F2/F3 fields."""
    f3 = dict(f3_forecast or {})
    screening = f3.get("f2_screening") or {}
    derived = screening.get("derived_features") or {}
    decision = f3.get("decision")
    confidence = f3.get("confidence")
    required_inputs: list[str] = []
    reason_codes: list[str] = []
    priority = "medium"
    action = "Lanjutkan observasi sesuai protokol dan konfirmasi checkpoint berikutnya sebelum keputusan lanjutan."

    missing = _missing_checkpoint_fields(checkpoint)
    if decision == "abstain_human_review_required" or missing:
        required_inputs = missing or list(ALL_CHECKPOINT_FIELDS)
        reason_codes.append("missing_baseline_or_checkpoint")
        priority = "high"
        action = "Lengkapi dan konfirmasi pengukuran baseline atau checkpoint yang masih kurang sebelum forecast dilanjutkan."
    elif derived.get("electrolyte_thickener_risk") == "high":
        required_inputs = ["viscosity_cp", "appearance"]
        reason_codes.append("f2_electrolyte_thickener_risk_high")
        priority = "high"
        action = "Prioritaskan pengukuran ulang viskositas dan review appearance pada checkpoint berikutnya."
    elif decision == "flag_high_risk" or f3.get("risk_band") == "high":
        reason_codes.append("f3_high_risk")
        priority = "high"
        action = "Eskalasi ke formulator untuk review sebelum siklus trial berikutnya; pertahankan observasi dan evidence saat ini."
    elif confidence in {"low", "medium"}:
        required_inputs = list(ALL_CHECKPOINT_FIELDS)
        reason_codes.append("f3_low_confidence" if confidence == "low" else "f3_medium_confidence")
        priority = "medium"
        action = "Kumpulkan satu checkpoint tambahan yang terkonfirmasi untuk mengurangi ketidakpastian sebelum keputusan lanjutan."
    else:
        reason_codes.append("continue_observation_protocol")

    return {
        "recommendation_type": "next_validation_step",
        "priority": priority,
        "recommended_action": action,
        "reason_codes": _unique(reason_codes),
        "required_inputs": _unique(required_inputs),
        "evidence_ids": list(f3.get("evidence_ids") or []),
        "data_origin": f3.get("data_origin", "synthetic_demo"),
        "requires_human_review": True,
        "limitations": [LIMITATION],
    }
