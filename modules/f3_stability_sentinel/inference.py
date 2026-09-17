"""Inference F3 yang dapat diuji sebelum dibungkus oleh API.

Input memakai istilah domain. Modul ini menghitung feature internal lewat F2 dan
trend observasi; client tidak mengirim vector feature F3 secara langsung.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import joblib
import pandas as pd

from modules import f2_guardrail as f2
from modules.f3_stability_sentinel.deployment import sha256_file, validate_runtime
from modules.f3_stability_sentinel.train_stability_sentinel import (
    FEATURE_COLUMNS,
    build_sample_forecast,
    extract_row,
)


@dataclass(frozen=True)
class LoadedArtifact:
    """A local, hash-verified F3 model with its deployment manifest."""

    model: Any
    manifest: dict[str, Any]


def load_artifact(artifact_dir: Path) -> LoadedArtifact:
    """Load a model only when its local manifest matches the artifact hash."""
    model_path = artifact_dir / "stability_sentinel_model.joblib"
    manifest_path = artifact_dir / "model_manifest.json"
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    if manifest.get("model_sha256") != sha256_file(model_path):
        raise ValueError("model SHA-256 does not match deployment manifest")
    if manifest.get("feature_columns") != FEATURE_COLUMNS:
        raise ValueError("feature schema does not match the deployed F3 runtime")
    if manifest.get("data_origin") != "synthetic_demo":
        raise ValueError("this prototype only deploys an explicitly synthetic-demo artifact")
    validate_runtime(manifest)

    return LoadedArtifact(model=joblib.load(model_path), manifest=manifest)


def _abstention(trial_id: str, reason: str, screening: dict[str, Any]) -> dict[str, Any]:
    return {
        "trial_id": trial_id,
        "prediction_type": "synthetic_demo_early_risk_forecast",
        "data_origin": "synthetic_demo",
        "decision": "abstain_human_review_required",
        "early_pass_issued": False,
        "requires_human_review": True,
        "reason": reason,
        "f2_screening": screening,
        "limitations": [
            "Tidak ada forecast F3 diterbitkan sebelum formula dan checkpoint dapat ditinjau manusia.",
            "ParaLab adalah prototype synthetic-demo dan tidak menggantikan formal stability validation.",
        ],
    }


def _training_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    observations = [
        {
            "week": observation["week"],
            "appearance": observation.get("appearance", "uniform"),
            "measurements": {
                "ph": observation["ph"],
                "viscosity_cp": observation["viscosity_cp"],
            },
        }
        for observation in payload["observations"]
    ]
    return {
        "id": payload["trial_id"],
        "label": {"failed_by_12": 0, "outcome_id": "inference-not-labeled"},
        "feature": {
            "landmark_week": payload["landmark_week"],
            "temperature_c": payload["storage_temperature_c"],
            "formula_concentrations": [
                {"inci_name": item["bahan"], "pct": item["pct"]} for item in payload["formula"]
            ],
            "process": payload["process"],
            "observations": observations,
        },
    }


def forecast(artifact: LoadedArtifact, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Produce a one-sided F3 forecast or abstain before model inference."""
    trial_id = str(payload["trial_id"])
    formula = payload["formula"]
    screening = f2.screen_formula(formula, konteks=payload.get("context"))
    if screening["overall_status"] in {"blocked", "unknown"}:
        return _abstention(
            trial_id,
            "F2 menemukan bahan blocked atau unknown; human review wajib sebelum forecast F3.",
            screening,
        )

    row = extract_row(_training_record(payload))
    if row["abstain"]:
        return _abstention(
            trial_id,
            "Checkpoint baseline minggu 0 atau checkpoint landmark belum lengkap.",
            screening,
        )

    feature_columns = artifact.manifest.get("feature_columns") or FEATURE_COLUMNS
    if feature_columns != FEATURE_COLUMNS:
        raise ValueError("artifact feature columns do not match inference runtime")
    probability = float(artifact.model.predict_proba(pd.DataFrame([row])[feature_columns])[0][1])
    result = build_sample_forecast(
        row,
        probability,
        threshold=float(artifact.manifest["decision_threshold"]),
        model_version=artifact.manifest["model_version"],
    )
    result.update(
        {
            "data_origin": artifact.manifest.get("data_origin", "synthetic_demo"),
            "requires_human_review": True,
            "f2_screening": screening,
            "cv_status": artifact.manifest.get("cv_status", "concept_only_synthetic_render_pilot"),
            "cv_limitations": artifact.manifest.get("cv_limitations", []),
        }
    )
    return result
