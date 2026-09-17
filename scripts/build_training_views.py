#!/usr/bin/env python3
"""Bangun view konsumsi bersama F1/F3 dari dataset demo dan evidence publik."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FULL = ROOT / "scripts" / "build_full_dataset.py"
PUBLIC = ROOT / "scripts" / "build_public_evidence.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def dump(path, payload, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in payload) if lines else json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    Path(path).write_text(content, encoding="utf-8")


def source_views():
    full = DATA / "full_synthetic" / "derived"
    features = rows(full / "forecast_features.jsonl")
    labels = {x["feature_id"]: x for x in rows(full / "forecast_labels.jsonl")}
    synthetic = [{"id": f"TRAIN-{x['id']}", "data_origin": "synthetic_demo", "split": x["split"], "feature": x, "label": labels[x["id"]]} for x in features]
    public_evidence = rows(DATA / "public_observed" / "f1_evidence_documents.jsonl")
    synthetic_evidence = rows(full / "f1_train_corpus.jsonl")
    evidence = [{"id": f"CAT-{x['id']}", "data_origin": "observed_public", "document": x} for x in public_evidence] + [{"id": f"CAT-{x['id']}", "data_origin": "synthetic_demo", "document": x} for x in synthetic_evidence]
    return synthetic, evidence


def validate_directory(output):
    output = Path(output)
    errors = []
    try:
        forecast = rows(output / "f3_forecast_train.jsonl")
        train_rows = rows(output / "f3_train.jsonl")
        validation_rows = rows(output / "f3_validation.jsonl")
        test_rows = rows(output / "f3_test.jsonl")
        evidence = rows(output / "f1_evidence_catalog.jsonl")
        report = json.loads((output / "training_report.json").read_text())
        expected_forecast, expected_evidence = source_views()
        if forecast != expected_forecast: errors.append("view F3 tidak cocok dengan feature/label yang diizinkan")
        if train_rows != [x for x in expected_forecast if x["split"] == "train"]: errors.append("split train F3 tidak cocok")
        if validation_rows != [x for x in expected_forecast if x["split"] == "validation"]: errors.append("split validation F3 tidak cocok")
        if test_rows != [x for x in expected_forecast if x["split"] == "test"]: errors.append("split test F3 tidak cocok")
        if evidence != expected_evidence: errors.append("catalog F1 tidak cocok dengan sumber")
        if any(x["data_origin"] != "synthetic_demo" for x in forecast): errors.append("F3 menerima origin yang belum eligible")
        if any(x["feature"]["id"] != x["label"]["feature_id"] for x in forecast): errors.append("join feature/label F3 rusak")
        expected_report = {"f1": {"observed_public_documents": 15, "synthetic_demo_documents": len(expected_evidence) - 15}, "f3": {"synthetic_demo_rows_included": len(expected_forecast), "public_observed_rows_included": 0, "public_observed_rows_excluded": 15, "policy": "F3 hanya menerima source rows yang secara eksplisit eligible, longitudinal sampai landmark, punya outcome horizon, dan split per source group."}, "limitations": ["F3 saat ini belum memakai data publik karena paper yang diingest adalah proxy cross-sectional.", "Synthetic demo dan evidence publik tidak boleh digabung sebagai satu klaim validasi ilmiah.", "Tidak ada training model yang dijalankan oleh script ini."]}
        if report != expected_report: errors.append("training report tidak cocok")
        manifest = json.loads((output / "sha256_manifest.json").read_text())
        actual = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"}
        if manifest != {"algorithm": "sha256", "files": actual}: errors.append("manifest tidak cocok")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"gagal validasi view training: {exc}")
    return errors


def build(output):
    for command in ([sys.executable, str(FULL), "build"], [sys.executable, str(PUBLIC), "build"]):
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        if completed.returncode:
            raise ValueError(completed.stderr or completed.stdout)
    forecast, evidence = source_views()
    report = {"f1": {"observed_public_documents": 15, "synthetic_demo_documents": len(evidence) - 15}, "f3": {"synthetic_demo_rows_included": len(forecast), "public_observed_rows_included": 0, "public_observed_rows_excluded": 15, "policy": "F3 hanya menerima source rows yang secara eksplisit eligible, longitudinal sampai landmark, punya outcome horizon, dan split per source group."}, "limitations": ["F3 saat ini belum memakai data publik karena paper yang diingest adalah proxy cross-sectional.", "Synthetic demo dan evidence publik tidak boleh digabung sebagai satu klaim validasi ilmiah.", "Tidak ada training model yang dijalankan oleh script ini."]}
    output = Path(output).resolve()
    dump(output / "f3_forecast_train.jsonl", forecast, lines=True)
    dump(output / "f3_train.jsonl", [x for x in forecast if x["split"] == "train"], lines=True)
    dump(output / "f3_validation.jsonl", [x for x in forecast if x["split"] == "validation"], lines=True)
    dump(output / "f3_test.jsonl", [x for x in forecast if x["split"] == "test"], lines=True)
    dump(output / "f1_evidence_catalog.jsonl", evidence, lines=True)
    dump(output / "training_report.json", report)
    files = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"}
    dump(output / "sha256_manifest.json", {"algorithm": "sha256", "files": files})
    errors = validate_directory(output)
    return {"f3_rows": len(forecast), "f1_documents": len(evidence), "validation_errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "validate"])
    parser.add_argument("--output", type=Path, default=DATA / "training")
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
