"""Kontrak inference F3 untuk adaptor API di masa depan."""
import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules" / "f3_stability_sentinel" / "inference.py"


def api():
    spec = importlib.util.spec_from_file_location("f3_inference", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AlwaysHighRiskModel:
    def predict_proba(self, frame):
        return [[0.1, 0.9] for _ in range(len(frame))]


class InferenceContractTests(unittest.TestCase):
    def test_forecast_exposes_synthetic_and_cv_concept_limits(self):
        payload = {
            "trial_id": "DEMO-API-001",
            "formula": [
                {"bahan": "Aqua", "pct": 90.0},
                {"bahan": "Xanthan Gum", "pct": 0.5},
                {"bahan": "Phenoxyethanol", "pct": 0.8},
                {"bahan": "Squalane", "pct": 3.7},
                {"bahan": "Ceteareth-20", "pct": 5.0},
            ],
            "process": {"heating_temp_c": 72, "homogenization_rpm": 2400, "mixing_time_min": 14},
            "storage_temperature_c": 40,
            "landmark_week": 4,
            "observations": [
                {"week": 0, "ph": 5.5, "viscosity_cp": 10000, "appearance": "uniform"},
                {"week": 4, "ph": 5.8, "viscosity_cp": 8500, "appearance": "uniform"},
            ],
        }
        artifact = api().LoadedArtifact(
            model=AlwaysHighRiskModel(),
            manifest={
                "model_version": "test-v1",
                "decision_threshold": 0.321,
                "feature_columns": [],
                "data_origin": "synthetic_demo",
                "cv_status": "concept_only_synthetic_render_pilot",
                "cv_limitations": ["CV is a concept-only pilot."],
            },
        )

        forecast = api().forecast(artifact, payload)

        self.assertEqual(forecast["decision"], "flag_high_risk")
        self.assertFalse(forecast["early_pass_issued"])
        self.assertEqual(forecast["data_origin"], "synthetic_demo")
        self.assertEqual(forecast["cv_status"], "concept_only_synthetic_render_pilot")
        self.assertTrue(forecast["requires_human_review"])
        self.assertIn("concept-only", forecast["cv_limitations"][0])

    def test_unknown_formula_abstains_before_model_prediction(self):
        artifact = api().LoadedArtifact(
            model=AlwaysHighRiskModel(),
            manifest={"model_version": "test-v1", "decision_threshold": 0.321},
        )
        payload = {
            "trial_id": "DEMO-API-UNKNOWN",
            "formula": [{"bahan": "Not A Real INCI", "pct": 1.0}],
            "process": {"heating_temp_c": 72, "homogenization_rpm": 2400, "mixing_time_min": 14},
            "storage_temperature_c": 40,
            "landmark_week": 4,
            "observations": [
                {"week": 0, "ph": 5.5, "viscosity_cp": 10000, "appearance": "uniform"},
                {"week": 4, "ph": 5.8, "viscosity_cp": 8500, "appearance": "uniform"},
            ],
        }

        forecast = api().forecast(artifact, payload)

        self.assertEqual(forecast["decision"], "abstain_human_review_required")
        self.assertTrue(forecast["requires_human_review"])
        self.assertNotIn("failure_risk", forecast)


if __name__ == "__main__":
    unittest.main()
