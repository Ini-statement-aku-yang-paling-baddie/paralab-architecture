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
VERSION = "full-synthetic-v2"
# Accelerated stability time points per ISO/TR 18811:2018 / Cosmetics Europe,
# as run in Postles (2018). Week 16 closes the protocol window; the F3 label
# horizon stays at week 12.
WEEKS = [0, 1, 2, 4, 6, 8, 12, 16]
HORIZON_WEEK = 12
# Pre-agreed release specification checked at the horizon readout.
VISCOSITY_SPEC_RATIO = 0.88
PH_SPEC_DRIFT = 0.5
SPEC_UNCERTAIN_MARGIN = 0.06
SCENARIOS = ["stable", "early_viscosity_drop", "delayed_phase_separation", "ph_drift", "electrolyte_thickener_failure", "process_parameter_failure", "borderline"]
TABLES = ["projects", "formulas", "trials", "observation_series", "checkpoints", "outcomes"]

# INCI names resolvable by the F2 ingredient master, so F2 can derive the
# formula risk features that F3 consumes.
THICKENERS = [("ING:CARBOMER", "Carbomer"), ("ING:XANTHAN_GUM", "Xanthan Gum"),
              ("ING:HYDROXYETHYLCELLULOSE", "Hydroxyethylcellulose")]
EMULSIFIERS = [("ING:CETEARETH_20", "Ceteareth-20"), ("ING:GLYCERYL_STEARATE", "Glyceryl Stearate"),
               ("ING:POLYSORBATE_80", "Polysorbate 80"), None]
PRESERVATIVES = [("ING:PHENOXYETHANOL", "Phenoxyethanol", 0.3, 0.7),
                 ("ING:SODIUM_BENZOATE", "Sodium Benzoate", 0.2, 0.3),
                 ("ING:POTASSIUM_SORBATE", "Potassium Sorbate", 0.05, 0.25)]
EMOLLIENTS = [("ING:SQUALANE", "Squalane"), ("ING:CAPRYLIC_CAPRIC_TRIGLYCERIDE", "Caprylic/Capric Triglyceride"),
              ("ING:DIMETHICONE", "Dimethicone")]
ELECTROLYTE_IDS = {"ING:SODIUM_BENZOATE", "ING:POTASSIUM_SORBATE", "ING:SODIUM_HYALURONATE"}
SENSITIVE_THICKENER_IDS = {"ING:CARBOMER"}


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


def spec_violation(checkpoint, baseline):
    """How far past the release specification a checkpoint sits, as a ratio.
    Above 1.0 the sample is out of spec on viscosity loss or pH drift."""
    visc_ratio = checkpoint["measurements"]["viscosity_cp"] / baseline["measurements"]["viscosity_cp"]
    visc_breach = (1 - visc_ratio) / (1 - VISCOSITY_SPEC_RATIO)
    ph_breach = abs(checkpoint["measurements"]["ph"] - baseline["measurements"]["ph"]) / PH_SPEC_DRIFT
    return max(visc_breach, ph_breach)


# Weight of each risk factor in the hazard sum. These values are an assumption,
# not a measurement: nobody knows what a carbomer/electrolyte pairing is really
# worth in hazard units. modules/f3_stability_sentinel/weight_sensitivity.py exists precisely to
# test whether the F3 decision policy survives getting them wrong.
HAZARD_WEIGHTS = {
    "base": 0.35,
    "electrolyte_thickener_risk": 1.30,
    "emulsifier_missing": 0.85,
    "electrolyte_load": 0.30,
    "storage_40c": 0.55,
    "process_penalty": 0.40,
    "ph_deviation": 0.45,
}


def instability_hazard(formula_risk, process, temperature_c, ph0, weights=None):
    """Latent instability pressure of one trial, in arbitrary hazard units.

    Every term is a documented formulation/process risk factor, so the early
    measurement trend and the week-12 outcome share one cause instead of the
    outcome being looked up from a scenario name.
    """
    w = weights or HAZARD_WEIGHTS
    process_penalty = (
        max(0.0, process["heating_temp_c"] - 78) * 0.05
        + max(0.0, 2000 - process["homogenization_rpm"]) * 0.0004
        + max(0.0, 10 - process["mixing_time_min"]) * 0.06
    )
    return (
        w["base"]
        + w["electrolyte_thickener_risk"] * formula_risk["electrolyte_thickener_risk"]
        + w["emulsifier_missing"] * formula_risk["emulsifier_missing"]
        + w["electrolyte_load"] * formula_risk["electrolyte_load"]
        + w["storage_40c"] * (temperature_c == 40)
        + w["process_penalty"] * process_penalty
        + w["ph_deviation"] * abs(ph0 - 5.5)
    )


