"""HTTP contract for the local ParaLab F1/F2/F4/F5 gateway."""
from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeF1Service:
    def query(self, query: str, top_k: int = 5) -> dict:
        return {
            "query": query,
            "evidence_status": "sufficient",
            "evidence": [
                {
                    "source_id": "E-001",
                    "hybrid_score": 0.9,
                    "outcome": "continue_observation",
                    "failure_mode": "none",
                    "journal_title": "Synthetic example",
                }
            ],
            "answer": {
                "summary": "Ringkasan evidence yang aman.",
                "limitations": "Evidence ini berasal dari data sintetis dan memerlukan validasi R&D manusia.",
            },
            "requires_human_review": True,
            "limitations": ["Synthetic demo."],
        }


class ModelGatewayContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from api.model_gateway import create_app

        cls.client = TestClient(create_app(f1_service=FakeF1Service()))

    def test_f1_query_returns_evidence_and_reviewable_answer(self):
        response = self.client.post("/v1/f1/query", json={"query": "Apa risiko pemisahan fase?"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["evidence_status"], "sufficient")
        self.assertEqual(body["evidence"][0]["source_id"], "E-001")
        self.assertTrue(body["requires_human_review"])
        self.assertIn("summary", body["answer"])

    def test_f2_health_check_runs_server_side_screening(self):
        response = self.client.post(
            "/v1/f2/health-check",
            json={
                "formula": [{"bahan": "Xanthan Gum", "pct": 0.5}],
                "context": {"target_skin": "oily"},
                "ph": 5.5,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["overall_status"], "clear_for_current_screening")

    def test_f4_returns_a_reviewable_next_step(self):
        response = self.client.post(
            "/v1/f4/next-validation",
            json={
                "f3_forecast": {
                    "decision": "flag_high_risk",
                    "risk_band": "high",
                    "confidence": "high",
                    "data_origin": "synthetic_demo",
                    "f2_screening": {"derived_features": {}},
                },
                "checkpoint": None,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["requires_human_review"])

    def test_f5_makes_a_confirmation_required_draft_from_browser_transcript(self):
        response = self.client.post(
            "/v1/f5/transcribe-draft",
            json={
                "selected_trial_id": "TRIAL-01",
                "transcript": "pH lima koma lima, viskositas 12000 cP, sampel homogen",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["trial_id"], "TRIAL-01")
        self.assertEqual(body["proposed_checkpoint_patch"]["measurements"]["ph"], 5.5)
        self.assertEqual(body["proposed_checkpoint_patch"]["measurements"]["viscosity_cp"], 12000.0)
        self.assertEqual(body["proposed_checkpoint_patch"]["observations"]["appearance"], "uniform")
        self.assertTrue(body["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
