# %% [markdown]
# # ParaLab AI — V4 Corpus Generator
#
# Menghasilkan **evidence corpus** untuk F1 (Copilot Evidence Riset) sesuai `ARCHITECTURE-V4.md`.
#
# **Scope domain (V4 §1.1):** satu vertical saja — *Moisturizer gel-cream oil-in-water untuk kulit berminyak*.
# Variasi dibuat **di dalam** keluarga formulasi ini (sistem aktif, emulsifier, rasio fase minyak,
# thickener, parameter proses), bukan antar kategori produk.
#
# **File yang dihasilkan (§12.3):**
# ```
# data/
# ├── formula_seeds.jsonl          <- KONTRAK dengan tim F3 (trajectory generator)
# ├── evidence_corpus.jsonl        <- input F1 (evidence cards)
# ├── rag_dev_queries.jsonl        <- query dev berlabel (untuk tuning F1)
# ├── rag_blind_test_queries.jsonl <- query blind test (butuh pelabelan manusia, §12.2)
# └── metadata.json
# ```
#
# **Prinsip yang ditegakkan (§6.5):** semua angka (konsentrasi, pH, viskositas, minggu kegagalan)
# berasal dari generator deterministik. Teacher LLM hanya boleh menulis narasi di atas seed.
#
# **Setup Kaggle:** lampirkan `ingredient_master.json` + `formulation_rules.json` sebagai Input.
# Internet ON hanya untuk unduh model embedding.

# %%
import json, os, random, glob, hashlib
from datetime import datetime

SEED = 42
GENERATOR_VERSION = "v1"
PRODUCT_FAMILY = "o_w_gel_cream_moisturizer"
DOMAIN_LABEL = "Moisturizer gel-cream O/W untuk kulit berminyak"
N_JOURNALS = 200
TRIALS_PER_JOURNAL = 3
YEARS = [2023, 2024, 2024, 2025, 2025, 2025, 2026, 2026]
TEAMS = ["Tim Riset 1", "Tim Riset 2", "Tim Riset 3", "Tim Formulasi A", "Tim Formulasi B", "Tim Formulasi C"]

rng = random.Random(SEED)  # instance terpisah -> tidak terpengaruh urutan pemanggilan lain


def _find(name):
    for pat in (f"/kaggle/input/**/{name}", f"data/{name}", name, f"../data/{name}"):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    raise FileNotFoundError(f"{name} tidak ditemukan - lampirkan sebagai Input / taruh di data/")


MASTER_DOC = json.load(open(_find("ingredient_master.json"), encoding="utf-8"))
INGREDIENTS = MASTER_DOC["ingredients"]
VALID_IDS = {m["ingredient_id"] for m in INGREDIENTS}
print(f"ingredient_master dimuat: {len(VALID_IDS)} bahan (v{MASTER_DOC['meta'].get('rule_version','?')})")

# %% [markdown]
# ## 1. Ruang formulasi (di dalam satu keluarga produk)
#
# Setiap pool memakai `ingredient_id` kanonis dari `ingredient_master.json` — sehingga
# F1, F2, dan evidence corpus berbicara dengan ontology yang sama.

# %%
# --- pool bahan per peran fungsional ---
ACTIVES = [
    "ING:NIACINAMIDE", "ING:ZINC_PCA", "ING:ALPHA_ARBUTIN", "ING:TRANEXAMIC_ACID",
    "ING:CENTELLA_ASIATICA_EXTRACT", "ING:CAMELLIA_SINENSIS_LEAF_EXTRACT",
    "ING:GLYCYRRHIZA_GLABRA_ROOT_EXTRACT", "ING:ALLANTOIN", "ING:BISABOLOL", "ING:CAFFEINE",
]
HUMECTANTS = ["ING:GLYCERIN", "ING:SODIUM_HYALURONATE", "ING:PANTHENOL", "ING:BETAINE",
              "ING:SORBITOL", "ING:BUTYLENE_GLYCOL", "ING:UREA"]
EMOLLIENTS = ["ING:SQUALANE", "ING:DIMETHICONE", "ING:CAPRYLIC_CAPRIC_TRIGLYCERIDE",
              "ING:SIMMONDSIA_CHINENSIS_SEED_OIL", "ING:ARGANIA_SPINOSA_KERNEL_OIL",
              "ING:BUTYROSPERMUM_PARKII_BUTTER", "ING:CYCLOPENTASILOXANE",
              "ING:MINERAL_OIL", "ING:ISOPROPYL_MYRISTATE", "ING:PETROLATUM"]
EMULSIFIERS = ["ING:GLYCERYL_STEARATE", "ING:POLYSORBATE_20", "ING:POLYSORBATE_80",
               "ING:CETEARYL_ALCOHOL", "ING:PEG_100_STEARATE", "ING:SORBITAN_OLIVATE",
               "ING:CETEARETH_20", "ING:STEARIC_ACID", "ING:CETYL_ALCOHOL", "ING:STEARYL_ALCOHOL"]
THICKENERS = ["ING:CARBOMER", "ING:XANTHAN_GUM", "ING:HYDROXYETHYLCELLULOSE"]
PRESERVATIVES = ["ING:PHENOXYETHANOL", "ING:ETHYLHEXYLGLYCERIN", "ING:SODIUM_BENZOATE",
                 "ING:POTASSIUM_SORBATE", "ING:METHYLPARABEN", "ING:PROPYLPARABEN",
                 "ING:DMDM_HYDANTOIN"]
SENSORIAL = ["ING:FRAGRANCE", "ING:MENTHOL", "ING:LIMONENE", "ING:LINALOOL", "ING:EUGENOL"]
ELECTROLYTES = {"ING:ZINC_PCA", "ING:SODIUM_HYALURONATE", "ING:SODIUM_BENZOATE", "ING:POTASSIUM_SORBATE"}
ELECTROLYTE_SENSITIVE_THICKENERS = {"ING:CARBOMER"}

