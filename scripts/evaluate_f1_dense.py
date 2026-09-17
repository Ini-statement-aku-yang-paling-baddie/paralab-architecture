#!/usr/bin/env python3
"""Evaluasi dense retrieval F1 pada kandidat blind yang sudah diberi label mesin."""
import argparse
import hashlib
import json
import math
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = ROOT / "data" / "labeling" / "rag_blind_v1" / "rag_blind_labels_machine_adjudicated.jsonl"
DEFAULT_TEXT = ROOT / "data" / "evidence_rag_text.jsonl"
DEFAULT_EMBEDDINGS = ROOT / "sentence-transformer" / "embeddings_formulab.npy"
DEFAULT_MODEL_ARCHIVE = ROOT / "sentence-transformer" / "embedding_model.zip"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "f1_dense_pool_v1.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def load_label_groups(path):
    groups = defaultdict(list)
    for row in load_jsonl(path):
        groups[row["query_id"]].append(row)
    return {query_id: sorted(rows, key=lambda row: row["candidate_rank"]) for query_id, rows in sorted(groups.items())}


def metrics_at_k(ranked, k):
    top = ranked[:k]
    total_relevant = sum(row["relevance"] > 0 for row in ranked)
    retrieved_relevant = sum(row["relevance"] > 0 for row in top)
    first_rank = next((index for index, row in enumerate(top, 1) if row["relevance"] > 0), None)
    dcg = sum((2 ** row["relevance"] - 1) / math.log2(index + 1) for index, row in enumerate(top, 1))
    ideal = sorted(ranked, key=lambda row: row["relevance"], reverse=True)[:k]
    idcg = sum((2 ** row["relevance"] - 1) / math.log2(index + 1) for index, row in enumerate(ideal, 1))
    return {
        "k": k,
        "judged_candidate_count": len(ranked),
        "relevant_candidate_count": total_relevant,
        "recall_at_k": retrieved_relevant / total_relevant if total_relevant else None,
        "mrr_at_k": 1 / first_rank if first_rank else 0.0,
        "ndcg_at_k": dcg / idcg if idcg else None,
    }


def load_model(archive):
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise RuntimeError("sentence-transformers belum tersedia di environment aktif.") from exc
    with tempfile.TemporaryDirectory(prefix="formulab-st-") as temp_dir:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(temp_dir)
        model = SentenceTransformer(temp_dir)
        yield model


def evaluate(labels_path=DEFAULT_LABELS, text_path=DEFAULT_TEXT, embeddings_path=DEFAULT_EMBEDDINGS,
             model_archive=DEFAULT_MODEL_ARCHIVE):
    import numpy as np

    labels = load_label_groups(labels_path)
    texts = load_jsonl(text_path)
    source_to_index = {row["source_id"]: index for index, row in enumerate(texts)}
    if len(source_to_index) != len(texts):
        raise ValueError("source_id evidence_rag_text tidak unik")
    embeddings = np.load(embeddings_path)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(texts):
        raise ValueError("dimensi embeddings tidak cocok dengan evidence_rag_text")
    if any(row["source_id"] not in source_to_index for rows in labels.values() for row in rows):
        raise ValueError("label memuat source_id yang tidak tersedia pada embeddings")

    from contextlib import contextmanager
    @contextmanager
    def model_context():
        generator = load_model(model_archive)
        try:
            yield next(generator)
        finally:
            try:
                next(generator)
            except StopIteration:
                pass

    result_queries = []
    with model_context() as model:
        for query_id, rows in labels.items():
            query_vector = np.asarray(model.encode([rows[0]["query"]], normalize_embeddings=True)[0], dtype="float32")
            ranked = []
            for row in rows:
                candidate = dict(row)
                candidate["score"] = float(embeddings[source_to_index[row["source_id"]]] @ query_vector)
                ranked.append(candidate)
            ranked.sort(key=lambda row: (-row["score"], row["source_id"]))
            result_queries.append({
                "query_id": query_id,
                "query": rows[0]["query"],
                "metrics": {f"at_{k}": metrics_at_k(ranked, k) for k in (1, 3, 5)},
                "top_5": [{"source_id": row["source_id"], "score": row["score"], "relevance": row["relevance"]} for row in ranked[:5]],
            })

    def mean(name):
        values = [item["metrics"]["at_5"][name] for item in result_queries]
        return sum(values) / len(values)

    return {
        "evaluation_id": "f1-dense-pool-v1",
        "retriever": "SentenceTransformer paraphrase-multilingual-MiniLM-L12-v2",
        "evaluation_scope": "reranking dense pada 30 kandidat machine-adjudicated per blind query; bukan metrik open-corpus retrieval",
        "data_origin": "synthetic_demo",
        "scientific_validation_status": "not_validated_for_production",
        "inputs": {
            "labels_sha256": sha256(labels_path), "evidence_text_sha256": sha256(text_path),
            "embeddings_sha256": sha256(embeddings_path), "model_archive_sha256": sha256(model_archive),
        },
        "aggregate_at_5": {"mean_recall_at_5": mean("recall_at_k"), "mean_mrr_at_5": mean("mrr_at_k"), "mean_ndcg_at_5": mean("ndcg_at_k")},
        "queries": result_queries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--text", type=Path, default=DEFAULT_TEXT)
    parser.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS)
    parser.add_argument("--model-archive", type=Path, default=DEFAULT_MODEL_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = evaluate(args.labels, args.text, args.embeddings, args.model_archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "aggregate_at_5": report["aggregate_at_5"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
