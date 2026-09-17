"""Does the F3 decision policy survive our hazard weights being wrong?

The generator's hazard weights are an assumption we invented, and the formula
features reconstruct that hazard almost perfectly (R2 ~ 0.99). Any single
accuracy figure from this data therefore measures our own assumption, not the
world.

This script answers a question that does not depend on knowing the true weights:
if each risk factor were worth anywhere between a tenth and twice what we
assumed, would the one-sided alert policy still meet its targets? A policy that
holds across that whole range is a claim we can defend; a point estimate is not.

Each replicate draws a fresh weight vector, regenerates the whole dataset from
it, retrains, re-tunes the threshold on validation, and evaluates once on test.
"""
import json
import random
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_full_dataset as generator  # noqa: E402
from landmark_sweep import FEATURES, build_rows  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs" / "1"
LANDMARK_WEEK = 4
REPLICATES = 30
RECALL_TARGET = 0.80
PRECISION_FLOOR = 0.60

# How wrong each assumed weight is allowed to be, as a multiplier of the value
# in HAZARD_WEIGHTS. Formula factors get the wider floor because "formula
# composition barely matters, only the measured trend does" is the scenario that
# would hurt the F2-to-F3 design most, so it has to be inside the test range.
WEIGHT_RANGES = {
    "electrolyte_thickener_risk": (0.1, 2.0),
    "emulsifier_missing": (0.1, 2.0),
    "electrolyte_load": (0.1, 2.0),
    "storage_40c": (0.3, 2.0),
    "process_penalty": (0.3, 2.0),
    "ph_deviation": (0.3, 2.0),
}


def draw_weights(rng):
    weights = dict(generator.HAZARD_WEIGHTS)
    scales = {}
    for factor, (low, high) in WEIGHT_RANGES.items():
        scale = rng.uniform(low, high)
        scales[factor] = round(scale, 3)
        weights[factor] = generator.HAZARD_WEIGHTS[factor] * scale
    return weights, scales


def canonical_from_generated(data):
    checkpoints = {}
    for checkpoint in data["checkpoints"]:
        checkpoints.setdefault(checkpoint["series_id"], []).append(checkpoint)
    return (
        {s["id"]: s for s in data["observation_series"]},
        {t["id"]: t for t in data["trials"]},
        {f["id"]: f for f in data["formulas"]},
        {o["series_id"]: o for o in data["outcomes"]},
        checkpoints,
    )


def select_alert_threshold(proba, y):
    """Same one-sided rule as landmark_sweep: lowest threshold meeting the
    precision floor. There is no lower cut-off, so no early pass can be issued."""
    best = (0.0, 0.95)
    for threshold in np.arange(0.20, 0.96, 0.01):
        alerted = proba >= threshold
        if not alerted.any():
            continue
        if y[alerted].mean() >= PRECISION_FLOOR:
            recall = y[alerted].sum() / max(y.sum(), 1)
            if recall > best[0]:
                best = (float(recall), float(threshold))
    return best[1]


def run_replicate(index, rng):
    weights, scales = draw_weights(rng)
    data = generator.generate(seed=2026, hazard_weights=weights)
    frame = build_rows(LANDMARK_WEEK, canonical_from_generated(data))

    train = frame[frame["split"] == "train"]
    validation = frame[frame["split"] == "validation"]
    test = frame[frame["split"] == "test"]
    failure_rate = float(frame["label"].mean())

    # A replicate with almost no failures (or almost nothing but) cannot say
    # anything useful about the policy, so it is reported rather than scored.
    degenerate = not (0.10 <= failure_rate <= 0.90) or train["label"].nunique() < 2

    result = {
        "replicate": index,
        "weight_scales": scales,
        "failure_rate": round(failure_rate, 4),
        "degenerate": degenerate,
    }
    if degenerate:
        return result

    model = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    model.fit(train[FEATURES], train["label"])

    threshold = select_alert_threshold(
        model.predict_proba(validation[FEATURES])[:, 1], validation["label"].to_numpy()
    )
    test_proba = model.predict_proba(test[FEATURES])[:, 1]
    y_test = test["label"].to_numpy()
    alerted = test_proba >= threshold

    result.update({
        "roc_auc": round(float(roc_auc_score(y_test, test_proba)), 4),
        "recall_failed": round(float(alerted[y_test == 1].mean()), 4),
        "alert_precision": round(float(y_test[alerted].mean()) if alerted.any() else 0.0, 4),
        "alert_threshold": round(threshold, 3),
        "early_pass_issued": 0,
        "meets_recall_target": bool(alerted[y_test == 1].mean() >= RECALL_TARGET),
    })
    return result


def summarise(values):
    return {
        "min": round(min(values), 4),
        "median": round(statistics.median(values), 4),
        "max": round(max(values), 4),
    }


def main():
    rng = random.Random(7)
    results = [run_replicate(i + 1, rng) for i in range(REPLICATES)]
    scored = [r for r in results if not r["degenerate"]]

    report = {
        "question": "Apakah kebijakan alert F3 bertahan bila bobot hazard yang kami asumsikan ternyata salah?",
        "method": (
            "Tiap replikat menarik vektor bobot baru dalam rentang WEIGHT_RANGES, "
            "meregenerasi seluruh dataset dari bobot itu, melatih ulang, menyetel "
            "threshold di validation, lalu mengevaluasi sekali di test."
        ),
        "landmark_week": LANDMARK_WEEK,
        "replicates": REPLICATES,
        "replicates_scored": len(scored),
        "replicates_degenerate": REPLICATES - len(scored),
        "recall_target": RECALL_TARGET,
        "precision_floor": PRECISION_FLOOR,
        "weight_ranges_as_multiple_of_assumed": WEIGHT_RANGES,
        "evaluation_label": "synthetic-demo evaluation",
        "summary": {
            "roc_auc": summarise([r["roc_auc"] for r in scored]),
            "recall_failed": summarise([r["recall_failed"] for r in scored]),
            "alert_precision": summarise([r["alert_precision"] for r in scored]),
            "failure_rate": summarise([r["failure_rate"] for r in scored]),
            "replicates_meeting_recall_target": sum(r["meets_recall_target"] for r in scored),
            "total_early_passes_issued": sum(r["early_pass_issued"] for r in scored),
        },
        "replicate_detail": results,
    }

    with open(OUTPUT_DIR / "weight_sensitivity.json", "w") as f:
        json.dump(report, f, indent=2)

    s = report["summary"]
    print(f"replikat dinilai: {len(scored)}/{REPLICATES} (degenerate: {report['replicates_degenerate']})")
    print(f"{'metrik':20} {'min':>8} {'median':>8} {'max':>8}")
    for key in ("roc_auc", "recall_failed", "alert_precision", "failure_rate"):
        print(f"{key:20} {s[key]['min']:8.3f} {s[key]['median']:8.3f} {s[key]['max']:8.3f}")
    print()
    print(f"memenuhi target recall >= {RECALL_TARGET}: {s['replicates_meeting_recall_target']}/{len(scored)}")
    print(f"total early pass dikeluarkan: {s['total_early_passes_issued']}")


if __name__ == "__main__":
    main()
