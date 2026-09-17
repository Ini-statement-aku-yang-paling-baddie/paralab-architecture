"""Contract checks for the Kaggle training notebook."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "cv" / "notebooks" / "train_visual_screening.ipynb"


class KaggleTrainingNotebookTests(unittest.TestCase):
    def test_notebook_has_reproducible_manifest_first_training_pipeline(self):
        payload = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        self.assertEqual(payload["nbformat"], 4)
        source = "\n".join("".join(cell.get("source", [])) for cell in payload["cells"])
        for required_fragment in (
            "validate_manifest",
            "sample_sequence_id",
            "TinyVialCNN",
            "CrossEntropyLoss",
            "confusion_matrix",
            "synthetic_demo",
            "not_validated_for_production",
            "model_state_dict",
            "synthetic_v3",
            'LABELS = ("stable_uniform", "creaming", "phase_separation", "heterogeneous")',
        ):
            with self.subTest(required_fragment=required_fragment):
                self.assertIn(required_fragment, source)


if __name__ == "__main__":
    unittest.main()
