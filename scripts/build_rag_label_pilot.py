#!/usr/bin/env python3
"""Bangun queue label provisional untuk evaluasi blind retrieval F1."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "data" / "rag_blind_test_queries.jsonl"
CORPUS = ROOT / "data" / "evidence_corpus.jsonl"
POOL_SIZE = 30


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def dump(path, payload, lines=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in payload) if lines else json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def evidence_text(row):
    return " ".join(str(row.get(key, "")) for key in ["journal_title", "target_spec", "narrative_excerpt", "lesson_learned", "domain_note"]).lower()


def provisional_relevance(query_id, row):
    scenario = row["normalized_context"]["scenario_family"]
    outcome = row["outcome"]
    failure = row["failure_mode"]
    ingredients = set(row["ingredient_ids"])
    text = evidence_text(row)
    coverage_gap = None
    if query_id == "QB-001":
        if scenario == "early_viscosity_drop": return 2, "Skenario penurunan viskositas awal cocok langsung.", coverage_gap
        if failure == "viscosity_collapse": return 1, "Memiliki kegagalan viskositas, tetapi bukan pola awal yang eksplisit.", coverage_gap
    elif query_id == "QB-002":
        if failure == "phase_separation": return 2, "Outcome mencatat phase separation.", coverage_gap
        if scenario == "process_parameter_failure": return 1, "Kegagalan proses dapat menjadi konteks pemisahan emulsi, perlu review.", coverage_gap
    elif query_id == "QB-003":
        if {"ING:NIACINAMIDE", "ING:ZINC_PCA"} <= ingredients: return 2, "Mengandung Niacinamide dan Zinc PCA untuk konteks kulit berminyak.", coverage_gap
        if "ING:NIACINAMIDE" in ingredients: return 1, "Mengandung Niacinamide tetapi tidak kedua bahan yang ditanyakan.", coverage_gap
    elif query_id == "QB-004":
        if "non-lengket" in text or "ringan" in text:
            return 1, "Target tekstur ringan/non-lengket relevan sebagai konteks parsial, tetapi bukan observasi keluhan lengket.", "no_observed_tackiness_or_daytime_comfort_field"
    elif query_id == "QB-005":
        if "premium" in text and outcome == "pass": return 2, "Segmen premium dengan outcome pass.", coverage_gap
        if "premium" in text: return 1, "Segmen premium, tetapi outcome bukan pass.", coverage_gap
    elif query_id == "QB-006":
        if scenario == "ph_drift": return 2, "Skenario pH drift cocok langsung.", coverage_gap
    elif query_id == "QB-007":
        if "ING:CARBOMER" in ingredients and scenario == "electrolyte_thickener_failure": return 2, "Carbomer dengan skenario electrolyte-thickener failure.", coverage_gap
        if "ING:CARBOMER" in ingredients: return 1, "Mengandung Carbomer, tetapi hubungan elektrolit perlu review.", coverage_gap
    elif query_id == "QB-008":
        if "ING:FRAGRANCE" not in ingredients and ({"ING:PANTHENOL", "ING:ALLANTOIN"} & ingredients): return 2, "Tanpa fragrance dan memiliki bahan soothing sebagai proxy sensitivitas.", coverage_gap
        if "ING:FRAGRANCE" not in ingredients: return 1, "Tanpa fragrance, tetapi klaim kulit sensitif tidak direkam eksplisit.", coverage_gap
    elif query_id == "QB-009":
        coverage_gap = "gender_not_recorded_in_synthetic_corpus"
        if row["normalized_context"]["target_problem"] == "oil_control": return 1, "Cocok untuk oil control, tetapi corpus tidak merekam gender/pria.", coverage_gap
    elif query_id == "QB-010":
        if scenario == "process_parameter_failure": return 2, "Skenario kegagalan parameter proses cocok langsung.", coverage_gap
        if failure == "emulsion_instability": return 1, "Instabilitas emulsi dapat menjadi kandidat inspeksi proses, perlu review.", coverage_gap
    return 0, "Tidak ada kecocokan terstruktur yang cukup untuk query ini.", coverage_gap


def build_rows():
    queries = load_jsonl(QUERIES)
    corpus = load_jsonl(CORPUS)
    rows = []
    for query in queries:
        candidates = []
        for document in corpus:
            relevance, rationale, coverage_gap = provisional_relevance(query["query_id"], document)
            candidates.append({"query_id": query["query_id"], "query": query["query"], "source_id": document["source_id"],
                "relevance": relevance, "rationale": rationale, "label_source": "ai_assisted_provisional",
                "review_status": "needs_human_review", "coverage_gap": coverage_gap,
                "evidence_snapshot": {"scenario_family": document["normalized_context"]["scenario_family"], "outcome": document["outcome"],
                                      "failure_mode": document["failure_mode"], "ingredient_ids": document["ingredient_ids"]}})
        candidates.sort(key=lambda x: (-x["relevance"], x["source_id"]))
        if query["query_id"] == "QB-009":
            selected = candidates[:POOL_SIZE]
        else:
            high = [x for x in candidates if x["relevance"] == 2][:15]
            medium = [x for x in candidates if x["relevance"] == 1][:10]
            zero = [x for x in candidates if x["relevance"] == 0]
            selected = high + medium
            selected += zero[:POOL_SIZE - len(selected)]
            if len(selected) < POOL_SIZE:
                selected += [x for x in candidates if x not in selected][:POOL_SIZE - len(selected)]
        for rank, candidate in enumerate(selected, 1):
            candidate["candidate_rank"] = rank
            rows.append(candidate)
    return rows


def build_machine_adjudicated_rows():
    """Produce a reproducible benchmark reference for this synthetic corpus.

    The label is a corpus-internal reference, not a human or scientific ground truth.
    """
    adjudicated = []
    for row in build_rows():
        result = dict(row)
        result["label_source"] = "synthetic_metadata_and_llm_audit"
        result["review_status"] = "machine_adjudicated_not_human"
        result["adjudication_policy"] = "corpus_internal_relevance_v1"
        result["scientific_truth_status"] = "not_a_scientific_or_human_expert_label"
        if result["query_id"] == "QB-009":
            result["relevance"] = min(result["relevance"], 1)
            result["adjudication_note"] = "Gender pria tidak direkam, sehingga evidence oil-control hanya relevan parsial."
        elif result["query_id"] == "QB-004":
            result["relevance"] = min(result["relevance"], 1)
            result["adjudication_note"] = "Target non-lengket hanya context; tidak ada observasi keluhan lengket atau kenyamanan siang hari."
        else:
            result["adjudication_note"] = "Label diturunkan dari metadata dan isi evidence card synthetic, lalu diaudit model secara independen."
        adjudicated.append(result)
    return adjudicated


def write_machine_adjudicated_rows(output):
    output = Path(output)
    rows = build_machine_adjudicated_rows()
    dump(output, rows, lines=True)
    return {"machine_adjudicated_count": len(rows), "output": str(output)}


def manifest(rows):
    return {"version": "rag-label-pilot-v1", "query_source_sha256": sha(QUERIES), "corpus_source_sha256": sha(CORPUS),
            "query_count": 10, "pool_size_per_query": POOL_SIZE, "review_queue_count": len(rows), "human_approved_count": 0,
            "label_source": "ai_assisted_provisional", "review_status": "needs_human_review",
            "instructions": ["Reviewer mengubah relevance menjadi 0, 1, atau 2 berdasarkan query dan evidence snapshot.",
                             "Reviewer tidak boleh mengubah source_id atau menganggap data synthetic sebagai eksperimen nyata.",
                             "QB-009 harus mempertahankan coverage gap gender, karena corpus tidak memiliki metadata pria/gender.",
                             "Hanya setelah adjudication, export label final boleh dipakai untuk metrik blind F1."]}


def validate_directory(output):
    output = Path(output)
    errors = []
    try:
        rows = load_jsonl(output / "rag_blind_label_candidates.jsonl")
        expected = build_rows()
        source_ids = {row["source_id"] for row in load_jsonl(CORPUS)}
        if rows != expected: errors.append("queue label tidak dapat direplay dari sumber")
        if len(rows) != 300: errors.append("jumlah candidate bukan 300")
        if any(row["source_id"] not in source_ids for row in rows): errors.append("source_id tidak ada di corpus")
        if any(row["relevance"] not in {0, 1, 2} for row in rows): errors.append("relevance di luar skala")
        if any(row["label_source"] != "ai_assisted_provisional" or row["review_status"] != "needs_human_review" for row in rows): errors.append("status review tidak aman")
        if json.loads((output / "labeling_manifest.json").read_text()) != manifest(rows): errors.append("manifest labeling tidak cocok")
        stored = json.loads((output / "sha256_manifest.json").read_text())
        actual = {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name not in {"sha256_manifest.json", "rag_blind_labels_machine_adjudicated.jsonl"}}
        if stored != {"algorithm": "sha256", "files": actual}: errors.append("hash manifest tidak cocok")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"gagal validasi queue label: {exc}")
    return errors


def build(output):
    output = Path(output).resolve()
    rows = build_rows()
    dump(output / "rag_blind_label_candidates.jsonl", rows, lines=True)
    dump(output / "labeling_manifest.json", manifest(rows))
    files = {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name not in {"sha256_manifest.json", "rag_blind_labels_machine_adjudicated.jsonl"}}
    dump(output / "sha256_manifest.json", {"algorithm": "sha256", "files": files})
    errors = validate_directory(output)
    return {"review_queue_count": len(rows), "validation_errors": errors}


def export_reviewer_templates(output):
    """Export dua worksheet CSV kosong dan satu queue adjudication yang traceable."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    reviewer_fields = [
        "review_row_id", "query_id", "query", "candidate_rank", "source_id", "ai_provisional_relevance",
        "ai_rationale", "coverage_gap", "scenario_family", "outcome", "failure_mode", "ingredient_ids",
        "human_relevance", "review_decision", "reviewer_rationale", "reviewer_id", "reviewed_at",
    ]
    adjudication_fields = [
        "review_row_id", "query_id", "query", "source_id", "ai_provisional_relevance",
        "reviewer_a_relevance", "reviewer_b_relevance", "agreement", "final_relevance", "adjudicator_id",
        "adjudication_rationale", "adjudicated_at",
    ]

    def reviewer_row(row):
        snapshot = row["evidence_snapshot"]
        return {
            "review_row_id": f"{row['query_id']}::{row['source_id']}", "query_id": row["query_id"],
            "query": row["query"], "candidate_rank": row["candidate_rank"], "source_id": row["source_id"],
            "ai_provisional_relevance": row["relevance"], "ai_rationale": row["rationale"],
            "coverage_gap": row["coverage_gap"] or "", "scenario_family": snapshot["scenario_family"],
            "outcome": snapshot["outcome"], "failure_mode": snapshot["failure_mode"] or "",
            "ingredient_ids": "; ".join(snapshot["ingredient_ids"]), "human_relevance": "",
            "review_decision": "", "reviewer_rationale": "", "reviewer_id": "", "reviewed_at": "",
        }

    def write_csv(name, fields, export_rows):
        with (output / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(export_rows)

    reviewer_rows = [reviewer_row(row) for row in rows]
    write_csv("reviewer_a.csv", reviewer_fields, reviewer_rows)
    write_csv("reviewer_b.csv", reviewer_fields, reviewer_rows)
    write_csv("adjudication.csv", adjudication_fields, [{
        "review_row_id": item["review_row_id"], "query_id": item["query_id"], "query": item["query"],
        "source_id": item["source_id"], "ai_provisional_relevance": item["ai_provisional_relevance"],
        "reviewer_a_relevance": "", "reviewer_b_relevance": "", "agreement": "", "final_relevance": "",
        "adjudicator_id": "", "adjudication_rationale": "", "adjudicated_at": "",
    } for item in reviewer_rows])
    (output / "README.md").write_text(
        "# Template review blind F1\n\n"
        "Isi `human_relevance` dengan 0, 1, atau 2. Isi `review_decision` dengan `accept`, `modify`, atau `abstain`. "
        "Dua reviewer bekerja pada salinan terpisah. Jangan mengubah query, source_id, atau metadata snapshot. "
        "Setelah itu pindahkan hasil ke `adjudication.csv`; blind labels belum final tanpa adjudication.\n",
        encoding="utf-8",
    )
    return {"review_rows_per_reviewer": len(rows), "adjudication_rows": len(rows), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "validate", "export-review-templates", "build-machine-adjudicated"])
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "labeling" / "rag_blind_v1")
    parser.add_argument("--template-output", type=Path)
    parser.add_argument("--adjudicated-output", type=Path, default=ROOT / "data" / "labeling" / "rag_blind_v1" / "rag_blind_labels_machine_adjudicated.jsonl")
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.output)
    elif args.command == "validate":
        result = {"validation_errors": validate_directory(args.output)}
    elif args.command == "export-review-templates":
        template_output = args.template_output or args.output.parent / f"{args.output.name}_review_templates"
        result = export_reviewer_templates(template_output)
    else:
        result = write_machine_adjudicated_rows(args.adjudicated_output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return int(bool(result.get("validation_errors")))


if __name__ == "__main__":
    raise SystemExit(main())
