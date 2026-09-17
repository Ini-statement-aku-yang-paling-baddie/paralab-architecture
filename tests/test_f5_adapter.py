"""Acceptance tests for canonical F5 source -> V4 extraction contract."""
import unittest

from scripts.f5_adapter import adapt_f5_example, trial_id_from_checkpoint


class F5AdapterTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "checkpoint_id": "FULL-P-001-T1-SERIES-W00",
            "trial_id": "FULL-P-001-T1",
            "requires_confirmation": True,
            "target": {
                "appearance": "uniform",
                "measurements": {"ph": 5.57, "viscosity_cp": 15708},
                "quality": {"ph": "observed", "viscosity_cp": "observed"},
            },
        }

    def test_derives_trial_id_from_checkpoint(self):
        self.assertEqual(trial_id_from_checkpoint("FULL-P-001-T1-SERIES-W06"), "FULL-P-001-T1")

    def test_adapts_observed_fields_without_changing_measurements(self):
        result = adapt_f5_example(self.row)
        self.assertEqual(result["trial_id"], "FULL-P-001-T1")
        self.assertEqual(
            result["proposed_checkpoint_patch"],
            {
                "measurements": {"ph": 5.57, "viscosity_cp": 15708},
                "observations": {"appearance": "uniform"},
            },
        )
        self.assertEqual(result["field_confidence"], {"ph": 0.95, "viscosity_cp": 0.95, "appearance": 0.9})
        self.assertIs(result["requires_confirmation"], True)

    def test_keeps_uncertain_number_but_lowers_confidence(self):
        row = {
            **self.row,
            "target": {
                **self.row["target"],
                "quality": {"ph": "uncertain", "viscosity_cp": "observed"},
            },
        }
        result = adapt_f5_example(row)
        self.assertEqual(result["proposed_checkpoint_patch"]["measurements"]["ph"], 5.57)
        self.assertEqual(result["field_confidence"]["ph"], 0.65)

    def test_omits_missing_field_and_sets_null_confidence(self):
        row = {
            **self.row,
            "target": {
                **self.row["target"],
                "measurements": {"ph": None, "viscosity_cp": 15708},
                "quality": {"ph": "missing", "viscosity_cp": "observed"},
            },
        }
        result = adapt_f5_example(row)
        self.assertNotIn("ph", result["proposed_checkpoint_patch"]["measurements"])
        self.assertIsNone(result["field_confidence"]["ph"])

    def test_rejects_confirmation_false(self):
        row = {**self.row, "requires_confirmation": False}
        with self.assertRaisesRegex(ValueError, "requires_confirmation"):
            adapt_f5_example(row)


if __name__ == "__main__":
    unittest.main()
