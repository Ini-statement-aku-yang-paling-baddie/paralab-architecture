"""Kontrak ingest sumber terbuka; tidak menyentuh data sintetis."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/ingest_open_sources.py"


def api():
    spec = importlib.util.spec_from_file_location("open_sources", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenSourceIngestionTests(unittest.TestCase):
    def test_parse_preserves_source_values_and_declares_scope(self):
        self.assertTrue(SCRIPT.exists(), "CLI ingest belum tersedia")
        module = api()
        source = [{"Ingredient A": 1.25, "Stability_Test": False, "Turbidity_NTU": "NA", "ID": 7}]
        rows = module.normalize_records(source)
        self.assertEqual(rows[0]["source_values"], source[0])
        self.assertEqual(rows[0]["source_record_id"], 7)
        self.assertEqual(rows[0]["data_origin"], "observed_open_dataset")
        self.assertEqual(rows[0]["domain_scope"]["product_class"], "shampoo_rinse_off_liquid_formulations")
        self.assertEqual(rows[0]["domain_scope"]["observation_horizon"], "36_hours_after_final_ph_adjustment")
        self.assertFalse(rows[0]["eligible_for_synthetic_training_join"])

    def test_cached_build_is_deterministic_and_auditable(self):
        module = api()
        records = [
            {"Ingredient A": 1.25, "Stability_Test": False, "Turbidity_NTU": "NA", "ID": 7},
            {"Ingredient A": 0.0, "Stability_Test": True, "Turbidity_NTU": 4.5, "ID": 8},
        ]
        collection = {"id": 7132624, "doi": "10.6084/m9.figshare.c.7132624.v1", "title": "Collection"}
        article = {
            "id": 25451878,
            "doi": "10.6084/m9.figshare.25451878.v1",
            "title": "Liquid Formulations Dataset",
            "license": {"name": "CC0", "url": "https://creativecommons.org/publicdomain/zero/1.0/"},
            "citation": "Citation",
            "files": [{"id": 45187180, "name": "LiquidFormulationsDataset_2023.json", "size": 1,
                       "download_url": "https://ndownloader.figshare.com/files/45187180"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            module.cache_sources(output, json.dumps(collection).encode(), json.dumps(article).encode(),
                                 json.dumps(records).encode(), "2026-09-17T00:00:00Z")
            module.build_from_cache(output)
            before = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            module.build_from_cache(output)
            after = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(module.validate_directory(output), [])
            profile = json.loads((output / "schema_profile.json").read_text())
            audit = json.loads((output / "quality_audit.json").read_text())
            self.assertEqual(profile["record_count"], 2)
            self.assertEqual(profile["fields"]["Turbidity_NTU"]["missing_count"], 1)
            self.assertEqual(audit["unique_source_ids"], 2)
            normalized = [json.loads(line) for line in (output / "normalized/liquid_formulations.jsonl").read_text().splitlines()]
            self.assertEqual([row["source_values"] for row in normalized], records)
            (output / "raw/liquid_formulations_dataset_2023.json").write_text("[]")
            self.assertTrue(module.validate_directory(output))


if __name__ == "__main__":
    unittest.main()
