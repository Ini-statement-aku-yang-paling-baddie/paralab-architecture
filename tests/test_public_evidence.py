"""Kontrak ingest evidence publik: factual, berprovenance, dan tidak mencemari F3."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_public_evidence.py"
SEED = ROOT / "sources" / "public" / "PMC7407566_tables_2_5.json"


def api():
    spec = importlib.util.spec_from_file_location("public_evidence", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicEvidenceTests(unittest.TestCase):
    def test_source_has_real_table_provenance_and_no_invented_trajectory(self):
        self.assertTrue(SCRIPT.exists(), "CLI public evidence belum tersedia")
        self.assertTrue(SEED.exists(), "Seed ekstraksi paper belum tersedia")
        m = api()
        source = json.loads(SEED.read_text(encoding="utf-8"))
        self.assertEqual(source["doi"], "10.3390/pharmaceutics12070647")
        self.assertEqual(source["license"], "CC-BY-4.0")
        self.assertEqual(len(source["formulations"]), 15)
        self.assertEqual({x["paper_formula_id"] for x in source["formulations"]}, {f"F{i}" for i in range(1, 16)})
        self.assertEqual(source["measurements"]["ph"]["timepoint_days"], 1)
        self.assertEqual(source["measurements"]["instability_index"]["timepoint_days"], 4)
        self.assertTrue(all(x["data_origin"] == "observed_public" for x in source["formulations"]))
        self.assertTrue(all(x["not_a_lab_recipe"] for x in source["formulations"]))
        self.assertEqual(m.validate_source(source), [])

    def test_build_produces_evidence_and_explicitly_excludes_incompatible_f3_rows(self):
        m = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "public"
            result = m.build(output)
            self.assertEqual(result["validation_errors"], [])
            index = json.loads((output / "source_index.json").read_text())
            rows = [json.loads(line) for line in (output / "observed_formulations.jsonl").read_text().splitlines()]
            f1 = [json.loads(line) for line in (output / "f1_evidence_documents.jsonl").read_text().splitlines()]
            excluded = [json.loads(line) for line in (output / "f3_excluded_candidates.jsonl").read_text().splitlines()]
            self.assertEqual(index["source_count"], 1)
            self.assertEqual((len(rows), len(f1), len(excluded)), (15, 15, 15))
            self.assertTrue(all(x["training_eligibility"]["f3"] == "excluded" for x in rows))
            self.assertTrue(all("not_longitudinal_to_landmark_week_4" in x["reasons"] for x in excluded))
            self.assertTrue(all("synthetic" not in x["text"].lower() for x in f1))
            self.assertEqual(m.validate_directory(output), [])

    def test_validator_rejects_claiming_public_cross_sectional_rows_as_f3_labels(self):
        m = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "public"
            m.build(output)
            path = output / "f3_excluded_candidates.jsonl"
            payload = [json.loads(line) for line in path.read_text().splitlines()]
            payload[0]["reasons"] = []
            path.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in payload))
            self.assertTrue(m.validate_directory(output))

    def test_cli_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "public"
            command = [sys.executable, str(SCRIPT), "build", "--output", str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True, text=True).returncode, 0)
            first = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(subprocess.run(command, capture_output=True, text=True).returncode, 0)
            second = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(first, second)
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "validate", "--output", str(output)], capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
