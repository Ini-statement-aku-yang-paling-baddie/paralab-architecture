"""Kontrak baseline dense retrieval F1 tanpa fallback BM25."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_f1_dense.py"


def api():
    spec = importlib.util.spec_from_file_location("evaluate_f1_dense", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DenseEvaluationTests(unittest.TestCase):
    def test_metrics_are_computed_only_over_judged_pool(self):
        m = api()
        ranked = [
            {"source_id": "A", "relevance": 0, "score": 0.9},
            {"source_id": "B", "relevance": 2, "score": 0.8},
            {"source_id": "C", "relevance": 1, "score": 0.7},
        ]
        metrics = m.metrics_at_k(ranked, 3)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["mrr_at_k"], 0.5)
        self.assertGreater(metrics["ndcg_at_k"], 0.0)
        self.assertEqual(metrics["judged_candidate_count"], 3)

    def test_machine_labels_have_exactly_30_candidates_per_blind_query(self):
        m = api()
        groups = m.load_label_groups(ROOT / "data" / "labeling" / "rag_blind_v1" / "rag_blind_labels_machine_adjudicated.jsonl")
        self.assertEqual(len(groups), 10)
        self.assertTrue(all(len(rows) == 30 for rows in groups.values()))

    def test_implementation_does_not_offer_bm25_fallback(self):
        self.assertNotIn("bm25", SCRIPT.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