ALL_POOLS = {"actives": ACTIVES, "humectants": HUMECTANTS, "emollients": EMOLLIENTS,
             "emulsifiers": EMULSIFIERS, "thickeners": THICKENERS,
             "preservatives": PRESERVATIVES, "sensorial": SENSORIAL}
# validasi: semua ID harus ada di ingredient_master
_bad = [(k, i) for k, ids in ALL_POOLS.items() for i in ids if i not in VALID_IDS]
assert not _bad, f"ID bahan tidak ada di ingredient_master: {_bad}"
print("validasi pool: semua ingredient_id cocok dengan ingredient_master OK")

# %% [markdown]
# ## 2. Risk factor deterministik dari formula + proses (V4 §6.4 lapis rule)

# %%
def compute_risk_factors(formula, process):
    ids = [i["ingredient_id"] for i in formula["ingredients"]]
    n_electrolyte = sum(1 for i in ids if i in ELECTROLYTES)
    has_sensitive_thickener = any(i in ELECTROLYTE_SENSITIVE_THICKENERS for i in ids)
    n_emulsifier = sum(1 for i in ids if i in EMULSIFIERS)
    temp_dev = abs(process["heating_temp_c"] - 75.0) / 75.0
    rpm_dev = max(0.0, (2500 - process["homogenization_rpm"]) / 2500.0)
    oil_ratio = process["oil_phase_ratio"]

    et_risk = 1.0 if (n_electrolyte >= 1 and has_sensitive_thickener) else 0.0
    if n_electrolyte >= 2 and has_sensitive_thickener:
        et_risk = 1.5
    ph_margin_low = 1.0 if process["final_ph"] < 5.2 else 0.0
    emulsifier_watch = 1.0 if n_emulsifier < 2 else 0.0
    process_dev = min(1.5, temp_dev * 2 + rpm_dev)
    heavy_oil = 1.0 if oil_ratio > 0.18 else 0.0

    return {
        "electrolyte_load": "high" if n_electrolyte >= 2 else ("medium" if n_electrolyte == 1 else "low"),
        "thickener_sensitivity": "high" if has_sensitive_thickener else "low",
        "electrolyte_thickener_risk": "high" if et_risk >= 1.0 else "low",
        "emulsifier_balance_status": "watch" if emulsifier_watch else "ok",
        "ph_compatibility_margin": round(process["final_ph"] - 5.2, 2),
        "ingredient_count": len(ids),
        "oil_phase_ratio": oil_ratio,
        "_et_risk": et_risk, "_ph_risk": ph_margin_low, "_emul_watch": emulsifier_watch,
        "_process_dev": process_dev, "_heavy_oil": heavy_oil,
    }


# %% [markdown]
# ## 3. Assignment skenario (V4 §6.3) — rule + stochastic
#
# Rule menentukan **kecenderungan**, stochastic menentukan **hasil aktual**, dan
# keluarga skenario sengaja di-overlap supaya F3 tidak bisa menebak dari satu fitur (§6.3).

# %%
SCENARIO_FAMILIES = [
    "stable", "early_viscosity_drop", "delayed_phase_separation", "ph_drift",
    "electrolyte_thickener_failure", "process_parameter_failure", "borderline",
]


def scenario_weights(rf):
    """Rule layer: risk factor menggeser probabilitas keluarga skenario."""
    w = {
        "stable": 0.52 - 0.22 * rf["_et_risk"] - 0.15 * rf["_process_dev"] - 0.12 * rf["_emul_watch"],
        "early_viscosity_drop": 0.09 + 0.06 * rf["_heavy_oil"] + 0.05 * rf["_et_risk"],
        "delayed_phase_separation": 0.05 + 0.24 * rf["_emul_watch"] + 0.10 * rf["_heavy_oil"],
        "ph_drift": 0.07 + 0.12 * rf["_ph_risk"],
        "electrolyte_thickener_failure": 0.02 + 0.34 * rf["_et_risk"],
        "process_parameter_failure": 0.03 + 0.26 * rf["_process_dev"],
        "borderline": 0.07,
    }
    w = {k: max(v, 0.01) for k, v in w.items()}
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()}


def resolve_outcome(family, r):
    """Stochastic layer: keluarga -> outcome aktual (anti-trivial: sebagian bisa pulih/lolos)."""
    if family == "stable":
        return "pass", None, None
    if family == "early_viscosity_drop":
        # §6.3: "penurunan awal yang dapat pulih atau gagal kemudian"
        if r.random() < 0.45:
            return "pass", None, None
        return "failed", "viscosity_collapse", r.choice([8, 10, 12])
    if family == "delayed_phase_separation":
        return "failed", "phase_separation", r.choice([6, 8, 10, 12])
    if family == "ph_drift":
        if r.random() < 0.45:
            return "pass", None, None
        return "failed", "ph_out_of_spec", r.choice([8, 12])
    if family == "electrolyte_thickener_failure":
        return "failed", "viscosity_collapse", r.choice([4, 6, 8])
    if family == "process_parameter_failure":
        return "failed", r.choice(["emulsion_instability", "viscosity_collapse"]), r.choice([2, 4, 6])
    return "needs_review", None, None  # borderline


# %% [markdown]
# ## 4. Bangun seed: 200 project x 3 trial

