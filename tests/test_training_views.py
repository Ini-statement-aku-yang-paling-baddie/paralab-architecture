"""Kontrak gabungan train/test: public evidence boleh masuk F1, tetapi tidak F3 tanpa eligibility."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_training_views.py"


def api():
    spec = importlib.util.spec_from_file_location("training_views", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrainingViewsTests(unittest.TestCase):
    def test_combined_views_keep_public_rows_out_of_f3_and_add_them_to_f1_catalog(self):
        self.assertTrue(SCRIPT.exists(), "Builder training views belum tersedia")
        m = api()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "training"
            result = m.build(out)
            self.assertEqual(result["validation_errors"], [])
            forecast = [json.loads(x) for x in (out / "f3_forecast_train.jsonl").read_text().splitlines()]
            evidence = [json.loads(x) for x in (out / "f1_evidence_catalog.jsonl").read_text().splitlines()]
            report = json.loads((out / "training_report.json").read_text())
            train_rows = [json.loads(x) for x in (out / "f3_train.jsonl").read_text().splitlines()]
            validation_rows = [json.loads(x) for x in (out / "f3_validation.jsonl").read_text().splitlines()]
            test_rows = [json.loads(x) for x in (out / "f3_test.jsonl").read_text().splitlines()]
            self.assertEqual({x["split"] for x in train_rows}, {"train"})
            self.assertEqual({x["split"] for x in validation_rows}, {"validation"})
            self.assertEqual({x["split"] for x in test_rows}, {"test"})
            self.assertEqual(len(train_rows) + len(validation_rows) + len(test_rows), len(forecast))
            self.assertTrue(forecast)
            self.assertEqual({x["data_origin"] for x in forecast}, {"synthetic_demo"})
            self.assertEqual(len(forecast), 515)
            self.assertIn("observed_public", {x["data_origin"] for x in evidence})
            self.assertEqual(report["f1"]["synthetic_demo_documents"], 420)
            self.assertEqual(report["f1"]["observed_public_documents"], 15)
            self.assertEqual(report["f3"]["synthetic_demo_rows_included"], 515)
            self.assertEqual(report["f3"]["public_observed_rows_included"], 0)
            self.assertEqual(m.validate_directory(out), [])


if __name__ == "__main__":
    unittest.main()
