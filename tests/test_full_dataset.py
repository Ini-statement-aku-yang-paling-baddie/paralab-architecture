"""Kontrak generator dataset penuh 200 proyek / 600 trial."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_full_dataset.py"


def api():
    spec = importlib.util.spec_from_file_location("full_dataset", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FullDatasetTests(unittest.TestCase):
    def test_generates_architecture_v4_target_deterministically(self):
        self.assertTrue(SCRIPT.exists(), "Generator dataset penuh belum tersedia")
        m = api()
        data = m.generate(seed=2026)
        self.assertEqual(data, m.generate(seed=2026))
        self.assertEqual(len(data["projects"]), 200)
        self.assertEqual(len(data["formulas"]), 600)
        self.assertEqual(len(data["trials"]), 600)
        self.assertEqual(len(data["observation_series"]), 600)
        self.assertEqual(len(data["checkpoints"]), 4800)
        self.assertEqual(len(data["outcomes"]), 600)
        self.assertEqual(m.validate(data), [])

    def test_derived_views_are_split_safe_and_do_not_leak_future(self):
        m = api()
        data = m.generate(seed=2026)
        derived = m.derive(data)
        self.assertEqual(len(derived["journal_documents"]), 600)
        self.assertEqual(len(derived["f1_train_corpus"]), 420)
        self.assertEqual(len(derived["f5_examples"]), 4800)
        self.assertEqual(len(derived["forecast_features"]), len(derived["forecast_labels"]))
        self.assertGreater(len(derived["forecast_features"]), 400)
        self.assertGreater(len(derived["forecast_excluded"]), 0)
        checkpoints = {x["id"]: x for x in data["checkpoints"]}
        labels = {x["feature_id"]: x for x in derived["forecast_labels"]}
        for feature in derived["forecast_features"]:
            self.assertEqual([checkpoints[x]["week"] for x in feature["checkpoint_ids"]], [0, 1, 2, 4])
            self.assertNotIn("status", feature)
            self.assertNotIn("failure_week", feature)
            self.assertIn(labels[feature["id"]]["failed_by_12"], {0, 1})
        self.assertEqual(m.validate_derived(data, derived), [])

    def test_cli_build_is_deterministic_and_validates_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "full"
            command = [sys.executable, str(SCRIPT), "build", "--output", str(output), "--seed", "2026"]
            first_run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first_run.returncode, 0, first_run.stdout + first_run.stderr)
            first = {str(path.relative_to(output)): path.read_bytes() for path in output.rglob("*") if path.is_file()}
            second_run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second_run.returncode, 0, second_run.stdout + second_run.stderr)
            second = {str(path.relative_to(output)): path.read_bytes() for path in output.rglob("*") if path.is_file()}
            self.assertEqual(first, second)
            report = json.loads((output / "metrics.json").read_text())
            self.assertEqual(report["canonical_counts"]["checkpoints"], 4800)
            self.assertEqual(report["validation_errors"], [])
            validate = subprocess.run([sys.executable, str(SCRIPT), "validate", "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)


if __name__ == "__main__":
    unittest.main()