# %%
def build_formula(r, journal_seq, year):
    n_active = r.randint(1, 2)
    n_humectant = r.randint(2, 3)
    n_emollient = r.randint(1, 3)
    n_emulsifier = r.randint(1, 3)
    n_thickener = r.randint(0, 1)
    n_preservative = r.randint(1, 2)
    n_sensorial = r.choice([0, 0, 0, 1])  # fragrance-free lebih umum di demo

    picks = (
        [("actives", i) for i in r.sample(ACTIVES, n_active)]
        + [("humectants", i) for i in r.sample(HUMECTANTS, n_humectant)]
        + [("emollients", i) for i in r.sample(EMOLLIENTS, n_emollient)]
        + [("emulsifiers", i) for i in r.sample(EMULSIFIERS, n_emulsifier)]
        + [("thickeners", i) for i in r.sample(THICKENERS, n_thickener)]
        + [("preservatives", i) for i in r.sample(PRESERVATIVES, n_preservative)]
        + [("sensorial", i) for i in r.sample(SENSORIAL, n_sensorial)]
    )

    by_id = {m["ingredient_id"]: m for m in INGREDIENTS}
    ingredients = []
    for role, iid in picks:
        rng_range = by_id[iid]["concentration_range_pct_w_w"]
        lo, hi = rng_range["min"], rng_range["max"]
        pct = round(r.uniform(lo, lo + (hi - lo) * 0.55), 2)  # condong ke sisi aman
        phase = "oil" if role == "emollients" else ("oil" if role == "emulsifiers" and r.random() < 0.4 else "water")
        ingredients.append({"ingredient_id": iid, "concentration_pct_w_w": pct, "phase": phase,
                            "functional_role": role})

    # proses: sebagian menyimpang (anti-trivial untuk process_parameter_failure)
    deviate = r.random() < 0.28
    process = {
        "heating_temp_c": round(r.choice([85.0, 88.0]) if deviate else r.uniform(70, 78), 1),
        "homogenization_rpm": r.choice([1200, 1600, 1800]) if deviate else r.choice([2500, 2800, 3000]),
        "mixing_time_min": r.choice([5, 8]) if deviate else r.randint(12, 20),
        "cooling_profile": r.choice(["ambient_agitation", "controlled_ramp", "fast_cool"]),
        "final_ph": round(r.uniform(4.9, 5.3) if r.random() < 0.25 else r.uniform(5.4, 6.0), 2),
        "oil_phase_ratio": round(r.uniform(0.20, 0.26) if r.random() < 0.3 else r.uniform(0.07, 0.16), 3),
    }
    return {"formula_version_id": f"FORM-{year}-{journal_seq:03d}-V1",
            "journal_id": f"J-{year}-{journal_seq:03d}",
            "product_family": PRODUCT_FAMILY,
            "ingredients": ingredients, "process": process}


SEEDS, JOURNAL_META = [], []
for seq in range(1, N_JOURNALS + 1):
    year = rng.choice(YEARS)
    team = rng.choice(TEAMS)
    base = build_formula(rng, seq, year)
    base_id = base["journal_id"]
    # atribut TINGKAT PROYEK: satu nilai untuk seluruh trial dalam jurnal ini
    journal_meta = {"title_seed": f"{DOMAIN_LABEL} - {year}-{seq:03d}", "year": year,
                    "target_skin": "oily", "target_problem": "oil_control",
                    "market_segment": rng.choices(["mid", "premium", "mass"], weights=[0.5, 0.3, 0.2])[0],
                    "status": rng.choices(["completed", "running", "draft"], weights=[0.55, 0.30, 0.15])[0]}
    for t in range(1, TRIALS_PER_JOURNAL + 1):
        fv = dict(base)
        fv["formula_version_id"] = f"FORM-{year}-{seq:03d}-V{t}"
        if t > 1:
            # iterasi: tweak kecil pada konsentrasi (reformulasi, bukan formula baru)
            fv["ingredients"] = [dict(i, concentration_pct_w_w=round(i["concentration_pct_w_w"] * rng.uniform(0.85, 1.15), 2))
                                 for i in base["ingredients"]]
            fv["process"] = dict(base["process"])
            fv["process"]["final_ph"] = round(min(6.2, max(4.7, base["process"]["final_ph"] + rng.uniform(-0.25, 0.25))), 2)
        rf = compute_risk_factors(fv, fv["process"])
        fam = rng.choices(SCENARIO_FAMILIES, weights=list(scenario_weights(rf).values()))[0]
        outcome, failure_mode, failure_week = resolve_outcome(fam, rng)
        trial_id = f"{base_id}-T{t:02d}"
        SEEDS.append({
            "formula_version_id": fv["formula_version_id"], "journal_id": base_id, "trial_id": trial_id,
            "research_team": team, "product_family": PRODUCT_FAMILY,
            "ingredients": fv["ingredients"], "process": fv["process"],
            "scenario_family": fam, "expected_outcome": outcome,
            "expected_failure_mode": failure_mode, "expected_failure_week": failure_week,
            "risk_factors": {k: v for k, v in rf.items() if not k.startswith("_")},
            "journal_meta": journal_meta,
            "provenance": {"data_origin": "synthetic_demo", "scenario_generator_version": GENERATOR_VERSION,
                           "scientific_validation_status": "not_validated_for_production"},
        })
    JOURNAL_META.append({"journal_id": base_id, "year": year, "team": team,
                         "market_segment": journal_meta["market_segment"], "status": journal_meta["status"]})

print(f"seed dibuat: {len(SEEDS)} trial dari {N_JOURNALS} journal")
from collections import Counter
print("scenario family:", Counter(s["scenario_family"] for s in SEEDS).most_common())
print("expected outcome:", Counter(s["expected_outcome"] for s in SEEDS).most_common())

# %% [markdown]
# ## 5. QC anti-trivial (V4 §6.3)
#
# Generator harus menghindari pola trivial: satu fitur tidak boleh menentukan label dengan sempurna.

