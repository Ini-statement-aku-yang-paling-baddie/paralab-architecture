"""Kontrak feature engineering dan fallback F3 Predictive Stability Sentinel."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modules" / "f3_stability_sentinel" / "train_stability_sentinel.py"

try:
    import pandas  # noqa: F401
    import sklearn  # noqa: F401
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False


def api():
    spec = importlib.util.spec_from_file_location("train_stability_sentinel", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record(ingredients, observations, landmark_week=4, failed=1):
    return {
        "id": "TRAIN-TEST-001",
        "label": {"failed_by_12": failed, "outcome_id": "TEST-001-OUT"},
        "feature": {
            "landmark_week": landmark_week,
            "horizon_week": 12,
            "temperature_c": 40,
            "formula_concentrations": ingredients,
            "process": {"heating_temp_c": 72, "homogenization_rpm": 2400, "mixing_time_min": 14},
            "observations": observations,
        },
    }


def series(values):
    return [
        {"week": week, "appearance": appearance,
         "measurements": {"ph": ph, "viscosity_cp": viscosity},
         "quality": {"ph": "observed", "viscosity_cp": "observed"}}
        for week, ph, viscosity, appearance in values
    ]


RISKY_FORMULA = [
    {"ingredient_id": "ING:AQUA", "inci_name": "Aqua", "pct": 90.0},
    {"ingredient_id": "ING:CARBOMER", "inci_name": "Carbomer", "pct": 0.5},
    {"ingredient_id": "ING:SODIUM_BENZOATE", "inci_name": "Sodium Benzoate", "pct": 0.3},
    {"ingredient_id": "ING:SQUALANE", "inci_name": "Squalane", "pct": 4.2},
    {"ingredient_id": "ING:CETEARETH_20", "inci_name": "Ceteareth-20", "pct": 5.0},
]

SAFE_FORMULA = [
    {"ingredient_id": "ING:AQUA", "inci_name": "Aqua", "pct": 90.0},
    {"ingredient_id": "ING:XANTHAN_GUM", "inci_name": "Xanthan Gum", "pct": 0.5},
    {"ingredient_id": "ING:PHENOXYETHANOL", "inci_name": "Phenoxyethanol", "pct": 0.8},
    {"ingredient_id": "ING:SQUALANE", "inci_name": "Squalane", "pct": 3.7},
    {"ingredient_id": "ING:CETEARETH_20", "inci_name": "Ceteareth-20", "pct": 5.0},
]


@unittest.skipUnless(DEPS_AVAILABLE, "butuh pandas + scikit-learn (requirements/f3_stability_sentinel.txt)")
class FeatureExtractionTests(unittest.TestCase):
    def test_trend_features_come_from_baseline_and_landmark_only(self):
        m = api()
        row = m.extract_row(record(SAFE_FORMULA, series([
            (0, 5.50, 10000, "uniform"),
            (1, 5.55, 9800, "uniform"),
            (2, 5.60, 9600, "creaming"),
            (4, 5.70, 9000, "uniform"),
            (8, 5.90, 5000, "separated"),
        ])))
        self.assertFalse(row["abstain"])
        self.assertEqual(row["viscosity_baseline_cp"], 10000)
        self.assertEqual(row["viscosity_current_cp"], 9000)
        self.assertAlmostEqual(row["viscosity_change_pct"], -10.0)
        self.assertAlmostEqual(row["ph_change"], 0.20, places=6)
        # week 8 is past the landmark and must not leak into the feature row
        self.assertEqual(row["appearance_warning_count"], 1)
        self.assertLess(row["viscosity_slope_per_week"], 0)

    def test_formula_features_are_derived_by_f2_not_raw_percentages(self):
        m = api()
        self.assertFalse([c for c in m.FEATURE_COLUMNS if c.startswith("pct_")])

        risky = m.extract_row(record(RISKY_FORMULA, series([
            (0, 5.5, 10000, "uniform"), (4, 5.6, 9000, "uniform")])))
        safe = m.extract_row(record(SAFE_FORMULA, series([
            (0, 5.5, 10000, "uniform"), (4, 5.6, 9000, "uniform")])))

        self.assertEqual(risky["f2_electrolyte_thickener_risk"], 1)
        self.assertEqual(risky["f2_thickener_sensitivity"], 1)
        self.assertEqual(risky["f2_electrolyte_load"], 1)
        self.assertEqual(safe["f2_electrolyte_thickener_risk"], 0)
        self.assertEqual(safe["f2_emulsifier_balance_watch"], 0)

    def test_formula_without_emulsifier_is_flagged_for_watch(self):
        m = api()
        without_emulsifier = [c for c in SAFE_FORMULA if c["ingredient_id"] != "ING:CETEARETH_20"]
        row = m.extract_row(record(without_emulsifier, series([
            (0, 5.5, 10000, "uniform"), (4, 5.6, 9000, "uniform")])))
        self.assertEqual(row["f2_emulsifier_balance_watch"], 1)

    def test_missing_post_baseline_checkpoint_abstains_instead_of_forecasting(self):
        m = api()
        row = m.extract_row(record(SAFE_FORMULA, series([(0, 5.5, 10000, "uniform")])))
        self.assertTrue(row["abstain"])
        self.assertNotIn("viscosity_change_pct", row)


@unittest.skipUnless(DEPS_AVAILABLE, "butuh pandas + scikit-learn (requirements/f3_stability_sentinel.txt)")
class ForecastContractTests(unittest.TestCase):
    def test_lead_time_counts_only_flagged_trials_that_actually_failed(self):
        import numpy as np
        import pandas as pd
        m = api()
        frame = pd.DataFrame([
            {"outcome_id": "A", "landmark_week": 4, "label": 1},  # flagged, failed week 12
            {"outcome_id": "B", "landmark_week": 4, "label": 1},  # not flagged
            {"outcome_id": "C", "landmark_week": 4, "label": 0},  # flagged but passed
        ])
        proba = np.array([0.95, 0.10, 0.90])
        result = m.lead_time_proxy(frame, proba, {"A": 12, "B": 8, "C": None})
        self.assertEqual(result["n_true_positive_with_known_failure_week"], 1)
        self.assertEqual(result["mean_weeks_before_failure"], 8.0)

    def test_confidence_is_derived_from_margin_not_hardcoded(self):
        m = api()
        row = {"record_id": "T1", "landmark_week": 4, "viscosity_change_pct": -9.0, "ph_change": 0.2,
               "f2_electrolyte_thickener_risk": 1, "f2_emulsifier_balance_watch": 0}
        confident = m.build_sample_forecast(row, 0.97)
        borderline = m.build_sample_forecast(row, 0.52)
        self.assertEqual(confident["confidence"], "high")
        self.assertEqual(borderline["confidence"], "low")

    def test_low_risk_never_clears_a_trial_early(self):
        """A false pass is a safety event, so the only two outputs are an alert
        and 'keep observing' — never an early release."""
        m = api()
        row = {"record_id": "T1", "landmark_week": 4, "viscosity_change_pct": -0.1, "ph_change": 0.01,
               "f2_electrolyte_thickener_risk": 0, "f2_emulsifier_balance_watch": 0}
        for risk in (0.001, 0.05, 0.2, 0.49):
            forecast = m.build_sample_forecast(row, risk, threshold=0.5)
            self.assertEqual(forecast["decision"], "continue_observation")
            self.assertFalse(forecast["early_pass_issued"])
            self.assertIn("lanjutkan observasi", forecast["recommended_action"].lower())

    def test_high_risk_triggers_parallel_reformulation_not_test_truncation(self):
        m = api()
        row = {"record_id": "T1", "landmark_week": 4, "viscosity_change_pct": -9.0, "ph_change": 0.4,
               "f2_electrolyte_thickener_risk": 1, "f2_emulsifier_balance_watch": 0}
        forecast = m.build_sample_forecast(row, 0.92, threshold=0.5)
        self.assertEqual(forecast["decision"], "flag_high_risk")
        self.assertFalse(forecast["early_pass_issued"])
        self.assertIn("reformulasi", forecast["recommended_action"].lower())
        self.assertTrue(any("tidak pernah menyatakan formula lolos" in x for x in forecast["limitations"]))

    def test_f2_risk_signal_is_surfaced_with_its_source(self):
        m = api()
        row = {"record_id": "T1", "landmark_week": 4, "viscosity_change_pct": -9.0, "ph_change": 0.2,
               "f2_electrolyte_thickener_risk": 1, "f2_emulsifier_balance_watch": 0}
        signals = m.build_sample_forecast(row, 0.9)["key_signals"]
        electrolyte = [s for s in signals if s["feature"] == "electrolyte_thickener_risk"]
        self.assertEqual(len(electrolyte), 1)
        self.assertIn("source", electrolyte[0])


if __name__ == "__main__":
    unittest.main()
