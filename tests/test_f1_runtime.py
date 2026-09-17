"""Tests for F1 retrieval-to-summary runtime guardrails."""
import unittest
from scripts.f1_runtime import prepare_summary_request, finalize_summary


class F1RuntimeTests(unittest.TestCase):
    def test_context_contains_sanitized_evidence_without_recipe_or_measurements(self):
        retrieval = {
            "evidence_status": "sufficient",
            "related_cases": [{
                "source_id": "A", "outcome": "failed", "failure_mode": "x",
                "journal_title": "Gel cream", "narrative_excerpt": "pH 5.5; pemisahan pada minggu ke-12",
                "lesson_learned": "Rasio minyak 10% perlu ditinjau", "target_spec": "secret recipe 5%",
                "text": "raw retrieval text with full recipe 5%",
            }],
        }
        out = prepare_summary_request("why?", retrieval)
        card = out["related_cases"][0]
        self.assertEqual(card["source_id"], "A")
        self.assertEqual(card["outcome"], "failed")
        self.assertNotIn("text", card)
        self.assertNotIn("target_spec", card)
        self.assertNotRegex(card["narrative_excerpt"], r"5\.5|12")
        self.assertNotRegex(card["lesson_learned"], r"10%")

    def test_insufficient_retrieval_never_calls_summary(self):
        self.assertIsNone(prepare_summary_request("q", {"evidence_status": "insufficient", "related_cases": []}))

    def test_finalizer_overwrites_limitations_and_rejects_measurements(self):
        out = finalize_summary({"summary": "Kasus gagal karena pemisahan fase.", "limitations": "x"})
        self.assertIn("sintetis", out["limitations"].lower())
        with self.assertRaises(ValueError):
            finalize_summary({"summary": "pH 5.5 berubah", "limitations": "x"})


if __name__ == "__main__":
    unittest.main()
