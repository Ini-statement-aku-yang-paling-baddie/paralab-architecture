#!/usr/bin/env python3
"""Ingest dataset terbuka terverifikasi tanpa menggabungkannya ke data sintetis."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
COLLECTION_URL = "https://api.figshare.com/v2/collections/7132624"
ARTICLE_URL = "https://api.figshare.com/v2/articles/25451878"
DATASET_URL = "https://ndownloader.figshare.com/files/45187180"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, payload, lines=False):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n" for x in payload) if lines else json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8")


def normalize_records(records):
    scope = {"product_class": "shampoo_rinse_off_liquid_formulations", "observation_horizon": "36_hours_after_final_ph_adjustment", "limitations": ["Bukan trajectory stabilitas kosmetik 12 minggu.", "Tidak mendukung ekstrapolasi ke moisturizer, leave-on, keamanan, atau efektivitas."]}
    return [{"record_id": f"figshare:25451878:{row['ID']}", "source_record_id": row["ID"], "data_origin": "observed_open_dataset", "source_handle": "figshare-25451878-v1", "domain_scope": scope, "eligible_for_synthetic_training_join": False, "source_values": row} for row in records]


def profile(records):
    fields = sorted({k for row in records for k in row})
    return {"record_count": len(records), "fields": {field: {"missing_count": sum(row.get(field) in (None, "", "NA", "N/A") for row in records), "value_type_counts": dict(sorted(Counter(type(row.get(field)).__name__ for row in records).items()))} for field in fields}}


def cache_sources(output, collection_bytes, article_bytes, dataset_bytes, fetched_at):
    output = Path(output)
    raw = output / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "figshare_collection_7132624.json").write_bytes(collection_bytes)
    (raw / "figshare_article_25451878.json").write_bytes(article_bytes)
    (raw / "liquid_formulations_dataset_2023.json").write_bytes(dataset_bytes)
    dump(raw / "fetch_metadata.json", {"fetched_at": fetched_at, "urls": {"collection": COLLECTION_URL, "article": ARTICLE_URL, "dataset": DATASET_URL}})


def build_from_cache(output):
    output = Path(output)
    raw = output / "raw"
    collection = json.loads((raw / "figshare_collection_7132624.json").read_text())
    article = json.loads((raw / "figshare_article_25451878.json").read_text())
    records = json.loads((raw / "liquid_formulations_dataset_2023.json").read_text())
    if article.get("license", {}).get("name") != "CC0":
        raise ValueError("Lisensi dataset bukan CC0; tidak diproses")
    normalized = normalize_records(records)
    if len({x["source_record_id"] for x in normalized}) != len(normalized):
        raise ValueError("ID sumber duplikat")
    dump(output / "normalized" / "liquid_formulations.jsonl", normalized, lines=True)
    dump(output / "schema_profile.json", profile(records))
    dump(output / "quality_audit.json", {"collection_doi": collection.get("doi"), "article_doi": article.get("doi"), "license": article["license"], "record_count": len(records), "unique_source_ids": len({x["source_record_id"] for x in normalized}), "raw_sha256": {p.name: sha(p) for p in sorted(raw.glob("*.json"))}})
    files = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"}
    dump(output / "sha256_manifest.json", {"algorithm": "sha256", "files": files})
    errors = validate_directory(output)
    if errors: raise ValueError(errors)


def validate_directory(output):
    output = Path(output)
    errors = []
    try:
        raw = output / "raw"
        collection = json.loads((raw / "figshare_collection_7132624.json").read_text())
        article = json.loads((raw / "figshare_article_25451878.json").read_text())
        records = json.loads((raw / "liquid_formulations_dataset_2023.json").read_text())
        normalized = [json.loads(line) for line in (output / "normalized" / "liquid_formulations.jsonl").read_text().splitlines()]
        if normalized != normalize_records(records): errors.append("normalisasi tidak dapat direplay")
        if json.loads((output / "schema_profile.json").read_text()) != profile(records): errors.append("schema profile tidak cocok")
        audit = json.loads((output / "quality_audit.json").read_text())
        expected_audit = {"collection_doi": collection.get("doi"), "article_doi": article.get("doi"), "license": article["license"], "record_count": len(records), "unique_source_ids": len({x["source_record_id"] for x in normalized}), "raw_sha256": {p.name: sha(p) for p in sorted(raw.glob("*.json"))}}
        if audit != expected_audit: errors.append("quality audit tidak cocok")
        manifest = json.loads((output / "sha256_manifest.json").read_text())
        actual = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"}
        if manifest != {"algorithm": "sha256", "files": actual}: errors.append("manifest tidak cocok")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"gagal validasi ingest: {exc}")
    return errors


def fetch(url):
    with urlopen(url, timeout=60) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch-build", "build-from-cache", "validate"])
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "open_sources" / "figshare_shampoo")
    args = parser.parse_args()
    try:
        if args.command == "fetch-build":
            cache_sources(args.output, fetch(COLLECTION_URL), fetch(ARTICLE_URL), fetch(DATASET_URL), datetime.now(timezone.utc).isoformat())
            build_from_cache(args.output)
        elif args.command == "build-from-cache": build_from_cache(args.output)
        else:
            print(json.dumps({"validation_errors": validate_directory(args.output)}, ensure_ascii=False, indent=2))
            return int(bool(validate_directory(args.output)))
        print(json.dumps({"validation_errors": validate_directory(args.output)}, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