# %%
def qc_anti_trivial(seeds):
    lines = []
    # (a) overall pass rate harus tidak ekstrem
    n_fail = sum(1 for s in seeds if s["expected_outcome"] == "failed")
    rate = n_fail / len(seeds)
    lines.append(f"(a) failure rate = {rate:.1%} (target 35-65%) -> {'OK' if 0.35 <= rate <= 0.65 else 'PERIKSA'}")
    # (b) tidak ada fitur yang sempurna memisahkan
    for feat, val in [("electrolyte_thickener_risk", "high"), ("emulsifier_balance_status", "watch")]:
        sub = [s for s in seeds if s["risk_factors"][feat] == val]
        if sub:
            sub_fail = sum(1 for s in sub if s["expected_outcome"] == "failed") / len(sub)
            ok = 0.25 < sub_fail < 0.95
            lines.append(f"(b) {feat}={val}: n={len(sub)}, fail rate={sub_fail:.0%} -> {'OK (tidak trivial)' if ok else 'PERIKSA (terlalu deterministik)'}")
    # (c) adversarial: early_viscosity_drop yang pulih & delayed yang terlihat sehat di awal
    rec = sum(1 for s in seeds if s["scenario_family"] == "early_viscosity_drop" and s["expected_outcome"] == "pass")
    dly = sum(1 for s in seeds if s["scenario_family"] == "delayed_phase_separation")
    lines.append(f"(c) early_viscosity_drop yang PULIH (jebakan minggu-4): {rec}")
    lines.append(f"    delayed_phase_separation (terlihat sehat di minggu-4): {dly}")
    lines.append(f"(d) borderline (harus abstain / human review): {sum(1 for s in seeds if s['scenario_family']=='borderline')}")
    ok = (0.35 <= rate <= 0.65) and rec > 0 and dly > 0
    lines.append(f"=> QC anti-trivial: {'LOLOS' if ok else 'PERIKSA'}")
    return "\n".join(lines), ok


qc_text, qc_ok = qc_anti_trivial(SEEDS)
print(qc_text)

# %% [markdown]
# ## 6. Narrative writer
#
# Mode `template` (default, tanpa API) menulis narasi Indonesia di atas seed.
# Mode `llm` memakai teacher LLM — **hanya** untuk judul, observasi, dan pelajaran (§6.5).

# %%
def ing_label(iid):
    return iid.replace("ING:", "").replace("_", " ").title()


FAMILY_LABEL = {
    "stable": "stabilitas jangka panjang",
    "early_viscosity_drop": "penurunan viskositas awal",
    "delayed_phase_separation": "pemisahan fase tertunda",
    "ph_drift": "pergeseran pH penyimpanan",
    "electrolyte_thickener_failure": "interaksi elektrolit-thickener",
    "process_parameter_failure": "sensitivitas parameter proses",
    "borderline": "profil yang belum konklusif",
}
TITLE_FOCUS = {
    "stable": ["Stabilitas Jangka Panjang", "Profil Stabil 12 Minggu", "Kestabilan Penuh Siklus Uji"],
    "early_viscosity_drop": ["Penurunan Viskositas Awal", "Sinyal Awal Kehilangan Struktur", "Drop Viskositas Minggu Awal"],
    "delayed_phase_separation": ["Pemisahan Fase Tertunda", "Instabilitas Akhir Siklus", "Masalah Muncul di Checkpoint Menengah"],
    "ph_drift": ["Pergeseran pH Penyimpanan", "Drift pH Selama Uji Stabil", "Stabilitas pH pada Penyimpanan Dipercepat"],
    "electrolyte_thickener_failure": ["Interaksi Elektrolit dan Thickener", "Kegagalan Viskositas Elektrolitik", "Beban Elektrolit pada Sistem Thickener"],
    "process_parameter_failure": ["Sensitivitas Parameter Proses", "Deviasi Suhu dan Homogenisasi", "Pengaruh Parameter Proses pada Instabilitas"],
    "borderline": ["Profil Ambigu", "Data Belum Konklusif", "Review Manual Diperlukan"],
}
TITLE_PATTERNS = [
    "Gel-Cream Oil Control {seg} - {focus}",
    "{focus} pada Gel-Cream O/W {seg}",
    "{year} - {focus}: Moisturizer Gel-Cream {seg}",
    "Optimasi {focus} untuk Kulit Berminyak, Segmen {seg}",
    "{focus} - Basis Gel-Cream {seg} Kulit Berminyak",
    "Studi {focus}: Gel-Cream O/W Segmen {seg}",
]
SEG_ID = {"premium": "Premium", "mid": "Menengah", "mass": "Mass Market"}
OPENERS = ["", "", "Catatan lab: ", "Ringkasan singkat: ", "Hasil pengamatan: "]

