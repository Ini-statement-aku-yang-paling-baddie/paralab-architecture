"""Kontrak artefak deployable untuk F3 Stability Sentinel."""
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules" / "f3_stability_sentinel" / "deployment.py"


def api():
    spec = importlib.util.spec_from_file_location("f3_deployment", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentManifestTests(unittest.TestCase):
    def test_manifest_binds_model_schema_threshold_and_synthetic_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "model.joblib"
            report_path = root / "training_report.json"
            model_path.write_bytes(b"trusted-model-bytes")
            report_path.write_text(
                json.dumps(
                    {
                        "model_version": "stability-sentinel-random_forest-v1",
                        "feature_schema_version": "stability-sentinel-v1",
                        "test_report": {"decision_threshold": 0.321},
                        "limitations": ["Synthetic demo only."],
                    }
                ),
                encoding="utf-8",
            )

            manifest = api().build_model_manifest(
                model_path=model_path,
                training_report_path=report_path,
                feature_columns=["ph_change", "viscosity_change_pct"],
                f2_rule_version="v4.0",
            )

            self.assertEqual(manifest["model_version"], "stability-sentinel-random_forest-v1")
            self.assertEqual(manifest["decision_threshold"], 0.321)
            self.assertEqual(manifest["feature_columns"], ["ph_change", "viscosity_change_pct"])
            self.assertEqual(manifest["data_origin"], "synthetic_demo")
            self.assertEqual(manifest["cv_status"], "concept_only_synthetic_render_pilot")
            self.assertEqual(manifest["model_sha256"], hashlib.sha256(b"trusted-model-bytes").hexdigest())
            self.assertIn("not validated on real laboratory photographs", manifest["cv_limitations"][0])

    def test_manifest_rejects_report_without_deployment_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_path = root / "model.joblib"
            report_path = root / "training_report.json"
            model_path.write_bytes(b"trusted-model-bytes")
            report_path.write_text(json.dumps({"test_report": {}}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "decision_threshold"):
                api().build_model_manifest(
                    model_path=model_path,
                    training_report_path=report_path,
                    feature_columns=["ph_change"],
                    f2_rule_version="v4.0",
                )

    def test_runtime_mismatch_rejects_incompatible_serialized_model(self):
        with self.assertRaisesRegex(ValueError, "runtime mismatch"):
            api().validate_runtime({"runtime": {"python": "0.0.0"}})


if __name__ == "__main__":
    unittest.main()
