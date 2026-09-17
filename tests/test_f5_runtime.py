"""Tests for finalizing F5 model extraction with UI-owned trial identity."""
import unittest
from scripts.f5_runtime import finalize_extraction

class F5RuntimeTests(unittest.TestCase):
    def test_selected_trial_id_overwrites_llm_hallucinated_id(self):
        model_output={"trial_id":"FULL-P-041-T3","proposed_checkpoint_patch":{"measurements":{"ph":5.4,"viscosity_cp":10000},"observations":{"appearance":"homogeneous"}},"field_confidence":{"ph":0.9,"viscosity_cp":0.9,"appearance":0.9},"requires_confirmation":False}
        actual=finalize_extraction("FULL-P-186-T1",model_output)
        self.assertEqual(actual["trial_id"],"FULL-P-186-T1")
        self.assertTrue(actual["requires_confirmation"])
        self.assertEqual(actual["proposed_checkpoint_patch"],model_output["proposed_checkpoint_patch"])
    def test_rejects_missing_patch(self):
        with self.assertRaises(ValueError): finalize_extraction("T-1",{})
if __name__=='__main__': unittest.main()
