"""Behavior contract for F4 risk-aware next validation step."""
import unittest

from modules.f4_next_validation import recommend_next_validation


class F4NextValidationTests(unittest.TestCase):
    def test_missing_baseline_abstention_requests_only_missing_measurements(self):
        result = recommend_next_validation(
            {"decision": "abstain_human_review_required", "reason": "Checkpoint baseline minggu 0 atau checkpoint landmark belum lengkap."},
            {"measurements": {"ph": None, "viscosity_cp": 12000}, "appearance": "uniform"},
        )
        self.assertEqual(result["recommendation_type"], "next_validation_step")
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["required_inputs"], ["ph"])
        self.assertIn("missing_baseline_or_checkpoint", result["reason_codes"])
        self.assertTrue(result["requires_human_review"])

    def test_electrolyte_thickener_risk_prioritizes_viscosity_and_appearance(self):
        result = recommend_next_validation({
            "decision": "continue_observation",
            "data_origin": "synthetic_demo",
            "f2_screening": {"derived_features": {"electrolyte_thickener_risk": "high"}},
            "evidence_ids": ["J-2025-044-T02"],
        })
        self.assertEqual(result["priority"], "high")
        self.assertEqual(result["required_inputs"], ["viscosity_cp", "appearance"])
        self.assertIn("f2_electrolyte_thickener_risk_high", result["reason_codes"])
        self.assertEqual(result["evidence_ids"], ["J-2025-044-T02"])

    def test_high_risk_escalates_review_without_recommending_formula_change(self):
        result = recommend_next_validation({
            "decision": "flag_high_risk",
            "risk_band": "high",
            "confidence": "high",
            "data_origin": "synthetic_demo",
            "f2_screening": {"derived_features": {}},
        })
        self.assertEqual(result["priority"], "high")
        self.assertIn("f3_high_risk", result["reason_codes"])
        self.assertIn("formulator", result["recommended_action"].lower())
        self.assertNotRegex(result["recommended_action"].lower(), r"konsentrasi|naikkan|turunkan|resep")

    def test_low_confidence_requests_an_additional_confirmed_checkpoint(self):
        result = recommend_next_validation({
            "decision": "continue_observation",
            "confidence": "low",
            "data_origin": "synthetic_demo",
            "f2_screening": {"derived_features": {}},
        })
        self.assertEqual(result["priority"], "medium")
        self.assertIn("f3_low_confidence", result["reason_codes"])
        self.assertEqual(result["required_inputs"], ["ph", "viscosity_cp", "appearance"])


if __name__ == "__main__":
    unittest.main()
