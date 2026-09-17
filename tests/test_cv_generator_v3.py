"""Contract checks for the more diverse procedural CV v3 dataset."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "cv" / "generate_dataset_v3.py"


def api():
    spec = importlib.util.spec_from_file_location("cv_generator_v3", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyntheticVisualDatasetV3Tests(unittest.TestCase):
    def test_build_has_stratified_classes_and_visual_nuisance_metadata(self):
        generator = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            result = generator.build(output, seed=29, sequences_per_class=5, views_per_sequence=2, image_size=96)
            self.assertEqual(result["dataset_version"], "procedural-cv-v3")
            self.assertEqual(result["image_count"], 40)

            rows = [json.loads(line) for line in (output / "manifest.jsonl").read_text().splitlines()]
            self.assertEqual({row["label"] for row in rows}, set(generator.LABELS))
            for split in generator.SPLITS:
                self.assertEqual({row["label"] for row in rows if row["split"] == split}, set(generator.LABELS))
            self.assertTrue(all({"vessel_type", "camera_profile", "liquid_palette", "condition_parameters"} <= set(row) for row in rows))
            self.assertEqual(generator.validate_directory(output), [])


if __name__ == "__main__":
    unittest.main()