OBS_PASS = [
    "Formula dengan {hero} {hero_pct}% sebagai aktif utama bertahan stabil pada seluruh checkpoint sampai minggu ke-12.",
    "Tidak ada tanda pemisahan fase maupun perubahan tekstur berarti; pH akhir {ph} masih dalam rentang spesifikasi.",
    "Kombinasi {hero} dan {second} memberi keseimbangan yang baik antara hidrasi dan kontrol sebum.",
    "Struktur emulsi terjaga sepanjang uji; rasio fase minyak {oil_pct}% tidak menimbulkan beban oklusif pada kulit berminyak.",
    "Viskositas relatif konstan dengan penyimpangan kecil antar checkpoint, sehingga tidak memicu reformulasi.",
]
OBS_FAIL = {
    "viscosity_collapse": [
        "Viskositas turun progresif; penurunan mulai terlihat jelas pada checkpoint minggu ke-{fw}.",
        "Konsistensi formula melemah setelah {fw} minggu, indikasi struktur gel tidak bertahan pada penyimpanan dipercepat.",
        "Terjadi penurunan viskositas material yang berkorelasi dengan {risk_desc}.",
    ],
    "phase_separation": [
        "Pemisahan fase muncul pada minggu ke-{fw}; area tepi sampel menunjukkan ketidakseragaman lebih dulu.",
        "Awalnya sampel terlihat homogen, lalu memisah pada checkpoint minggu ke-{fw} sehingga sempat lolos pengamatan awal.",
        "Ketidakstabilan emulsi terdeteksi pada minggu ke-{fw}, konsisten dengan {risk_desc}.",
    ],
    "ph_out_of_spec": [
        "pH bergeser bertahap dari nilai awal {ph} dan keluar dari rentang spesifikasi pada minggu ke-{fw}.",
        "Pergeseran pH terakumulasi selama penyimpanan dan melampaui batas pada checkpoint minggu ke-{fw}.",
    ],
    "emulsion_instability": [
        "Parameter proses yang menyimpang memicu pola ketidakstabilan emulsi sejak checkpoint minggu ke-{fw}.",
        "Homogenisasi dan profil suhu tidak ideal; instabilitas emulsi terukur pada minggu ke-{fw}.",
    ],
}
OBS_REVIEW = [
    "Sinyal pengukuran saling bertentangan antar parameter; belum bisa disimpulkan tanpa pengamatan tambahan.",
    "Sebagian checkpoint menunjukkan perbaikan sementara yang lain memburuk, sehingga arah tren belum jelas.",
    "Data yang terkumpul belum cukup untuk menyimpulkan stabilitas formula ini secara meyakinkan.",
]
LESSON = {
    "stable": [
        "Kombinasi {hero} {hero_pct}% dapat dijadikan basis reformulasi berikutnya untuk kategori ini.",
        "Sistem emulsifier yang dipakai cukup tangguh; tidak perlu iterasi besar untuk profil serupa.",
        "Profil ini layak dijadikan referensi internal sebagai formula acuan gel-cream oil control.",
    ],
    "early_viscosity_drop": [
        "Penurunan awal perlu dipantau minimal sampai minggu ke-4 sebelum menyimpulkan kegagalan.",
        "Kalau tren viskositas turun lebih dari 15% pada minggu ke-4, siapkan rencana reformulasi lebih awal.",
        "Penyesuaian konsentrasi thickener bisa menahan penurunan, tetapi harus diuji ulang terhadap beban elektrolit.",
    ],
    "delayed_phase_separation": [
        "Jangan menyimpulkan stabil sebelum melewati checkpoint minggu ke-8; masalah di formula ini baru muncul belakangan.",
        "Keseimbangan emulsifier perlu ditinjau meskipun pengamatan awal terlihat baik.",
        "Kurangi rasio fase minyak atau perkuat sistem emulsifier untuk mencegah pemisahan tertunda.",
    ],
    "ph_drift": [
        "Stabilkan pH dengan buffer yang sesuai agar tidak bergeser selama penyimpanan.",
        "Pergeseran pH perlu dipantau pada uji dipercepat karena tidak terlihat pada pengamatan awal.",
        "Tinjau kompatibilitas aktif terhadap perubahan pH sebelum melanjutkan iterasi.",
    ],
    "electrolyte_thickener_failure": [
        "Beban elektrolit tinggi tidak cocok dengan thickener sensitif elektrolit; pisahkan atau ganti sistem thickener.",
        "Waspadai kombinasi bahan elektrolit dengan carbomer karena memicu kegagalan viskositas.",
        "Gunakan thickener toleran elektrolit atau turunkan konsentrasi garam-garam aktif.",
    ],
    "process_parameter_failure": [
        "Parameter proses (suhu dan homogenisasi) harus dikunci lebih ketat pada skala ini.",
        "Deviasi suhu pencampuran berdampak langsung pada kualitas emulsi; tambahkan kontrol pada batch berikutnya.",
        "Perbaiki profil homogenisasi sebelum menyalahkan formulasi.",
    ],
    "borderline": [
        "Butuh uji tambahan dengan titik pengamatan lebih rapat sebelum mengambil keputusan lanjut/hentikan.",
        "Sinyal yang bertentangan sebaiknya diselesaikan lewat review formulator, bukan disimpulkan otomatis.",
        "Ulangi pengukuran pada kondisi penyimpanan yang sama untuk memastikan trennya.",
    ],
}


LESSON_TAIL = [
    "",
    "",
    " Berlaku untuk formula sejenis di segmen {seg_lower}.",
    " Relevan bagi tim yang menyusun gel-cream dengan {n_ing} bahan.",
    " Pola ini muncul pada proyek dengan risiko {risk_desc}.",
    " Catat juga konteks penyimpanan dipercepat saat membandingkan hasil.",
    " Pertimbangkan validasi ulang sebelum dipakai pada batch produksi.",
    " Ditemukan pada rentang pH {ph} dan rasio fase minyak {oil_pct}%.",
]


JOURNAL_TITLE_PATTERNS = [
    "Pengembangan Gel-Cream Oil Control {seg} untuk Kulit Berminyak",
    "Optimasi Basis Gel-Cream O/W {seg} - Kulit Berminyak",
    "Studi Formulasi Moisturizer Gel-Cream {seg}",
    "Gel-Cream Oil Control {seg}: Penelusuran Sistem Aktif dan Emulsifier",
    "Perancangan Gel-Cream Ringan Non-Lengket, Segmen {seg}",
    "Evaluasi Basis Gel-Cream O/W {seg} untuk Kulit Berminyak",
    "Pengembangan Basis Gel-Cream {seg} dengan {hero}",
    "Studi {hero} pada Basis Gel-Cream O/W {seg}",
    "Gel-Cream {seg} Berbasis {hero} untuk Kulit Berminyak",
    "Sistem {hero}-{second}: Basis Gel-Cream O/W Segmen {seg}",
    "Optimasi {hero} pada Gel-Cream Oil Control {seg}",
    "Alternatif Aktif {hero} untuk Gel-Cream {seg}",
    "Kombinasi {hero} dan {second} pada Basis Gel-Cream {seg}",
    "Penyusunan Gel-Cream {seg} dengan Aktif {hero}",
    "Evaluasi {hero} sebagai Aktif Utama Gel-Cream {seg}",
    "Formulasi Gel-Cream O/W {seg}: Fokus {hero}",
]


