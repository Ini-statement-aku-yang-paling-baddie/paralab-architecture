"""Kontrak queue label provisional untuk blind F1 retrieval."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_rag_label_pilot.py"
QUERIES = ROOT / "data" / "rag_blind_test_queries.jsonl"
CORPUS = ROOT / "data" / "evidence_corpus.jsonl"


def api():
    spec = importlib.util.spec_from_file_location("rag_label_pilot", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RagLabelPilotTests(unittest.TestCase):
    def test_builds_300_provisional_labels_without_claiming_human_review(self):
        self.assertTrue(SCRIPT.exists(), "Builder queue label F1 belum tersedia")
        m = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "labels"
            result = m.build(output)
            self.assertEqual(result["validation_errors"], [])
            labels = [json.loads(line) for line in (output / "rag_blind_label_candidates.jsonl").read_text().splitlines()]
            manifest = json.loads((output / "labeling_manifest.json").read_text())
            source_ids = {json.loads(line)["source_id"] for line in CORPUS.read_text().splitlines()}
            self.assertEqual(len(labels), 300)
            self.assertEqual({x["query_id"] for x in labels}, {f"QB-{i:03d}" for i in range(1, 11)})
            self.assertTrue(all(x["source_id"] in source_ids for x in labels))
            self.assertTrue(all(x["relevance"] in {0, 1, 2} for x in labels))
            self.assertTrue(all(x["label_source"] == "ai_assisted_provisional" for x in labels))
            self.assertTrue(all(x["review_status"] == "needs_human_review" for x in labels))
            self.assertTrue(all(x["rationale"] for x in labels))
            self.assertEqual(manifest["human_approved_count"], 0)
            self.assertEqual(manifest["review_queue_count"], 300)
            by_query = {}
            for label in labels:
                by_query.setdefault(label["query_id"], set()).add(label["relevance"])
            self.assertTrue(all(0 in levels for query_id, levels in by_query.items() if query_id not in {"QB-004", "QB-009"}))
            self.assertEqual(m.validate_directory(output), [])

    def test_machine_adjudicated_labels_preserve_gaps_and_never_claim_human_review(self):
        m = api()
        rows = m.build_machine_adjudicated_rows()
        self.assertEqual(len(rows), 300)
        self.assertTrue(all(row["label_source"] == "synthetic_metadata_and_llm_audit" for row in rows))
        self.assertTrue(all(row["review_status"] == "machine_adjudicated_not_human" for row in rows))
        self.assertTrue(all(row["relevance"] <= 1 for row in rows if row["query_id"] == "QB-009"))
        self.assertTrue(all(row["relevance"] == 1 for row in rows if row["query_id"] == "QB-004"))

    def test_machine_output_does_not_invalidate_provisional_queue_manifest(self):
        m = api()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "queue"
            self.assertEqual(m.build(output)["validation_errors"], [])
            m.write_machine_adjudicated_rows(output / "rag_blind_labels_machine_adjudicated.jsonl")
            self.assertEqual(m.validate_directory(output), [])

    def test_reviewer_templates_are_blank_and_traceable(self):
        m = api()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "review_templates"
            result = m.export_reviewer_templates(output)
            self.assertEqual(result["review_rows_per_reviewer"], 300)
            for reviewer in ("reviewer_a.csv", "reviewer_b.csv"):
                with (output / reviewer).open(encoding="utf-8") as handle:
                    rows = list(__import__("csv").DictReader(handle))
                self.assertEqual(len(rows), 300)
                self.assertTrue(all(row["human_relevance"] == "" for row in rows))
                self.assertTrue(all(row["source_id"] for row in rows))
            with (output / "adjudication.csv").open(encoding="utf-8") as handle:
                adjudication = list(__import__("csv").DictReader(handle))
            self.assertEqual(len(adjudication), 300)
            self.assertTrue(all(row["final_relevance"] == "" for row in adjudication))

    def test_qb009_is_explicitly_a_coverage_gap_not_false_male_evidence(self):
        m = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "labels"
            m.build(output)
            labels = [json.loads(line) for line in (output / "rag_blind_label_candidates.jsonl").read_text().splitlines()]
            qb009 = [x for x in labels if x["query_id"] == "QB-009"]
            self.assertTrue(qb009)
            self.assertTrue(all(x["coverage_gap"] == "gender_not_recorded_in_synthetic_corpus" for x in qb009))
            self.assertTrue(all(x["relevance"] <= 1 for x in qb009))


if __name__ == "__main__":
    unittest.main()
