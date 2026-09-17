"""Manifest artefak deployable untuk F3 Stability Sentinel.

Modul ini tidak memuat model dari sumber eksternal. Manifest mengikat artefak
joblib yang dibangun pipeline ParaLab dengan schema, threshold, provenance, dan
batas konsep CV yang wajib diteruskan ke API.
"""
from __future__ import annotations

import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping, Sequence

DATA_ORIGIN = "synthetic_demo"
CV_STATUS = "concept_only_synthetic_render_pilot"
CV_LIMITATIONS = [
    "CV is a concept-only pilot trained on procedural synthetic renders and is not validated on real laboratory photographs.",
    "CV output must not be used as a laboratory measurement, stability result, or automatic F3 input without human confirmation.",
]


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a local trusted artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def runtime_fingerprint() -> dict[str, str | None]:
    """Return versions that determine compatibility of a serialized sklearn model."""
    return {
        "python": platform.python_version(),
        "scikit_learn": _package_version("scikit-learn"),
        "pandas": _package_version("pandas"),
        "joblib": _package_version("joblib"),
    }


def validate_runtime(manifest: Mapping[str, Any]) -> None:
    """Reject a serialized model built under a different runtime fingerprint."""
    expected = manifest.get("runtime", {})
    actual = runtime_fingerprint()
    for name, expected_version in expected.items():
        if expected_version is not None and actual.get(name) != expected_version:
            raise ValueError(
                f"runtime mismatch for {name}: artifact={expected_version}, runtime={actual.get(name)}"
            )


def build_model_manifest(
    *,
    model_path: Path,
    training_report_path: Path,
    feature_columns: Sequence[str],
    f2_rule_version: str,
) -> dict[str, Any]:
    """Build deployment metadata from one local model and its training report."""
    with training_report_path.open(encoding="utf-8") as handle:
        report = json.load(handle)

    threshold = report.get("test_report", {}).get("decision_threshold")
    if threshold is None:
        raise ValueError("training report must contain test_report.decision_threshold")

    return {
        "artifact_schema_version": "f3-deployment-manifest-v1",
        "model_version": report.get("model_version", "unknown"),
        "feature_schema_version": report.get("feature_schema_version", "unknown"),
        "feature_columns": list(feature_columns),
        "decision_threshold": float(threshold),
        "f2_rule_version": f2_rule_version,
        "data_origin": DATA_ORIGIN,
        "prediction_type": "synthetic_demo_early_risk_forecast",
        "model_sha256": sha256_file(model_path),
        "training_report_sha256": sha256_file(training_report_path),
        "runtime": runtime_fingerprint(),
        "limitations": report.get("limitations", []),
        "cv_status": CV_STATUS,
        "cv_limitations": CV_LIMITATIONS,
    }


def write_model_manifest(
    *,
    output_path: Path,
    model_path: Path,
    training_report_path: Path,
    feature_columns: Sequence[str],
    f2_rule_version: str,
) -> dict[str, Any]:
    """Write a deterministic deployment manifest beside a trusted artifact."""
    manifest = build_model_manifest(
        model_path=model_path,
        training_report_path=training_report_path,
        feature_columns=feature_columns,
        f2_rule_version=f2_rule_version,
    )
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest
