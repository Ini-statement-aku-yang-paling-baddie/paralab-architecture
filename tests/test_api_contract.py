"""HTTP contract untuk backend ParaLab F3."""
import importlib.util
import sys
from pathlib import Path
import unittest
import warnings

warnings.filterwarnings(
    "ignore",
    message="'asyncio.iscoroutinefunction' is deprecated",
    category=DeprecationWarning,
)

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "api" / "app.py"


def api_module():
    spec = importlib.util.spec_from_file_location("paralab_api", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AlwaysLowRiskModel:
    def predict_proba(self, frame):
        return [[0.9, 0.1] for _ in range(len(frame))]


PAYLOAD = {
    "trial_id": "API-CONTRACT-001",
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
        {"week": 4, "ph": 5.55, "viscosity_cp": 9900, "appearance": "uniform"},
    ],
}


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        inference = __import__("modules.f3_stability_sentinel.inference", fromlist=["LoadedArtifact"])
        self.artifact = inference.LoadedArtifact(
            model=AlwaysLowRiskModel(),
            manifest={
                "model_version": "test-v1",
                "decision_threshold": 0.321,
                "feature_columns": [],
                "data_origin": "synthetic_demo",
                "cv_status": "concept_only_synthetic_render_pilot",
                "cv_limitations": ["CV is a concept-only pilot."],
            },
        )
        self.client = TestClient(api_module().create_app(artifact_loader=lambda: self.artifact))

    def test_health_declares_synthetic_and_cv_concept_scope(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["data_origin"], "synthetic_demo")
        self.assertEqual(body["cv_status"], "concept_only_synthetic_render_pilot")

    def test_forecast_endpoint_never_issues_early_pass(self):
        response = self.client.post("/v1/f3/forecasts", json=PAYLOAD)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["decision"], "continue_observation")
        self.assertFalse(body["early_pass_issued"])
        self.assertTrue(body["requires_human_review"])


if __name__ == "__main__":
    unittest.main()
