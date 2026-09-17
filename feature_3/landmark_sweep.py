"""How much observation time can F3 actually save?

Trains one forecast per candidate landmark week and reports, for each, how many
week-12 decisions could be taken early at a fixed error budget. This is the
evidence the "12 weeks becomes N weeks" product claim needs; the headline
classification metrics in train_stability_sentinel.py do not answer it.

A trial is only decided early when its risk is outside an abstention band, so
the remaining trials keep being observed instead of being guessed.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from train_stability_sentinel import f2_formula_features, read_jsonl

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "data" / "full_synthetic" / "canonical"
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs" / "1"
LANDMARKS = [1, 2, 4, 6, 8]
HORIZON_WEEK = 12
PRECISION_FLOOR = 0.60


def load_canonical():
    series = {s["id"]: s for s in read_jsonl(CANONICAL / "observation_series.jsonl")}
    trials = {t["id"]: t for t in read_jsonl(CANONICAL / "trials.jsonl")}
    formulas = {f["id"]: f for f in read_jsonl(CANONICAL / "formulas.jsonl")}
    outcomes = {o["series_id"]: o for o in read_jsonl(CANONICAL / "outcomes.jsonl")}
    checkpoints = {}
    for checkpoint in read_jsonl(CANONICAL / "checkpoints.jsonl"):
        checkpoints.setdefault(checkpoint["series_id"], []).append(checkpoint)
    return series, trials, formulas, outcomes, checkpoints


def build_rows(landmark_week, canonical):
    series, trials, formulas, outcomes, checkpoints = canonical
    rows = []
    for series_id, item in series.items():
        outcome = outcomes[series_id]
        if outcome["status"] == "uncertain":
            continue
        early = sorted(
            (c for c in checkpoints[series_id] if c["week"] <= landmark_week),
            key=lambda c: c["week"],
        )
        baseline, landmark = early[0], early[-1]
        formula = formulas[trials[item["trial_id"]]["formula_id"]]

        weeks = np.array([c["week"] for c in early])
        viscosities = np.array([c["measurements"]["viscosity_cp"] for c in early])
        visc_baseline = baseline["measurements"]["viscosity_cp"]
        visc_current = landmark["measurements"]["viscosity_cp"]

        row = {"split": item["split"], "label": int(outcome["status"] == "failed")}
        row.update(f2_formula_features(formula["ingredients"], landmark["measurements"]["ph"]))
        row.update(formula["process"])
        row["storage_temperature_c"] = item["temperature_c"]
        row["viscosity_baseline_cp"] = visc_baseline
        row["viscosity_current_cp"] = visc_current
        row["viscosity_change_pct"] = (visc_current - visc_baseline) / visc_baseline * 100
        row["viscosity_slope_per_week"] = float(np.polyfit(weeks, viscosities, 1)[0])
        row["ph_baseline"] = baseline["measurements"]["ph"]
        row["ph_current"] = landmark["measurements"]["ph"]
        row["ph_change"] = landmark["measurements"]["ph"] - baseline["measurements"]["ph"]
        row["appearance_warning_count"] = sum(1 for c in early if c["appearance"] != "uniform")
        rows.append(row)
    return pd.DataFrame(rows)


FEATURES = [
    "f2_electrolyte_load", "f2_thickener_sensitivity", "f2_electrolyte_thickener_risk",
    "f2_emulsifier_balance_watch", "f2_ingredient_count", "oil_phase_ratio",
    "heating_temp_c", "homogenization_rpm", "mixing_time_min", "storage_temperature_c",
    "viscosity_baseline_cp", "viscosity_current_cp", "viscosity_change_pct",
    "viscosity_slope_per_week", "ph_baseline", "ph_current", "ph_change",
    "appearance_warning_count",
]


def select_alert_threshold(proba, y):
    """Lowest alert threshold that still meets the precision floor, so recall is
    as high as the false-alarm budget allows.

    There is deliberately no matching lower cut-off. F3 never issues an early
    pass: a false pass is a safety and liability event (Postles 2018), while a
    false alarm only costs development effort. The only two outputs are
    "flag high risk now" and "keep observing".
    """
    best = (0.0, 0.95)  # recall, threshold
    for threshold in np.arange(0.20, 0.96, 0.01):
        alerted = proba >= threshold
        if not alerted.any():
            continue
        precision = y[alerted].mean()
        recall = y[alerted].sum() / max(y.sum(), 1)
        if precision >= PRECISION_FLOOR and recall > best[0]:
            best = (float(recall), float(threshold))
    return best[1]


def main():
    canonical = load_canonical()
    report = {
        "question": "Berapa minggu siklus reformulasi yang bisa dihemat tanpa pernah mengeluarkan early pass?",
        "horizon_week": HORIZON_WEEK,
        "alert_precision_floor": PRECISION_FLOOR,
        "policy": "one-sided alert; F3 never issues an early pass",
        "evaluation_label": "synthetic-demo evaluation",
        "landmarks": [],
    }

    for landmark in LANDMARKS:
        frame = build_rows(landmark, canonical)
        train = frame[frame["split"] == "train"]
        validation = frame[frame["split"] == "validation"]
        test = frame[frame["split"] == "test"]

        model = Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ])
        model.fit(train[FEATURES], train["label"])

        val_proba = model.predict_proba(validation[FEATURES])[:, 1]
        threshold = select_alert_threshold(val_proba, validation["label"].to_numpy())

        test_proba = model.predict_proba(test[FEATURES])[:, 1]
        y_test = test["label"].to_numpy()
        alerted = test_proba >= threshold

        true_alerts = int((alerted & (y_test == 1)).sum())
        weeks_gained = HORIZON_WEEK - landmark

        report["landmarks"].append({
            "landmark_week": landmark,
            "weeks_gained_per_caught_failure": weeks_gained,
            "roc_auc": float(roc_auc_score(y_test, test_proba)),
            "alert_threshold": round(threshold, 3),
            "recall_failed": round(float(recall_score(y_test, alerted.astype(int), zero_division=0)), 4),
            "alert_precision": round(float(y_test[alerted].mean()) if alerted.any() else 0.0, 4),
            "alerts_issued": int(alerted.sum()),
            "failures_caught_early": true_alerts,
            "failures_total": int(y_test.sum()),
            "early_pass_issued": 0,
            "reformulation_weeks_saved": weeks_gained * true_alerts,
            "n_test": int(len(test)),
        })

    with open(OUTPUT_DIR / "landmark_sweep.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"{'week':>5} {'roc_auc':>8} {'recall':>8} {'precision':>10} {'caught':>8} "
          f"{'early_pass':>11} {'wks_saved':>10}")
    for entry in report["landmarks"]:
        print(f"{entry['landmark_week']:5d} {entry['roc_auc']:8.3f} {entry['recall_failed']:8.2%} "
              f"{entry['alert_precision']:10.2%} "
              f"{entry['failures_caught_early']:3d}/{entry['failures_total']:<4d} "
              f"{entry['early_pass_issued']:11d} {entry['reformulation_weeks_saved']:10d}")


if __name__ == "__main__":
    main()