def sample_onset_week(rng, hazard):
    """Week at which the instability mechanism starts, drawn from an
    exponential survival model whose mean shortens as hazard rises.

    Onset is what makes observation time worth paying for: a late-onset trial
    is genuinely indistinguishable from a stable one at week 4, so no amount
    of modelling can recover it from early checkpoints alone.
    Returns None when onset falls outside the accelerated window.
    """
    mean_weeks = 14.0 / (1.0 + hazard)
    drawn = rng.expovariate(1.0 / mean_weeks)
    return next((week for week in WEEKS if week >= drawn), None)


def trajectory(rng, scenario, week, ph0, vis0, hazard, onset_week):
    """Measurements at one checkpoint.

    Before onset the sample only drifts within normal variation. After onset it
    degrades at a rate set by hazard. Per Postles (2018), pH tracks the
    underlying reaction far more reliably than viscosity, so viscosity carries
    the larger measurement noise here.
    """
    noise_ph = rng.uniform(-0.012, 0.012)
    noise_vis = rng.uniform(-750, 750)
    appearance = "uniform"

    if scenario == "early_viscosity_drop":
        shape, ph_shape = 1.15, 0.85
    elif scenario == "delayed_phase_separation":
        shape, ph_shape = 1.10, 0.90
    elif scenario == "ph_drift":
        shape, ph_shape = 0.85, 1.20
    elif scenario == "electrolyte_thickener_failure":
        shape, ph_shape = 1.10, 0.95
    elif scenario == "process_parameter_failure":
        shape, ph_shape = 1.00, 1.00
    elif scenario == "borderline":
        shape, ph_shape = 0.95, 1.05
    else:
        shape, ph_shape = 0.90, 1.10

    elapsed = 0 if onset_week is None else max(0, week - onset_week)
    ph = ph0 + noise_ph + 0.066 * hazard * elapsed * ph_shape + 0.0015 * week
    vis = vis0 + noise_vis - vis0 * 0.016 * hazard * elapsed * shape - 18 * week

    if elapsed > 0 and hazard > 1.5:
        severity = 0.016 * hazard * elapsed * shape
        if severity > 0.30:
            appearance = "separated"
        elif severity > 0.18:
            appearance = "heterogeneous"
        elif severity > 0.10:
            appearance = "creaming"

    return round(max(0.0, min(14.0, ph)), 3), round(max(0.0, vis)), appearance


