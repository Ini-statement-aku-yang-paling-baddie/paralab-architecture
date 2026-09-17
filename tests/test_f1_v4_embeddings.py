"""Tests for rebuilding F1 V4 dense embeddings from the local MiniLM archive."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_f1_v4_embeddings.py"


def api():
    spec = importlib.util.spec_from_file_location("build_f1_v4_embeddings", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class F1V4EmbeddingTests(unittest.TestCase):
    def test_load_rag_rows_rejects_duplicate_source_ids(self):
        module = api()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rag.jsonl"
            path.write_text(
                '{"source_id":"A","text":"one"}\n'
                '{"source_id":"A","text":"two"}\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                module.load_rag_rows(path)

    def test_validate_embedding_matrix_requires_row_alignment_and_384_dimensions(self):
        module = api()
        rows = [{"source_id": "A", "text": "one"}, {"source_id": "B", "text": "two"}]
        module.validate_embedding_matrix(rows, np.zeros((2, 384), dtype=np.float32))
        with self.assertRaises(ValueError):
            module.validate_embedding_matrix(rows, np.zeros((1, 384), dtype=np.float32))
        with self.assertRaises(ValueError):
            module.validate_embedding_matrix(rows, np.zeros((2, 128), dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
