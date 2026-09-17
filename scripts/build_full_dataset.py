#!/usr/bin/env python3
"""Generator dataset penuh ParaLab; simulasi demo, bukan data lab."""
import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
VERSION = "full-synthetic-v1"
WEEKS = [0, 1, 2, 4, 6, 8, 12]
SCENARIOS = ["stable", "early_viscosity_drop", "delayed_phase_separation", "ph_drift", "electrolyte_thickener_failure", "process_parameter_failure", "borderline"]
TABLES = ["projects", "formulas", "trials", "observation_series", "checkpoints", "outcomes"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def common(identifier, seed, **fields):
    return {"id": identifier, "data_origin": "synthetic_demo", "human_verified": False,
            "scientific_validation_status": "not_validated_for_production",
            "provenance": {"generator": VERSION, "seed": seed, "assumption_id": "FULL-SIM-001"}, **fields}


def split_for_family(family_index):
    if family_index < 70:
        return "train"
    if family_index < 85:
        return "validation"
    return "test"


def trajectory(rng, scenario, week, ph0, vis0, risk):
    noise_ph = rng.uniform(-0.025, 0.025)
    noise_vis = rng.uniform(-150, 150)
    ph = ph0 + noise_ph
    vis = vis0 + noise_vis
    appearance = "uniform"
    if scenario == "stable":
        ph += 0.004 * week
        vis -= 25 * week
    elif scenario == "early_viscosity_drop":
        vis -= vis0 * (0.018 * min(week, 4) + 0.012 * max(week - 4, 0)) * risk
    elif scenario == "delayed_phase_separation":
        vis -= vis0 * 0.008 * week * risk
        if week >= 8:
            appearance = "creaming" if week == 8 else "separated"
    elif scenario == "ph_drift":
        ph += 0.045 * week * risk
        vis -= 45 * week
    elif scenario == "electrolyte_thickener_failure":
        vis -= vis0 * 0.025 * week * risk
        if week >= 8:
            appearance = "heterogeneous" if week == 8 else "separated"
    elif scenario == "process_parameter_failure":
        vis -= vis0 * (0.006 * week + (0.22 if week >= 6 else 0)) * risk
        if week >= 12:
            appearance = "separated"
    else:
        ph += 0.018 * week * risk
        vis -= vis0 * 0.009 * week * risk
        if week >= 8:
            appearance = "uncertain"
    return round(max(0.0, min(14.0, ph)), 3), round(max(0.0, vis)), appearance


def generate(seed=2026):
    rng = random.Random(seed)
    data = {name: [] for name in TABLES}
    for project_index in range(200):
        project_number = project_index + 1
        family_index = project_index // 2
        split = split_for_family(family_index)
        project_id = f"FULL-P-{project_number:03d}"
        family_id = f"FULL-FAMILY-{family_index + 1:03d}"
        data["projects"].append(common(project_id, seed, family_id=family_id, split=split,
            product_family="o_w_gel_cream_moisturizer", target_skin="oily"))
        for trial_index in range(3):
            trial_number = trial_index + 1
            trial_id = f"{project_id}-T{trial_number}"
            formula_id = f"{project_id}-FORM{trial_number}"
            series_id = f"{trial_id}-SERIES"
            scenario = SCENARIOS[(project_index * 3 + trial_index) % len(SCENARIOS)]
            risk = round(0.85 + rng.random() * 0.30, 5)
            glycerin = round(2.8 + (family_index % 8) * 0.18 + trial_index * 0.12, 4)
            squalane = round(3.5 + (family_index % 5) * 0.35, 4)
            niacinamide = round(2.0 + (project_index % 4) * 0.5, 4)
            emulsifier = round(2.5 + (family_index % 4) * 0.25, 4)
            preservative = 1.0
            water = round(100 - glycerin - squalane - niacinamide - emulsifier - preservative, 4)
            ingredients = [{"ingredient_id": ingredient, "pct": pct} for ingredient, pct in [
                ("DEMO:WATER", water), ("DEMO:GLYCERIN", glycerin), ("DEMO:SQUALANE", squalane),
                ("DEMO:NIACINAMIDE", niacinamide), ("DEMO:EMULSIFIER_UNSPECIFIED", emulsifier),
                ("DEMO:PRESERVATIVE_UNSPECIFIED", preservative)]]
            process = {"mixing_time_min": 13 + trial_index + project_index % 5,
                       "homogenization_rpm": 2100 + (family_index % 8) * 175 + trial_index * 125,
                       "heating_temp_c": 68 + project_index % 5}
            data["formulas"].append(common(formula_id, seed, project_id=project_id, split=split,
                ingredients=ingredients, process=process, review_status="unreviewed_not_lab_recipe",
                created_at="2026-01-01", disclaimer="Formula simulasi dengan placeholder; bukan resep laboratorium."))
            data["trials"].append(common(trial_id, seed, project_id=project_id, split=split,
                formula_id=formula_id, started_at="2026-01-01", scenario_family=scenario, latent_risk=risk))
            temperature = 40 if (project_index + trial_index) % 3 else 25
            data["observation_series"].append(common(series_id, seed, project_id=project_id, split=split,
                trial_id=trial_id, temperature_c=temperature, humidity_pct=None))
            ph0 = rng.uniform(5.25, 5.85)
            vis0 = rng.uniform(12500, 19000)
            checkpoints = []
            for week in WEEKS:
                ph, viscosity, appearance = trajectory(rng, scenario, week, ph0, vis0, risk)
                checkpoint_id = f"{series_id}-W{week:02d}"
                checkpoint = common(checkpoint_id, seed, project_id=project_id, split=split, series_id=series_id,
                    week=week, observed_at=(date(2026, 1, 1) + timedelta(weeks=week)).isoformat(),
                    measurements={"ph": ph, "viscosity_cp": viscosity},
                    raw_measurements={"ph": ph, "viscosity_cp": viscosity},
                    quality={"ph": "observed", "viscosity_cp": "observed"}, missing_reasons={},
                    appearance=appearance,
                    note=f"SIMULASI belum direview. Minggu {week}; pH {ph}; viscosity {viscosity} cP; tampilan {appearance}.")
                data["checkpoints"].append(checkpoint)
                checkpoints.append(checkpoint)
            if scenario == "stable":
                status, failure_week = "passed", None
            elif scenario == "borderline":
                status, failure_week = "uncertain", None
            elif scenario == "early_viscosity_drop":
                failed = checkpoints[-1]["measurements"]["viscosity_cp"] < vis0 * 0.72
                status, failure_week = ("failed", 12) if failed else ("passed", None)
            elif scenario == "ph_drift":
                failed = abs(checkpoints[-1]["measurements"]["ph"] - checkpoints[0]["measurements"]["ph"]) > 0.45
                status, failure_week = ("failed", 12) if failed else ("passed", None)
            elif scenario == "delayed_phase_separation":
                status, failure_week = "failed", 12
            else:
                status, failure_week = "failed", 12
            data["outcomes"].append(common(f"{series_id}-OUT", seed, project_id=project_id, split=split,
                series_id=series_id, status=status, failure_week=failure_week, last_week=12,
                horizon_week=12, endpoint_checkpoint_id=checkpoints[-1]["id"], stopped=False,
                censor_reason=None, label_basis="seeded_scenario_not_lab_observation"))
    return data


def validate(data):
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    try:
        require(set(data) == set(TABLES), "tabel kanonis tidak cocok")
        expected = {"projects": 200, "formulas": 600, "trials": 600, "observation_series": 600, "checkpoints": 4200, "outcomes": 600}
        require({key: len(value) for key, value in data.items()} == expected, "jumlah target arsitektur tidak terpenuhi")
        all_rows = [row for table in TABLES for row in data[table]]
        ids = [row["id"] for row in all_rows]
        require(len(ids) == len(set(ids)), "ID global duplikat")
        projects = {x["id"]: x for x in data["projects"]}
        formulas = {x["id"]: x for x in data["formulas"]}
        trials = {x["id"]: x for x in data["trials"]}
        series = {x["id"]: x for x in data["observation_series"]}
        outcomes = {x["series_id"]: x for x in data["outcomes"]}
        require(Counter(x["project_id"] for x in data["trials"]) == Counter({pid: 3 for pid in projects}), "setiap proyek harus tiga trial")
        family_splits = {}
        for project in data["projects"]:
            require(family_splits.setdefault(project["family_id"], project["split"]) == project["split"], "family leakage")
        require(Counter(x["split"] for x in data["projects"]) == {"train": 140, "validation": 30, "test": 30}, "rasio split proyek")
        for formula in data["formulas"]:
            require(formula["project_id"] in projects and formula["split"] == projects[formula["project_id"]]["split"], f"{formula['id']}: project/split")
            require(math.isclose(sum(x["pct"] for x in formula["ingredients"]), 100, abs_tol=1e-6), f"{formula['id']}: total formula")
            require(formula["review_status"] == "unreviewed_not_lab_recipe", f"{formula['id']}: review status")
        for trial in data["trials"]:
            require(trial["formula_id"] in formulas and trial["scenario_family"] in SCENARIOS, f"{trial['id']}: formula/scenario")
        for item in data["observation_series"]:
            require(item["trial_id"] in trials and item["temperature_c"] in {25, 40}, f"{item['id']}: trial/storage")
            checkpoints = [x for x in data["checkpoints"] if x["series_id"] == item["id"]]
            require([x["week"] for x in checkpoints] == WEEKS, f"{item['id']}: checkpoint lengkap")
            require(item["id"] in outcomes and outcomes[item["id"]]["endpoint_checkpoint_id"] == checkpoints[-1]["id"], f"{item['id']}: outcome")
        for checkpoint in data["checkpoints"]:
            require(checkpoint["series_id"] in series, f"{checkpoint['id']}: series")
            require(all(type(value) in (int, float) and math.isfinite(value) for value in checkpoint["measurements"].values()), f"{checkpoint['id']}: measurement")
        require(set(x["scenario_family"] for x in data["trials"]) == set(SCENARIOS), "scenario coverage")
        require({x["status"] for x in data["outcomes"]} >= {"passed", "failed", "uncertain"}, "outcome coverage")
        for row in all_rows:
            require(row["data_origin"] == "synthetic_demo" and row["human_verified"] is False, f"{row['id']}: provenance label")
            require(row["provenance"] == {"generator": VERSION, "seed": row["provenance"]["seed"], "assumption_id": "FULL-SIM-001"}, f"{row['id']}: provenance")
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        errors.append(f"schema tidak valid: {exc}")
    return errors


DERIVED = ["journal_documents", "f1_train_corpus", "forecast_features", "forecast_labels", "forecast_excluded", "f5_examples"]


def derive(data):
    result = {name: [] for name in DERIVED}
    trials = {x["id"]: x for x in data["trials"]}
    formulas = {x["id"]: x for x in data["formulas"]}
    outcomes = {x["series_id"]: x for x in data["outcomes"]}
    checkpoints_by_series = {}
    for checkpoint in data["checkpoints"]:
        checkpoints_by_series.setdefault(checkpoint["series_id"], []).append(checkpoint)
    for series in data["observation_series"]:
        seed = series["provenance"]["seed"]
        trial = trials[series["trial_id"]]
        formula = formulas[trial["formula_id"]]
        checkpoints = checkpoints_by_series[series["id"]]
        outcome = outcomes[series["id"]]
        metadata = {"project_id": series["project_id"], "series_id": series["id"], "split": series["split"]}
        document = common(f"FULL-DOC-{series['id']}", seed, **metadata, formula_id=formula["id"],
            checkpoint_ids=[x["id"] for x in checkpoints], outcome_id=outcome["id"],
            document_scope="synthetic_historical_trajectory_not_forecast_input",
            text="\n".join([f"SIMULASI O/W {series['id']}; storage {series['temperature_c']} C; skenario {trial['scenario_family']}."] +
                             [x["note"] for x in checkpoints] +
                             [f"Outcome simulasi: {outcome['status']}. Bukan hasil laboratorium."]))
        result["journal_documents"].append(document)
        if series["split"] == "train":
            result["f1_train_corpus"].append(document.copy())
        early = [x for x in checkpoints if x["week"] <= 4]
        feature = common(f"FULL-FEAT-{series['id']}", seed, **metadata, formula_id=formula["id"],
            feature_schema_version="landmark4-full-v1", landmark_week=4, horizon_week=12,
            checkpoint_ids=[x["id"] for x in early], temperature_c=series["temperature_c"],
            formula_concentrations=formula["ingredients"], process=formula["process"],
            observations=[{"week": x["week"], "measurements": x["measurements"], "quality": x["quality"], "appearance": x["appearance"]} for x in early])
        if outcome["status"] == "uncertain":
            result["forecast_excluded"].append(common(f"FULL-EXCL-{series['id']}", seed, **metadata,
                outcome_id=outcome["id"], reasons=["uncertain_outcome_no_binary_label"]))
        else:
            result["forecast_features"].append(feature)
            result["forecast_labels"].append(common(f"FULL-LABEL-{series['id']}", seed, **metadata,
                feature_id=feature["id"], outcome_id=outcome["id"], failed_by_12=int(outcome["status"] == "failed"),
                label_basis="seeded_scenario_not_lab_observation", horizon_week=12))
        for checkpoint in checkpoints:
            result["f5_examples"].append(common(f"FULL-VOICE-{checkpoint['id']}", seed, **metadata,
                checkpoint_id=checkpoint["id"], transcript=checkpoint["note"],
                transcript_origin="deterministic_text_not_recorded_audio", requires_confirmation=True,
                target={"week": checkpoint["week"], "observed_at": checkpoint["observed_at"],
                        "measurements": checkpoint["measurements"], "quality": checkpoint["quality"],
                        "appearance": checkpoint["appearance"]}))
    return result


def validate_derived(data, derived):
    errors = validate(data)
    if errors:
        return errors
    expected = derive(data)
    if set(derived) != set(DERIVED):
        errors.append("tabel turunan tidak cocok")
        return errors
    for name in DERIVED:
        if derived[name] != expected[name]:
            errors.append(f"{name}: tidak dapat direplay dari data kanonis")
    return errors


def dump(path, payload, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if lines:
        text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n" for row in payload)
    else:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def metrics(data, derived):
    return {"dataset_version": VERSION, "scope": "synthetic_demo_not_lab_validation",
            "canonical_counts": {name: len(data[name]) for name in TABLES},
            "derived_counts": {name: len(derived[name]) for name in DERIVED},
            "project_splits": dict(sorted(Counter(x["split"] for x in data["projects"]).items())),
            "scenario_counts": dict(sorted(Counter(x["scenario_family"] for x in data["trials"]).items())),
            "outcome_counts": dict(sorted(Counter(x["status"] for x in data["outcomes"]).items())),
            "forecast_labels": dict(sorted(Counter(f"{x['split']}:{x['failed_by_12']}" for x in derived["forecast_labels"]).items())),
            "validation_errors": validate_derived(data, derived), "ml_training_executed": False}


def build(output, seed=2026):
    output = Path(output).resolve()
    data = generate(seed)
    errors = validate(data)
    if errors:
        raise ValueError(errors)
    derived = derive(data)
    errors = validate_derived(data, derived)
    if errors:
        raise ValueError(errors)
    for group, tables in (("canonical", data), ("derived", derived)):
        for name, payload in tables.items():
            dump(output / group / f"{name}.jsonl", payload, lines=True)
    dump(output / "generation_contract.json", {
        "version": VERSION, "seed": seed, "weeks": WEEKS, "scenarios": SCENARIOS,
        "target": {"projects": 200, "trials_per_project": 3, "trials": 600, "checkpoints_per_trial": 7, "checkpoints": 4200},
        "split_unit": "formula_family; two projects per family", "split_counts": {"train_projects": 140, "validation_projects": 30, "test_projects": 30},
        "disclaimer": "Semua trajectory adalah simulasi seeded, bukan hasil laboratorium atau resep yang layak diracik."
    })
    dump(output / "metrics.json", metrics(data, derived))
    files = {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name != "sha256_manifest.json"}
    dump(output / "sha256_manifest.json", {"algorithm": "sha256", "files": files})
    errors = validate_directory(output)
    if errors:
        raise ValueError(errors)
    return metrics(data, derived)


def validate_directory(output):
    output = Path(output)
    errors = []
    try:
        contract = json.loads((output / "generation_contract.json").read_text())
        seed = contract["seed"]
        def read_group(group, names):
            return {name: [json.loads(line) for line in (output / group / f"{name}.jsonl").read_text().splitlines()] for name in names}
        data = read_group("canonical", TABLES)
        derived = read_group("derived", DERIVED)
        errors.extend(validate_derived(data, derived))
        if data != generate(seed):
            errors.append("data kanonis tidak dapat direplay dari seed")
        expected_contract = {"version": VERSION, "seed": seed, "weeks": WEEKS, "scenarios": SCENARIOS,
            "target": {"projects": 200, "trials_per_project": 3, "trials": 600, "checkpoints_per_trial": 7, "checkpoints": 4200},
            "split_unit": "formula_family; two projects per family", "split_counts": {"train_projects": 140, "validation_projects": 30, "test_projects": 30},
            "disclaimer": "Semua trajectory adalah simulasi seeded, bukan hasil laboratorium atau resep yang layak diracik."}
        if contract != expected_contract:
            errors.append("generation contract tidak cocok")
        if json.loads((output / "metrics.json").read_text()) != metrics(data, derived):
            errors.append("metrics tidak cocok")
        manifest = json.loads((output / "sha256_manifest.json").read_text())
        actual = {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob("*")) if path.is_file() and path.name != "sha256_manifest.json"}
        if manifest != {"algorithm": "sha256", "files": actual}:
            errors.append("manifest tidak cocok")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"gagal membaca dataset penuh: {exc}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "validate"])
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "full_synthetic")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    try:
        result = build(args.output, args.seed) if args.command == "build" else {"validation_errors": validate_directory(args.output)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return int(bool(result.get("validation_errors")))
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