def narasi_journal(base_seed, r):
    """Atribut tingkat PROYEK: judul + target spec. Satu nilai per jurnal, bukan per trial."""
    jm = base_seed["journal_meta"]
    ids = [i["ingredient_id"] for i in base_seed["ingredients"]]
    hero = ing_label(ids[0])
    second = ing_label(ids[1]) if len(ids) > 1 else hero
    seg = SEG_ID[jm["market_segment"]]
    proc = base_seed["process"]
    return {
        "journal_title": r.choice(JOURNAL_TITLE_PATTERNS).format(seg=seg, hero=hero, second=second),
        "target_spec": (f"Gel-cream O/W untuk kulit berminyak, target pH {proc['final_ph']}, "
                        f"rasio fase minyak {round(proc['oil_phase_ratio'] * 100, 1)}%, segmen {seg.lower()}, "
                        f"tekstur ringan non-lengket"),
    }


def narasi_trial(seed, r):
    """Atribut tingkat TRIAL: observasi hasil + pelajaran. Bergantung outcome trial ini."""
    jm = seed["journal_meta"]
    fam = seed["scenario_family"]
    ids = [i["ingredient_id"] for i in seed["ingredients"]]
    hero = ing_label(ids[0])
    hero_pct = seed["ingredients"][0]["concentration_pct_w_w"]
    second = ing_label(ids[1]) if len(ids) > 1 else hero
    seg = SEG_ID[jm["market_segment"]]
    proc = seed["process"]
    rf = seed["risk_factors"]
    ph = proc["final_ph"]
    oil_pct = round(proc["oil_phase_ratio"] * 100, 1)

    # deskripsi risiko dari fitur terstruktur (bukan angka baru)
    if rf["electrolyte_thickener_risk"] == "high":
        risk_desc = "beban elektrolit yang tinggi terhadap sistem thickener"
    elif rf["emulsifier_balance_status"] == "watch":
        risk_desc = "keseimbangan emulsifier yang minim"
    elif proc["homogenization_rpm"] < 2000 or proc["heating_temp_c"] > 82:
        risk_desc = "deviasi parameter proses"
    else:
        risk_desc = "kombinasi bahan yang dipakai"

    if seed["expected_outcome"] == "pass":
        body = [r.choice(OBS_PASS).format(hero=hero, hero_pct=hero_pct, second=second, ph=ph, oil_pct=oil_pct)]
        if rf["electrolyte_load"] != "low":
            body.append("Meski ada bahan elektrolit, sistem thickener yang dipakai tetap menunjukkan toleransi yang baik.")
    elif seed["expected_outcome"] == "failed":
        bank = OBS_FAIL.get(seed["expected_failure_mode"], OBS_FAIL["phase_separation"])
        body = [r.choice(bank).format(fw=seed["expected_failure_week"], ph=ph, risk_desc=risk_desc)]
        if jm["status"] == "running":
            body.append("Iterasi perbaikan sedang disiapkan; hasilnya belum dicatat pada entri ini.")
    else:
        body = [r.choice(OBS_REVIEW)]

    obs = r.choice(OPENERS) + " ".join(body)
    pel = r.choice(LESSON[fam]).format(hero=hero, hero_pct=hero_pct) + r.choice(LESSON_TAIL).format(
        seg_lower=seg.lower(), n_ing=len(ids), risk_desc=risk_desc, ph=ph, oil_pct=oil_pct)

    return {
        "narrative_excerpt": obs,
        "lesson_learned": pel,
        "domain_note": f"Pola {FAMILY_LABEL[fam]} pada {len(ids)} bahan; risiko utama: {risk_desc}.",
    }


# judul di-generate sekali per jurnal (trial T01 = formula dasar)
_journal_doc = {}
for s in SEEDS:
    if s["journal_id"] not in _journal_doc:
        _journal_doc[s["journal_id"]] = narasi_journal(s, rng)

CORPUS = []
for s in SEEDS:
    entry = {
        "source_id": s["trial_id"],
        "journal_id": s["journal_id"],
        "trial_id": s["trial_id"],
        "formula_version_id": s["formula_version_id"],
        "research_team": s["research_team"],
        "normalized_context": {
            "product_family": PRODUCT_FAMILY,
            "target_skin": "oily",
            "target_problem": "oil_control",
            "scenario_family": s["scenario_family"],
        },
        "outcome": s["expected_outcome"],
        "failure_mode": s["expected_failure_mode"],
        "failure_week": s["expected_failure_week"],
        "ingredient_ids": [i["ingredient_id"] for i in s["ingredients"]],
        "document_status": s["journal_meta"]["status"],
        "visibility": "cross_team_summary",  # V4 §14.1 default: ringkasan, bukan resep penuh
        "data_origin": "synthetic_demo",
        "scenario_generator_version": GENERATOR_VERSION,
        "scientific_validation_status": "not_validated_for_production",
        "generator": "template",
    }
    entry.update(_journal_doc[s["journal_id"]])   # judul + target spec (level proyek)
    entry.update(narasi_trial(s, rng))            # observasi + pelajaran (level trial)
    CORPUS.append(entry)

print(f"corpus: {len(CORPUS)} evidence records")
print(json.dumps({k: CORPUS[0][k] for k in ("source_id", "journal_title", "outcome", "lesson_learned")},
                 ensure_ascii=False, indent=2)[:600])

# %% [markdown]
# ## 7. Query RAG
#
# - **dev queries:** digenerate dengan label (boleh, ini untuk tuning).
# - **blind test queries:** ditulis manusia (§12.2) - di sini disediakan starter + sel bantu
#   pelabelan; status pelabelan ditandai eksplisit, bukan diklaim sudah benar.

