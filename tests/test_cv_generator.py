"""Behavior tests for the procedural synthetic visual dataset."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "cv" / "generate_dataset.py"


def api():
    spec = importlib.util.spec_from_file_location("cv_generator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyntheticVisualDatasetTests(unittest.TestCase):
    def test_build_creates_deterministic_labeled_dataset_with_sequence_safe_split(self):
        generator = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            result = generator.build(output, seed=7, sequences_per_class=3, views_per_sequence=2, image_size=96)

            self.assertEqual(result["image_count"], 30)
            self.assertEqual(result["sequence_count"], 15)
            self.assertEqual(set(result["class_counts"]), set(generator.LABELS))

            manifest = [json.loads(line) for line in (output / "manifest.jsonl").read_text().splitlines()]
            self.assertEqual(len(manifest), 30)
            self.assertEqual({row["data_origin"] for row in manifest}, {"synthetic_demo"})
            self.assertEqual(
                {row["scientific_validation_status"] for row in manifest},
                {"not_validated_for_production"},
            )
            self.assertTrue(all((output / row["image_path"]).is_file() for row in manifest))

            sequence_splits = {}
            for row in manifest:
                sequence_splits.setdefault(row["sample_sequence_id"], row["split"])
                self.assertEqual(sequence_splits[row["sample_sequence_id"]], row["split"])

            self.assertEqual(generator.validate_directory(output), [])

            first_manifest = (output / "manifest.jsonl").read_bytes()
            generator.build(output, seed=7, sequences_per_class=3, views_per_sequence=2, image_size=96)
            self.assertEqual((output / "manifest.jsonl").read_bytes(), first_manifest)

    def test_validate_detects_missing_image(self):
        generator = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            generator.build(output, seed=11, sequences_per_class=2, views_per_sequence=1, image_size=64)
            manifest = [json.loads(line) for line in (output / "manifest.jsonl").read_text().splitlines()]
            (output / manifest[0]["image_path"]).unlink()
            self.assertTrue(generator.validate_directory(output))

    def test_cv_requirements_declare_pillow(self):
        requirements = ROOT / "requirements" / "cv.txt"
        self.assertTrue(requirements.is_file())
        declared = requirements.read_text(encoding="utf-8").splitlines()
        self.assertIn("Pillow>=10,<12", declared)

    def test_render_uses_studio_vial_scene_metadata(self):
        generator = api()
        image, capture = generator.render_image("phase_separation", __import__("random").Random(4), 128)
        self.assertEqual(image.size, (128, 128))
        self.assertEqual(capture["scene"], "studio_vial")
        self.assertEqual(capture["render_quality"], "supersampled_procedural")

    def test_split_is_stratified_by_visual_label(self):
        generator = api()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            generator.build(output, seed=13, sequences_per_class=10, views_per_sequence=1, image_size=64)
            manifest = [json.loads(line) for line in (output / "manifest.jsonl").read_text().splitlines()]
            for split in generator.SPLITS:
                with self.subTest(split=split):
                    labels = {row["label"] for row in manifest if row["split"] == split}
                    self.assertEqual(labels, set(generator.LABELS))


if __name__ == "__main__":
    unittest.main()
