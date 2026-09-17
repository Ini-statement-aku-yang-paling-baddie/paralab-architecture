#!/usr/bin/env python
"""Build a 600-row F1 V4 dense-embedding artifact from a local MiniLM archive."""
import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEXT = ROOT / "data" / "evidence_rag_text.jsonl"
DEFAULT_ARCHIVE = ROOT.parent.parent / "embedding_model.zip"
DEFAULT_OUTPUT = ROOT / "data" / "f1_embeddings_v4.npy"
DEFAULT_MANIFEST = ROOT / "data" / "f1_embeddings_v4.manifest.json"
EXPECTED_DIMENSIONS = 384


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rag_rows(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("RAG text cannot be empty")
    if any(not isinstance(row.get("source_id"), str) or not row["source_id"] for row in rows):
        raise ValueError("every RAG row must have non-empty source_id")
    if any(not isinstance(row.get("text"), str) or not row["text"].strip() for row in rows):
        raise ValueError("every RAG row must have non-empty text")
    if len({row["source_id"] for row in rows}) != len(rows):
        raise ValueError("RAG source_id values must be unique")
    return rows


def validate_embedding_matrix(rows, embeddings):
    if not isinstance(embeddings, np.ndarray) or embeddings.ndim != 2:
        raise ValueError("embeddings must be a two-dimensional numpy array")
    if embeddings.shape[0] != len(rows):
        raise ValueError("embedding row count must match RAG row count")
    if embeddings.shape[1] != EXPECTED_DIMENSIONS:
        raise ValueError(f"expected {EXPECTED_DIMENSIONS} embedding dimensions")
    if embeddings.dtype != np.float32:
        raise ValueError("embeddings must be float32")
    if not np.isfinite(embeddings).all():
        raise ValueError("embeddings must be finite")


def build_embeddings(text_path, model_archive, output_path, manifest_path):
    text_path, model_archive = Path(text_path), Path(model_archive)
    output_path, manifest_path = Path(output_path), Path(manifest_path)
    rows = load_rag_rows(text_path)
    if not model_archive.is_file():
        raise FileNotFoundError(f"Missing local SentenceTransformer archive: {model_archive}")

    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install requirements-f1-dense.txt with Python 3.12 before building embeddings.") from exc

    with tempfile.TemporaryDirectory(prefix="formulab-minilm-") as temporary_dir:
        with zipfile.ZipFile(model_archive) as archive:
            archive.extractall(temporary_dir)
        model = SentenceTransformer(temporary_dir)
        embeddings = np.asarray(
            model.encode(
                [row["text"] for row in rows],
                normalize_embeddings=True,
                show_progress_bar=True,
            ),
            dtype=np.float32,
        )

    validate_embedding_matrix(rows, embeddings)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, embeddings)
    manifest = {
        "artifact": output_path.name,
        "rows": len(rows),
        "dimensions": int(embeddings.shape[1]),
        "dtype": str(embeddings.dtype),
        "normalized": True,
        "rag_text_sha256": sha256_file(text_path),
        "model_archive_sha256": sha256_file(model_archive),
        "embeddings_sha256": sha256_file(output_path),
        "source_ids_in_row_order": [row["source_id"] for row in rows],
        "data_origin": "synthetic_demo",
        "scientific_validation_status": "not_validated_for_production",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", type=Path, default=DEFAULT_TEXT)
    parser.add_argument("--model-archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    print(json.dumps(build_embeddings(args.text, args.model_archive, args.output, args.manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