def generate(seed=2026, hazard_weights=None):
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
            thickener = THICKENERS[rng.randrange(len(THICKENERS))]
            emulsifier = EMULSIFIERS[rng.randrange(len(EMULSIFIERS))]
            preservative = PRESERVATIVES[rng.randrange(len(PRESERVATIVES))]
            emollient = EMOLLIENTS[rng.randrange(len(EMOLLIENTS))]
            with_hyaluronate = rng.random() < 0.35

            components = [
                (*emollient, round(2.0 + rng.random() * 4.0, 4)),
                ("ING:GLYCERIN", "Glycerin", round(2.0 + rng.random() * 4.0, 4)),
                ("ING:NIACINAMIDE", "Niacinamide", round(2.0 + rng.random() * 3.0, 4)),
                (*thickener, round(0.2 + rng.random() * 0.6, 4)),
                (preservative[0], preservative[1], round(preservative[2] + rng.random() * preservative[3], 4)),
            ]
            if emulsifier is not None:
                components.append((*emulsifier, round(1.0 + rng.random() * 3.0, 4)))
            if with_hyaluronate:
                components.append(("ING:SODIUM_HYALURONATE", "Sodium Hyaluronate", round(0.1 + rng.random() * 0.9, 4)))
            water = round(100 - sum(x[-1] for x in components), 4)
            ingredients = [{"ingredient_id": "ING:AQUA", "inci_name": "Aqua", "pct": water}] + [
                {"ingredient_id": identifier, "inci_name": name, "pct": pct}
                for identifier, name, pct in components
            ]

            has_electrolyte = any(x[0] in ELECTROLYTE_IDS for x in components)
            formula_risk = {
                "electrolyte_load": int(has_electrolyte),
                "thickener_sensitivity": int(thickener[0] in SENSITIVE_THICKENER_IDS),
                "electrolyte_thickener_risk": int(has_electrolyte and thickener[0] in SENSITIVE_THICKENER_IDS),
                "emulsifier_missing": int(emulsifier is None),
            }
            process = {"mixing_time_min": 8 + rng.randrange(9),
                       "homogenization_rpm": 1800 + rng.randrange(9) * 150,
                       "heating_temp_c": 68 + rng.randrange(14)}
            data["formulas"].append(common(formula_id, seed, project_id=project_id, split=split,
                ingredients=ingredients, process=process, review_status="unreviewed_not_lab_recipe",
                created_at="2026-01-01", disclaimer="Formula simulasi dengan INCI kanonis; bukan resep laboratorium."))
            temperature = 40 if rng.random() < 0.45 else 25
            ph0 = rng.uniform(5.05, 6.05)
            vis0 = rng.uniform(12500, 19000)
            hazard = instability_hazard(formula_risk, process, temperature, ph0, hazard_weights)
            onset_week = sample_onset_week(rng, hazard)
            data["trials"].append(common(trial_id, seed, project_id=project_id, split=split,
                formula_id=formula_id, started_at="2026-01-01", scenario_family=scenario,
                latent_hazard=round(hazard, 5), latent_onset_week=onset_week))
            data["observation_series"].append(common(series_id, seed, project_id=project_id, split=split,
                trial_id=trial_id, temperature_c=temperature, humidity_pct=None))
            checkpoints = []
            for week in WEEKS:
                ph, viscosity, appearance = trajectory(rng, scenario, week, ph0, vis0, hazard, onset_week)
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
            # Outcome is the release specification read at the horizon, the way a
            # real stability study calls pass/fail. Randomness lives in the onset
            # week, so early checkpoints inform the call without deciding it.
            baseline = checkpoints[0]
            horizon_checkpoint = next(x for x in checkpoints if x["week"] == HORIZON_WEEK)
            breach = spec_violation(horizon_checkpoint, baseline)
            if breach >= 1 + SPEC_UNCERTAIN_MARGIN:
                status = "failed"
                failure_week = next(
                    (x["week"] for x in checkpoints
                     if x["week"] <= HORIZON_WEEK and spec_violation(x, baseline) >= 1),
                    HORIZON_WEEK,
                )
            elif breach >= 1 - SPEC_UNCERTAIN_MARGIN:
                status, failure_week = "uncertain", None
            else:
                status, failure_week = "passed", None
            data["outcomes"].append(common(f"{series_id}-OUT", seed, project_id=project_id, split=split,
                series_id=series_id, status=status, failure_week=failure_week, last_week=WEEKS[-1],
                horizon_week=HORIZON_WEEK, endpoint_checkpoint_id=horizon_checkpoint["id"], stopped=False,
                censor_reason=None, label_basis="seeded_onset_model_release_spec_not_lab_observation"))
    return data


def validate(data):
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    try:
        require(set(data) == set(TABLES), "tabel kanonis tidak cocok")
        expected = {"projects": 200, "formulas": 600, "trials": 600, "observation_series": 600, "checkpoints": 600 * len(WEEKS), "outcomes": 600}
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
            require(item["id"] in outcomes and outcomes[item["id"]]["endpoint_checkpoint_id"].endswith(f"W{HORIZON_WEEK:02d}"), f"{item['id']}: outcome")
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
                label_basis="seeded_hazard_model_not_lab_observation", horizon_week=12))
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
        "target": {"projects": 200, "trials_per_project": 3, "trials": 600, "checkpoints_per_trial": len(WEEKS), "checkpoints": 600 * len(WEEKS)},
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
            "target": {"projects": 200, "trials_per_project": 3, "trials": 600, "checkpoints_per_trial": len(WEEKS), "checkpoints": 600 * len(WEEKS)},
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