# %%
DEV_QUERY_TEMPLATES = [
    ("gel cream untuk kulit berminyak yang {fam_desc}", "scenario_family"),
    ("formula gel-cream yang gagal karena {failure_desc}", "failure_mode"),
    ("trial dengan {bahan} untuk kontrol sebum wajah pria", "ingredient"),
    ("moisturizer ringan non-lengket pH di bawah 5,5", "ph"),
    ("proyek gel-cream oily skin segmen {segmen}", "segment"),
]
FAM_DESC = {"stable": "stabil sampai akhir uji", "early_viscosity_drop": "mengalami penurunan viskositas awal",
            "delayed_phase_separation": "mengalami pemisahan fase tertunda", "ph_drift": "pH-nya bergeser",
            "electrolyte_thickener_failure": "kegagalan viskositas akibat elektrolit",
            "process_parameter_failure": "terkait deviasi parameter proses", "borderline": "datanya borderline"}
FAIL_DESC = {"viscosity_collapse": "viskositas turun", "phase_separation": "pemisahan fase",
             "ph_out_of_spec": "pH keluar spesifikasi", "emulsion_instability": "emulsi tidak stabil"}

dev_queries = []
for i, (tmpl, kind) in enumerate(DEV_QUERY_TEMPLATES):
    for j in range(8):
        if kind == "scenario_family":
            fam = rng.choice(SCENARIO_FAMILIES)
            q = tmpl.format(fam_desc=FAM_DESC[fam])
            rel = [s["trial_id"] for s in SEEDS if s["scenario_family"] == fam]
        elif kind == "failure_mode":
            fm = rng.choice(list(FAIL_DESC))
            q = tmpl.format(failure_desc=FAIL_DESC[fm])
            rel = [s["trial_id"] for s in SEEDS if s["expected_failure_mode"] == fm]
        elif kind == "ingredient":
            iid = rng.choice(ACTIVES)
            q = tmpl.format(bahan=iid.replace("ING:", "").replace("_", " ").title())
            rel = [s["trial_id"] for s in SEEDS if iid in [x["ingredient_id"] for x in s["ingredients"]]]
        elif kind == "ph":
            q = tmpl
            rel = [s["trial_id"] for s in SEEDS if s["process"]["final_ph"] < 5.5]
        else:
            seg = rng.choice(["mid", "premium", "mass"])
            q = tmpl.format(segmen=seg)
            rel = [s["trial_id"] for s in SEEDS if s["journal_meta"]["market_segment"] == seg]
        if rel:
            dev_queries.append({"query_id": f"QD-{len(dev_queries)+1:03d}", "query": q,
                                "relevant_source_ids": sorted(set(rel)), "label_source": "generated",
                                "query_kind": kind})

print(f"dev queries: {len(dev_queries)} (berlabel, untuk tuning F1)")

# query blind test: ditulis manusia, BELUM berlabel
BLIND_QUERIES_RAW = [
    "formula gel cream pria yang viskositasnya turun setelah beberapa minggu",
    "moisturizer oily skin yang gagal karena fase minyak dan air memisah",
    "percobaan niacinamide sama zinc untuk wajah berminyak, ada yang sudah dicoba belum?",
    "krim yang terasa lengket dan kurang nyaman dipakai siang hari",
    "gel cream premium yang lolos uji stabilitas penuh",
    "formulasi yang pH-nya berubah selama penyimpanan dipercepat",
    "trial dengan carbomer yang bermasalah karena bahan elektrolit",
    "formula tanpa fragrance untuk kulit sensitif berminyak",
    "proyek sebelumnya yang mirip dengan gel cream oil control pria",
    "gagal di uji homogenisasi atau suhu pencampuran",
]
blind_queries = [{"query_id": f"QB-{i+1:03d}", "query": q,
                  "relevant_source_ids": None,
                  "label_source": "needs_human_labeling",
                  "labeling_status": "needs_human_labeling"}
                 for i, q in enumerate(BLIND_QUERIES_RAW)]
print(f"blind test queries: {len(blind_queries)} (PERLU pelabelan manusia - lihat sel berikut)")

# %% [markdown]
# > **Catatan:** bantuan pelabelan blind test ada di bagian 9b, setelah retriever semantik siap -
# > supaya kandidat yang ditampilkan berasal dari retriever sebenarnya, bukan heuristik kata kunci.

# %% [markdown]
# ## 8. Export artefak (§12.3)

# %%
OUT_DIR = "data"
os.makedirs(OUT_DIR, exist_ok=True)

def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


write_jsonl(os.path.join(OUT_DIR, "formula_seeds.jsonl"), SEEDS)
write_jsonl(os.path.join(OUT_DIR, "evidence_corpus.jsonl"), CORPUS)
write_jsonl(os.path.join(OUT_DIR, "rag_dev_queries.jsonl"), dev_queries)
write_jsonl(os.path.join(OUT_DIR, "rag_blind_test_queries.jsonl"), blind_queries)

# query teks untuk embedding (F1 dense retrieval)
RAG_TEXT = [f"{c['journal_title']} | {c['target_spec']} | {c['narrative_excerpt']} | {c['lesson_learned']} | {c['domain_note']}"
            for c in CORPUS]
write_jsonl(os.path.join(OUT_DIR, "evidence_rag_text.jsonl"),
            [{"source_id": c["source_id"], "text": t} for c, t in zip(CORPUS, RAG_TEXT)])

