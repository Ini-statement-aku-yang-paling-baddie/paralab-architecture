"""F3 Predictive Stability Sentinel — tabular baseline training.

Per ARCHITECTURE-V4.md section 9.4: explainable tabular baselines
(Logistic Regression, Random Forest, Gradient Boosting) trained on
engineered trend features, not a deep time-series model. Evaluated
per section 13.3 and labeled synthetic-demo evaluation throughout.

Formula features come from the F2 guardrail engine, never from raw
ingredient percentages, per the section 9.6 responsibility boundary.
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier

    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "training"
OUTCOMES_PATH = ROOT / "data" / "full_synthetic" / "canonical" / "outcomes.jsonl"
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs" / "1"
# Fallback operating point; the real one is tuned on validation (select_threshold).
DEFAULT_THRESHOLD = 0.5

sys.path.insert(0, str(ROOT))
import f2_guardrail_v4 as f2  # noqa: E402


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_failure_weeks():
    return {rec["id"]: rec["failure_week"] for rec in read_jsonl(OUTCOMES_PATH)}


def f2_formula_features(formula_concentrations, final_ph):
    """Formula risk snapshot from the F2 guardrail engine (section 9.6:
    only canonical F2 features enter F3, never raw warning text)."""
    results = [
        f2.evaluate_ingredient(c.get("inci_name", c["ingredient_id"]), c["pct"])
        for c in formula_concentrations
    ]
    derived = f2.derive_features(results, ph=final_ph)
    oil_phase = sum(
        c["pct"]
        for c, r in zip(formula_concentrations, results)
        if "ingredient_id" in r and "emollient" in f2.by_id[r["ingredient_id"]]["functional_classes"]
    )
    return {
        "f2_electrolyte_load": int(derived["electrolyte_load"] == "high"),
        "f2_thickener_sensitivity": int(derived["thickener_sensitivity"] == "high"),
        "f2_electrolyte_thickener_risk": int(derived["electrolyte_thickener_risk"] == "high"),
        "f2_emulsifier_balance_watch": int(derived["emulsifier_balance_status"] == "watch"),
        "f2_ingredient_count": derived["ingredient_count"],
        "f2_compatibility_warning_count": derived["compatibility_warning_count"],
        "oil_phase_ratio": round(oil_phase, 4),
    }


def extract_row(record):
    feat = record["feature"]
    landmark_week = feat["landmark_week"]
    obs_by_week = {o["week"]: o for o in feat["observations"]}
    baseline = obs_by_week.get(0)
    landmark = obs_by_week.get(landmark_week)

    row = {
        "record_id": record["id"],
        "outcome_id": record["label"]["outcome_id"],
        "landmark_week": landmark_week,
        "abstain": baseline is None or landmark is None,
    }

    final_ph = landmark["measurements"]["ph"] if landmark else None
    row.update(f2_formula_features(feat["formula_concentrations"], final_ph))
    row.update(feat["process"])
    row["storage_temperature_c"] = feat.get("temperature_c")

    if row["abstain"]:
        row["label"] = record["label"]["failed_by_12"]
        return row

    weeks = np.array([o["week"] for o in feat["observations"] if o["week"] <= landmark_week])
    viscosities = np.array(
        [o["measurements"]["viscosity_cp"] for o in feat["observations"] if o["week"] <= landmark_week]
    )
    slope = float(np.polyfit(weeks, viscosities, 1)[0]) if len(weeks) >= 2 else 0.0

    visc_baseline = baseline["measurements"]["viscosity_cp"]
    visc_current = landmark["measurements"]["viscosity_cp"]
    ph_baseline = baseline["measurements"]["ph"]
    ph_current = landmark["measurements"]["ph"]

    row["viscosity_baseline_cp"] = visc_baseline
    row["viscosity_current_cp"] = visc_current
    row["viscosity_change_pct"] = (visc_current - visc_baseline) / visc_baseline * 100 if visc_baseline else 0.0
    row["viscosity_slope_per_week"] = slope
    row["ph_baseline"] = ph_baseline
    row["ph_current"] = ph_current
    row["ph_change"] = ph_current - ph_baseline
    row["appearance_warning_count"] = sum(
        1 for o in feat["observations"] if o["week"] <= landmark_week and o["appearance"] != "uniform"
    )
    row["label"] = record["label"]["failed_by_12"]
    return row


def build_frame(path):
    df = pd.DataFrame(extract_row(r) for r in read_jsonl(path))
    return df


# f2_compatibility_warning_count is kept on the row for the audit snapshot but
# excluded here: those warnings are halal/regulatory rules, not stability
# mechanisms, and they only act as a proxy for the preservative choice that
# f2_electrolyte_load already states directly.
FEATURE_COLUMNS = (
    [
        "f2_electrolyte_load",
        "f2_thickener_sensitivity",
        "f2_electrolyte_thickener_risk",
        "f2_emulsifier_balance_watch",
        "f2_ingredient_count",
        "oil_phase_ratio",
    ]
    + ["heating_temp_c", "homogenization_rpm", "mixing_time_min", "storage_temperature_c"]
    + [
        "viscosity_baseline_cp",
        "viscosity_current_cp",
        "viscosity_change_pct",
        "viscosity_slope_per_week",
        "ph_baseline",
        "ph_current",
        "ph_change",
        "appearance_warning_count",
    ]
)


def split_xy(df):
    usable = df[~df["abstain"]]
    return usable, usable[FEATURE_COLUMNS], usable["label"].astype(int)


def evaluate(model, X, y, threshold=0.5):
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "recall_failed": recall_score(y, pred, pos_label=1),
        "false_negative_rate": fn / (fn + tp) if (fn + tp) else 0.0,
        "precision_high_risk_alert": precision_score(y, pred, pos_label=1, zero_division=0),
        "pr_auc": average_precision_score(y, proba),
        "roc_auc": roc_auc_score(y, proba),
        "brier_score": brier_score_loss(y, proba),
        "decision_threshold": round(float(threshold), 4),
        "n": int(len(y)),
    }


def select_threshold(model, X, y):
    """Operating point chosen on validation with F-beta (beta=2), because
    section 13.3 treats a missed high-risk batch as the costliest error while
    still penalising over-flagging healthy trials."""
    proba = model.predict_proba(X)[:, 1]
    candidates = np.unique(np.round(proba, 3))
    scored = [(fbeta_score(y, (proba >= t).astype(int), beta=2, zero_division=0), t) for t in candidates]
    return float(max(scored)[1])


def lead_time_proxy(usable_df, proba, failure_weeks, threshold=0.5):
    """Mean weeks between the landmark-week high-risk alert and actual failure_week,
    among true positives (correctly flagged high-risk trials that did fail)."""
    high_risk = proba >= threshold
    lead_times = []
    for (_, row), flagged in zip(usable_df.iterrows(), high_risk):
        if not flagged or row["label"] != 1:
            continue
        fw = failure_weeks.get(row["outcome_id"])
        if fw is not None and fw >= row["landmark_week"]:
            lead_times.append(fw - row["landmark_week"])
    return {
        "mean_weeks_before_failure": float(np.mean(lead_times)) if lead_times else None,
        "n_true_positive_with_known_failure_week": len(lead_times),
    }


def build_sample_forecast(row, proba_value, threshold=DEFAULT_THRESHOLD, model_version="stability-sentinel-v1"):
    risk_band = "high" if proba_value >= threshold else "medium" if proba_value >= threshold / 2 else "low"
    margin = abs(proba_value - threshold)
    confidence = "high" if margin > 0.35 else "medium" if margin > 0.15 else "low"
    # One-sided by design: F3 either raises an alert or says keep observing. It
    # never clears a trial early, because a false pass is a safety and liability
    # event while a false alarm only costs development effort (Postles 2018).
    decision = "flag_high_risk" if proba_value >= threshold else "continue_observation"
    action = {
        "flag_high_risk": "Mulai reformulasi paralel; uji stabilitas tetap berjalan penuh.",
        "continue_observation": "Lanjutkan observasi sesuai protokol; belum ada dasar untuk eskalasi.",
    }[decision]

    key_signals = [
        {
            "feature": "viscosity_change_pct",
            "value": round(float(row["viscosity_change_pct"]), 2),
            "interpretation": "Viskositas turun dari baseline."
            if row["viscosity_change_pct"] < 0
            else "Viskositas naik dari baseline.",
        },
        {
            "feature": "ph_change",
            "value": round(float(row["ph_change"]), 3),
            "interpretation": "Perubahan pH dari baseline ke checkpoint saat ini.",
        },
    ]
    if row["f2_electrolyte_thickener_risk"]:
        key_signals.append({
            "feature": "electrolyte_thickener_risk",
            "value": "high",
            "source": "f2-guardrail-derived-features",
            "interpretation": "Elektrolit hadir bersama thickener yang sensitif elektrolit.",
        })
    if row["f2_emulsifier_balance_watch"]:
        key_signals.append({
            "feature": "emulsifier_balance_status",
            "value": "watch",
            "source": "f2-guardrail-derived-features",
            "interpretation": "Tidak ada emulsifier terdeteksi pada formula.",
        })

    return {
        "trial_id": row["record_id"],
        "forecast_week": int(row["landmark_week"]),
        "forecast_horizon": "week_12",
        "prediction_type": "synthetic_demo_early_risk_forecast",
        "failure_risk": round(float(proba_value), 4),
        "risk_band": risk_band,
        "decision": decision,
        "early_pass_issued": False,
        "likely_failure_mode": "unsupported_no_multiclass_label",
        "confidence": confidence,
        "key_signals": key_signals,
        "evidence_ids": [],
        "recommended_action": action,
        "limitations": [
            "Forecast dilatih dan dievaluasi menggunakan synthetic demo data dari seeded hazard model.",
            "Forecast tidak menggantikan formal stability validation.",
            "evidence_ids kosong karena integrasi F1 belum dibangun di baseline ini.",
            "F3 tidak pernah menyatakan formula lolos lebih awal; uji stabilitas tetap berjalan penuh.",
        ],
        "model_version": model_version,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failure_weeks = load_failure_weeks()

    train_df = build_frame(DATA_DIR / "f3_train.jsonl")
    val_df = build_frame(DATA_DIR / "f3_validation.jsonl")
    test_df = build_frame(DATA_DIR / "f3_test.jsonl")

    train_usable, X_train, y_train = split_xy(train_df)
    val_usable, X_val, y_val = split_xy(val_df)
    test_usable, X_test, y_test = split_xy(test_df)

    candidates = {
        "logistic_regression": Pipeline(
            [("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))]
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=6, class_weight="balanced", random_state=2026
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=2026),
    }
    if HAS_XGBOOST:
        candidates["xgboost"] = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            eval_metric="logloss",
            random_state=2026,
        )

    val_reports = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        val_reports[name] = evaluate(model, X_val, y_val)

    selected_name = max(val_reports, key=lambda n: val_reports[n]["pr_auc"])
    base_model = candidates[selected_name]

    # Calibration step (ARCHITECTURE-V4.md section 9.4): compare raw vs
    # sigmoid-calibrated probabilities on validation, keep whichever has the
    # lower Brier score, since displayed probabilities must be meaningful.
    calibrated_model = CalibratedClassifierCV(clone(base_model), method="sigmoid", cv=3)
    calibrated_model.fit(X_train, y_train)
    calibrated_val_report = evaluate(calibrated_model, X_val, y_val)

    if calibrated_val_report["brier_score"] < val_reports[selected_name]["brier_score"]:
        selected_model = calibrated_model
        calibration_applied = True
    else:
        selected_model = base_model
        calibration_applied = False

    decision_threshold = select_threshold(selected_model, X_val, y_val)
    test_report = evaluate(selected_model, X_test, y_test, decision_threshold)

    proba_test = selected_model.predict_proba(X_test)[:, 1]
    lead_time = lead_time_proxy(test_usable, proba_test, failure_weeks, decision_threshold)

    calib_curve_true, calib_curve_pred = calibration_curve(y_test, proba_test, n_bins=5, strategy="quantile")
    calibration_report = {
        "calibration_applied": calibration_applied,
        "raw_brier_score_validation": val_reports[selected_name]["brier_score"],
        "calibrated_brier_score_validation": calibrated_val_report["brier_score"],
        "reliability_curve_test": [
            {"mean_predicted_risk": float(p), "observed_failure_rate": float(t)}
            for p, t in zip(calib_curve_pred, calib_curve_true)
        ],
    }

    coverage = {
        split_name: {
            "total_rows": int(len(df)),
            "abstained_rows": int(df["abstain"].sum()),
            "abstention_rate": float(df["abstain"].mean()),
        }
        for split_name, df in [("train", train_df), ("validation", val_df), ("test", test_df)]
    }

    perm = permutation_importance(
        selected_model, X_val, y_val, n_repeats=20, random_state=2026, scoring="average_precision"
    )
    permutation_ranked = sorted(
        zip(FEATURE_COLUMNS, perm.importances_mean, perm.importances_std),
        key=lambda t: abs(t[1]),
        reverse=True,
    )[:8]

    joblib.dump(selected_model, OUTPUT_DIR / "stability_sentinel_model.joblib")

    predictions = test_usable[["record_id"]].copy()
    predictions["failure_risk"] = proba_test
    predictions["risk_band"] = np.where(
        proba_test >= decision_threshold, "high", np.where(proba_test >= decision_threshold / 2, "medium", "low")
    )
    predictions["label_failed_by_12"] = y_test.values
    predictions["prediction_type"] = "synthetic_demo_early_risk_forecast"
    predictions.to_csv(OUTPUT_DIR / "test_predictions.csv", index=False)

    model_version = f"stability-sentinel-{selected_name}-v1{'-calibrated' if calibration_applied else ''}"
    ranked_idx = np.argsort(-proba_test)
    sample_rows = list(ranked_idx[:3]) + [ranked_idx[-1]]
    sample_forecasts = [
        build_sample_forecast(test_usable.iloc[i], proba_test[i], decision_threshold, model_version)
        for i in sample_rows
    ]
    with open(OUTPUT_DIR / "sample_forecasts.json", "w") as f:
        json.dump(sample_forecasts, f, indent=2)

    report = {
        "feature_schema_version": "stability-sentinel-v1",
        "model_version": model_version,
        "model_selection": {
            "candidates_evaluated_on_validation": val_reports,
            "selected_model": selected_name,
            "selection_rule": "max pr_auc on validation split",
            "xgboost_available": HAS_XGBOOST,
        },
        "calibration": calibration_report,
        "test_report": {
            **test_report,
            "threshold_selection_rule": "max F-beta (beta=2) on validation",
            "evaluation_label": "synthetic-demo evaluation",
        },
        "lead_time_proxy_weeks": lead_time,
        "coverage": coverage,
        "top_features_native_importance": [
            {"feature": f, "weight": float(w)}
            for f, w in sorted(
                zip(
                    FEATURE_COLUMNS,
                    (
                        base_model.named_steps["clf"].coef_[0]
                        if hasattr(base_model, "named_steps")
                        else base_model.feature_importances_
                    ),
                ),
                key=lambda kv: abs(kv[1]),
                reverse=True,
            )[:8]
        ],
        "top_features_permutation_importance": [
            {"feature": f, "mean_importance": float(m), "std": float(s)} for f, m, s in permutation_ranked
        ],
        "limitations": [
            "Forecast dilatih dan dievaluasi menggunakan synthetic demo data dari seeded hazard model.",
            "Forecast tidak menggantikan formal stability validation.",
            "likely_failure_mode belum tersedia karena dataset hanya punya label biner failed_by_12.",
            "appearance_warning_count belum informatif karena seluruh observasi synthetic berlabel 'uniform'.",
            "evidence_ids kosong karena integrasi F1 belum dibangun di baseline ini.",
        ],
    }
    with open(OUTPUT_DIR / "training_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
