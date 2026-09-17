#!/usr/bin/env python3
"""Bangun evidence publik terverifikasi tanpa mencampurnya ke label F3."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "sources" / "public" / "PMC7407566_tables_2_5.json"
OUTPUT_FILES = ["source_index.json", "observed_formulations.jsonl", "f1_evidence_documents.jsonl", "f3_excluded_candidates.jsonl", "training_contract.json"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, payload, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if lines:
        text = "".join(json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n" for x in payload)
    else:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_source(source):
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    required = {"source_id", "title", "doi", "article_url", "license", "license_url", "accessed_at", "extraction_method", "source_table_ids", "domain", "domain_limitations", "not_a_lab_recipe", "measurements", "formulations"}
    require(required <= set(source), "metadata sumber wajib hilang")
    require(source.get("doi") == "10.3390/pharmaceutics12070647", "DOI sumber tidak cocok")
    require(source.get("license") == "CC-BY-4.0" and source.get("license_url") == "https://creativecommons.org/licenses/by/4.0/", "lisensi tidak eksplisit")
    require(source.get("not_a_lab_recipe") is True, "status recipe harus ditolak")
    require(source.get("extraction_method") == "manual_double_checked_html_table_transcription", "metode ekstraksi tidak diaudit")
    require(source.get("source_table_ids") == ["Table 2", "Table 5"], "rujukan tabel tidak tepat")
    measurements = source.get("measurements", {})
    require(set(measurements) == {"ph", "instability_index"}, "kontrak measurement tidak tepat")
    require(measurements.get("ph", {}).get("timepoint_days") == 1, "waktu pH tidak tepat")
    require(measurements.get("instability_index", {}).get("timepoint_days") == 4, "waktu instability tidak tepat")
    rows = source.get("formulations", [])
    require(len(rows) == 15, "jumlah formulasi bukan 15")
    seen = set()
    for row in rows:
        rid = row.get("paper_formula_id")
        require(isinstance(rid, str) and rid not in seen, f"ID formulasi duplikat/kosong: {rid}")
        seen.add(rid)
        require(row.get("data_origin") == "observed_public", f"{rid}: origin bukan observed_public")
        require(row.get("not_a_lab_recipe") is True, f"{rid}: status recipe")
        require(row.get("instability_compliance") in {"C", "NC"}, f"{rid}: compliance")
        for key in ["glycerol_monostearate_pct", "isopropyl_myristate_pct", "homogenization_rpm", "ph_mean", "ph_sd", "instability_index_mean", "instability_index_sd"]:
            require(finite(row.get(key)), f"{rid}: {key} bukan nilai finite")
        require(0 <= row.get("glycerol_monostearate_pct", -1) <= 100 and 0 <= row.get("isopropyl_myristate_pct", -1) <= 100, f"{rid}: konsentrasi")
        require(row.get("homogenization_rpm", 0) > 0 and 0 <= row.get("ph_mean", -1) <= 14 and 0 <= row.get("instability_index_mean", -1) <= 1, f"{rid}: range observasi")
    require(seen == {f"F{i}" for i in range(1, 16)}, "set ID formulasi tidak lengkap")
    return errors


def normalized_rows(source):
    source_hash = sha(SOURCE_PATH)
    common = {
        "data_origin": "observed_public",
        "human_verified": False,
        "scientific_validation_status": "reported_in_open_access_paper_not_independently_reproduced",
        "provenance": {
            "source_id": source["source_id"], "doi": source["doi"], "license": source["license"],
            "article_url": source["article_url"], "accessed_at": source["accessed_at"], "source_sha256": source_hash,
            "extraction_method": source["extraction_method"], "source_tables": source["source_table_ids"]
        },
        "domain": source["domain"], "domain_limitations": source["domain_limitations"],
        "not_a_lab_recipe": True,
        "training_eligibility": {
            "f1": "eligible_as_cited_evidence", "f2": "eligible_as_context_not_rule", "f3": "excluded",
            "reason": "cross_sectional_proxy_domain_without_week4_landmark_or_week12_outcome"
        }
    }
    rows = []
    for raw in source["formulations"]:
        rows.append({
            "id": f"{source['source_id']}-{raw['paper_formula_id']}", "paper_formula_id": raw["paper_formula_id"], **common,
            "partial_formula_variables": {
                "glycerol_monostearate_pct": raw["glycerol_monostearate_pct"],
                "isopropyl_myristate_pct": raw["isopropyl_myristate_pct"]
            },
            "process": {"homogenization_rpm": raw["homogenization_rpm"]},
            "observations": [
                {"metric": "ph", "mean": raw["ph_mean"], "sd": raw["ph_sd"], "unit": "pH", **source["measurements"]["ph"]},
                {"metric": "instability_index", "mean": raw["instability_index_mean"], "sd": raw["instability_index_sd"], "unit": "dimensionless", "reported_compliance": raw["instability_compliance"], **source["measurements"]["instability_index"]}
            ]
        })
    return rows


def derive(rows):
    evidence, excluded = [], []
    for row in rows:
        p = row["partial_formula_variables"]
        process = row["process"]
        obs = {x["metric"]: x for x in row["observations"]}
        evidence.append({
            "id": f"EVID-{row['id']}", "data_origin": "observed_public", "source_id": row["provenance"]["source_id"],
            "doi": row["provenance"]["doi"], "license": row["provenance"]["license"], "source_tables": row["provenance"]["source_tables"],
            "document_scope": "open_access_observed_proxy_evidence", "related_observation_id": row["id"],
            "text": (f"Evidence publik {row['paper_formula_id']} dari cream O/W hidrokortison. "
                     f"Variabel DoE yang dilaporkan: glycerol monostearate {p['glycerol_monostearate_pct']}%, "
                     f"isopropyl myristate {p['isopropyl_myristate_pct']}%, homogenisasi {process['homogenization_rpm']} rpm. "
                     f"pH hari {obs['ph']['timepoint_days']}: {obs['ph']['mean']} ± {obs['ph']['sd']}. "
                     f"Instability index hari {obs['instability_index']['timepoint_days']}: {obs['instability_index']['mean']} ± {obs['instability_index']['sd']} "
                     f"(laporan tabel: {obs['instability_index']['reported_compliance']}). "
                     "Proxy farmasi, bukan resep dan bukan bukti langsung untuk moisturizer kosmetik.")
        })
        excluded.append({
            "id": f"EXCL-F3-{row['id']}", "observation_id": row["id"], "data_origin": "observed_public",
            "reasons": ["not_longitudinal_to_landmark_week_4", "no_week12_outcome", "proxy_domain_not_cosmetic_moisturizer", "partial_formula_only"],
            "permitted_uses": ["f1_cited_evidence", "f2_context", "external_distribution_sanity_check"],
            "forbidden_uses": ["f3_supervised_feature", "f3_binary_label", "formula_recipe"]
        })
    return evidence, excluded


def contract(source_hash):
    return {
        "contract_version": "public-evidence-v1", "source_sha256": source_hash,
        "seamless_integration": {
            "common_origin_field": "data_origin", "f1": "Gunakan f1_evidence_documents sebagai corpus evidence dengan citation.",
            "f2": "Gunakan hanya sebagai context evidence; tidak membentuk rule otomatis.",
            "f3": "Hanya rows dengan status explicitly_eligible dan landmark/outcome kompatibel yang boleh diekspor ke train/test. Semua row sumber ini excluded."
        },
        "train_test_policy": "Kelompok sumber/paper harus menjadi unit split. Jangan split baris formulasi dari paper sama melintasi train/test.",
        "current_f3_status": "0 public rows eligible; synthetic_demo tetap dataset smoke-test terpisah."
    }


def validate_directory(output):
    output = Path(output)
    errors = []
    try:
        source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        errors.extend(validate_source(source))
        index = json.loads((output / "source_index.json").read_text())
        rows = [json.loads(line) for line in (output / "observed_formulations.jsonl").read_text().splitlines()]
        evidence = [json.loads(line) for line in (output / "f1_evidence_documents.jsonl").read_text().splitlines()]
        excluded = [json.loads(line) for line in (output / "f3_excluded_candidates.jsonl").read_text().splitlines()]
        expected_rows = normalized_rows(source)
        expected_evidence, expected_excluded = derive(expected_rows)
        if rows != expected_rows: errors.append("observed rows tidak bisa direplay dari sumber")
        if evidence != expected_evidence: errors.append("F1 evidence tidak bisa direplay")
        if excluded != expected_excluded: errors.append("F3 exclusion tidak bisa direplay")
        if index != {"source_count": 1, "observed_formulation_count": 15, "f1_document_count": 15, "f3_eligible_count": 0, "f3_excluded_count": 15, "sources": [{"source_id": source["source_id"], "doi": source["doi"], "license": source["license"], "source_sha256": sha(SOURCE_PATH)}]}: errors.append("source index tidak cocok")
        if json.loads((output / "training_contract.json").read_text()) != contract(sha(SOURCE_PATH)): errors.append("training contract tidak cocok")
        manifest = json.loads((output / "sha256_manifest.json").read_text())
        actual = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"}
        if manifest != {"algorithm": "sha256", "source_sha256": sha(SOURCE_PATH), "files": actual}: errors.append("manifest tidak cocok")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"gagal membaca output: {exc}")
    return errors


def build(output):
    output = Path(output).resolve()
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    errors = validate_source(source)
    if errors: raise ValueError(errors)
    rows = normalized_rows(source)
    evidence, excluded = derive(rows)
    index = {"source_count": 1, "observed_formulation_count": len(rows), "f1_document_count": len(evidence), "f3_eligible_count": 0, "f3_excluded_count": len(excluded), "sources": [{"source_id": source["source_id"], "doi": source["doi"], "license": source["license"], "source_sha256": sha(SOURCE_PATH)}]}
    dump(output / "source_index.json", index)
    dump(output / "observed_formulations.jsonl", rows, lines=True)
    dump(output / "f1_evidence_documents.jsonl", evidence, lines=True)
    dump(output / "f3_excluded_candidates.jsonl", excluded, lines=True)
    dump(output / "training_contract.json", contract(sha(SOURCE_PATH)))
    files = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"}
    dump(output / "sha256_manifest.json", {"algorithm": "sha256", "source_sha256": sha(SOURCE_PATH), "files": files})
    errors = validate_directory(output)
    return {"source_count": 1, "observed_formulation_count": len(rows), "f1_document_count": len(evidence), "f3_eligible_count": 0, "f3_excluded_count": len(excluded), "validation_errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "validate"])
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "public_observed")
    args = parser.parse_args()
    try:
        result = build(args.output) if args.command == "build" else {"validation_errors": validate_directory(args.output)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return int(bool(result.get("validation_errors")))
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