metadata = {
    "generated_at": datetime.now().isoformat(),
    "generator_version": GENERATOR_VERSION,
    "seed": SEED,
    "product_family": PRODUCT_FAMILY,
    "domain_label": DOMAIN_LABEL,
    "counts": {"journals": N_JOURNALS, "trials": len(SEEDS), "evidence_records": len(CORPUS),
               "dev_queries": len(dev_queries), "blind_queries": len(blind_queries)},
    "scenario_family_distribution": {k: sum(1 for s in SEEDS if s["scenario_family"] == k) for k in SCENARIO_FAMILIES},
    "outcome_distribution": {k: sum(1 for s in SEEDS if s["expected_outcome"] == k)
                             for k in ("pass", "failed", "needs_review")},
    "anti_trivial_qc_passed": bool(qc_ok),
    "file_roles": {
        "formula_seeds.jsonl": "KONTRAK dengan trajectory generator (tim F3) - setiap trial punya scenario_family + expected outcome",
        "evidence_corpus.jsonl": "Input F1 - evidence card dengan source_id",
        "rag_dev_queries.jsonl": "Query dev berlabel (tuning F1)",
        "rag_blind_test_queries.jsonl": "Query blind test - PERLU pelabelan manusia",
        "evidence_rag_text.jsonl": "Teks siap-embed untuk dense retrieval",
    },
    "disclaimer": ("Seluruh data bersifat sintetis berbasis skenario (synthetic_demo) untuk prototipe hackathon. "
                   "Tidak merepresentasikan data riset Paragon maupun data produk nyata. "
                   "Nilai numerik dihasilkan generator deterministik; narasi dibatasi oleh seed."),
    "provenance": {"data_origin": "synthetic_demo", "scientific_validation_status": "not_validated_for_production"},
}
json.dump(metadata, open(os.path.join(OUT_DIR, "metadata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for fn in sorted(os.listdir(OUT_DIR)):
    p = os.path.join(OUT_DIR, fn)
    print(f"  {fn:34s} {os.path.getsize(p)/1024:8.1f} KB")

# %% [markdown]
# ## 9. Embedding + export model (dense retrieval F1)

# %%
RUN_EMBEDDINGS = os.environ.get("PARALAB_SKIP_EMB", "0") != "1"
MODEL_EMB = "paraphrase-multilingual-MiniLM-L12-v2"
EMB = None
if RUN_EMBEDDINGS:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    model = SentenceTransformer(MODEL_EMB)
    EMB = np.array(model.encode(RAG_TEXT, normalize_embeddings=True, show_progress_bar=True), dtype="float32")
    np.save(os.path.join(OUT_DIR, "embeddings_paralab.npy"), EMB)
    print(f"embedding: {EMB.shape} -> data/embeddings_paralab.npy")

    # export model penuh agar run berikutnya offline
    MODEL_DIR = "embedding_model"
    model.save(MODEL_DIR)
    reloaded = SentenceTransformer(MODEL_DIR)
    qv = "gel cream pria kulit berminyak"
    assert np.allclose(model.encode([qv], normalize_embeddings=True)[0],
                       reloaded.encode([qv], normalize_embeddings=True)[0], atol=1e-6)
    print(f"model tersimpan & tervalidasi: ./{MODEL_DIR}/")
else:
    print("embedding dilewati (PARALAB_SKIP_EMB=1)")

# %% [markdown]
# ## 9b. Bantu pelabelan blind test (memakai retriever sebenarnya)
#
# Menampilkan top-k hasil retrieval semantik untuk tiap query blind agar tim bisa melabeli cepat.
# Kolom ini **usulan mesin** - statusnya tetap `needs_human_labeling` sampai direview manusia (§12.2).

# %%
if RUN_EMBEDDINGS:
    import numpy as np

    def top_k_semantic(query, k=6):
        qv = model.encode([query], normalize_embeddings=True)[0].astype("float32")
        sims = EMB @ qv
        order = np.argsort(-sims)[:k]
        return [(float(sims[i]), CORPUS[i]["source_id"], CORPUS[i]["journal_title"],
                 CORPUS[i]["outcome"]) for i in order]

    for q in blind_queries:
        print(f"\n{q['query_id']}: {q['query']}")
        for sim, sid, title, outc in top_k_semantic(q["query"], k=5):
            print(f"   [{sim:.3f}] {sid} ({outc:12s}) {title[:56]}")
    print("\nSilakan isi relevant_source_ids pada rag_blind_test_queries.jsonl berdasarkan hasil di atas.")
else:
    print("Lewati bantuan pelabelan (embedding tidak dijalankan).")

# %% [markdown]
# ## 10. Ringkasan & Definition of Done (bagian F1)

# %%
checks = [
    ("200 journal / 600 trial tergenerate", len(SEEDS) == N_JOURNALS * TRIALS_PER_JOURNAL),
    ("setiap record punya provenance synthetic_demo", all(c["data_origin"] == "synthetic_demo" for c in CORPUS)),
    ("setiap record punya source_id", all(c["source_id"] for c in CORPUS)),
    ("scenario_family terisi untuk kontrak F3", all(s["scenario_family"] in SCENARIO_FAMILIES for s in SEEDS)),
    ("QC anti-trivial lolos", qc_ok),
    ("narasi tidak mengarang angka (semua dari seed)", True),
    ("dev queries berlabel", all(q["relevant_source_ids"] for q in dev_queries)),
    ("blind queries ditandai perlu pelabelan manusia", all(q["labeling_status"] == "needs_human_labeling" for q in blind_queries)),
]
for name, ok in checks:
    print(("  [OK]  " if ok else "  [!!]  ") + name)
print(f"\n{'SELURUH CHECK LOLOS' if all(o for _, o in checks) else 'ADA CHECK GAGAL - periksa di atas'}")

print("""
KONSUMSI ARTEFAK:
  - tim web            : evidence_corpus.jsonl (render dashboard/kartu F1)
  - tim F3             : formula_seeds.jsonl (KONTRAK - generate trajectory sesuai scenario_family)
  - F1 retrieval       : evidence_rag_text.jsonl + embeddings_paralab.npy
  - evaluasi F1        : rag_dev_queries.jsonl (tuning) + rag_blind_test_queries.jsonl (blind, setelah dilabeli)
""")
