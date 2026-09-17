# ParaLab AI: Arsitektur v4

> **ARSIP HISTORIS:** dokumen ini telah digantikan oleh [Architecture v5](../../architecture/architecture_v5.md). Jangan gunakan sebagai panduan implementasi aktif.

> **Status:** cetak biru implementasi prototipe hackathon  
> **Menggantikan:** `architecture_v3.md` untuk keputusan scope MVP dan aliran data
> **Mempertahankan:** prinsip v3, yaitu inferensi local-first, RAG berbasis evidence, guardrail deterministik, kontrol akses sebelum retrieval, human sign-off, dan output yang dapat diaudit.

---

## 1. Keputusan Produk

### 1.1 Domain MVP

MVP memvalidasi satu vertical yang konsisten:

> **Moisturizer gel-cream oil-in-water untuk kulit berminyak.**

Visi produk tetap mencakup kategori kosmetik yang lebih luas. Namun, prototipe tidak mengklaim dapat memodelkan seluruh kategori produk. Satu keluarga formulasi membuat F1, F2, F3, F5, knowledge pool, dan dataset memakai ontology yang sama.

### 1.2 Posisi produk

ParaLab AI bukan pengganti Smart Lab. ParaLab adalah lapisan evidence, guardrail, dan memori eksperimen yang menghadap langsung kepada peneliti dan dapat diintegrasikan ke workflow Smart Lab.

> **ParaLab mengubah jurnal lab menjadi co-pilot berbasis evidence: menemukan eksperimen terdahulu, menangkap risiko formula yang sudah dikenal, memantau sinyal stabilitas awal, dan menjaga pembelajaran dari setiap trial.**

### 1.3 Siklus pengguna utama

```text
Brief riset
  → F1 mencari evidence dan trial serupa
  → peneliti menyusun formula
  → F2 menormalisasi bahan dan menerapkan guardrail yang dapat diaudit
  → peneliti menjalankan trial dan mencatat checkpoint
  → F3 memprediksi risiko gagal jangka panjang dari tren awal
  → F1 mengambil pola kegagalan historis untuk menjelaskan prediksi
  → peneliti memutuskan lanjut, reformulasi, atau review
  → outcome terverifikasi menjadi evidence jurnal berikutnya
```

### 1.4 Keputusan scope

| Prioritas | Modul | Peran MVP |
|---|---|---|
| P0 | F1: Copilot Evidence Riset | Hybrid RAG dengan sitasi dan abstention |
| P0 | F2: Guardrail Formulasi | Screening bahan dan rule deterministik |
| P0 | F3: Predictive Stability Sentinel | Forecast risiko awal dari data longitudinal |
| P0 | F5: Voice-to-Structured Logging | Pencatatan lab cepat yang wajib dikonfirmasi |
| P1 | Upload gambar F3 | Lampiran evidence dan quality check gambar saja |
| P2 | Classifier CV ketidakstabilan | Ditunda sampai memperoleh dataset gambar berlabel yang sesuai |
| P2 | Active learning / next-best experiment | Roadmap setelah ada trajectory stability historis nyata |

---

## 2. Prinsip yang Tidak Dapat Ditawar

1. **Satu schema jurnal kanonis.** Modul bertukar field terstruktur, bukan teks bebas.
2. **F1 mengambil evidence.** Narasi F1 tidak menjadi fitur numerik tanpa validasi bagi F3.
3. **F2 menghasilkan input ternormalisasi dan fitur dari guardrail.** F2 tidak memprediksi kebenaran ilmiah.
4. **F3 membuat forecast dari formula, proses, dan tren checkpoint aktual.** F3 harus menyatakan status coverage domainnya.
5. **Evidence RAG menjelaskan forecast setelah forecast dibuat.** RAG tidak menggantikan model prediktif secara diam-diam.
6. **Data sintetis membuktikan integrasi dan workflow, bukan performa ilmiah.** Semua record sintetis diberi label jelas.
7. **Teacher LLM hanya boleh menghasilkan narasi dari seed terkontrol.** LLM tidak boleh mengarang trajectory numerik, measurement, atau label.
8. **Setiap klaim dapat ditelusuri.** Rule version, source ID, model version, confidence, dan status review manusia disimpan.
9. **Sistem boleh abstain.** Domain tidak didukung, observasi kurang, atau evidence bertentangan harus menghasilkan limitation eksplisit.
10. **Human sign-off wajib.** Tidak ada output AI yang otomatis memfinalkan formula, observasi, atau keputusan compliance.

---

## 3. Arsitektur Logis

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                         RESEARCHER WORKSPACE                               │
│ Dashboard · Editor Jurnal · Tabel Formula · Timeline Stabilitas · Voice UI │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │ API terautentikasi
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     BACKEND MODULAR PARALAB                                │
│                                                                            │
│ ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐ │
│ │ Journal API │  │ Access/Audit │  │ Ingest/Index   │  │ Model Adapter  │ │
│ │ data kanonis│  │ ACL/proven.  │  │ background job │  │ runtime lokal  │ │
│ └──────┬──────┘  └──────┬───────┘  └──────┬─────────┘  └──────┬─────────┘ │
│        │                │                 │                   │           │
│ ┌──────▼──────┐ ┌───────▼──────┐ ┌────────▼─────────┐ ┌──────▼─────────┐ │
│ │ F1 Evidence │ │ F2 Guardrail │ │ F3 Stability     │ │ F5 Voice       │ │
│ │ Hybrid RAG  │ │ Rule Engine  │ │ Sentinel          │ │ Structuring    │ │
│ └──────┬──────┘ └───────┬──────┘ └────────┬─────────┘ └──────┬─────────┘ │
│        └────────────────┴──────────────────┴──────────────────┘           │
│                                  │                                         │
│            validasi schema · coverage gate · explanation layer             │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              LAPISAN DATA                                  │
│ DB jurnal kanonis · KB bahan · KB aturan · corpus evidence · audit event   │
│ Index turunan: full-text · vector · feature snapshot model                 │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Keputusan deployment

Gunakan modular monolith untuk hackathon:

- frontend web dengan framework yang dikuasai tim;
- satu backend Python untuk API, ML, dan background job;
- PostgreSQL untuk record kanonis;
- PostgreSQL full-text search plus pgvector untuk retrieval MVP;
- object storage lokal atau S3-compatible untuk audio/gambar yang diizinkan;
- adapter untuk embedding, reranker, LLM, STT, dan model F3.

Microservices secara eksplisit di luar scope.

---

## 4. Ontology Kanonis

### 4.1 Identitas bahan

Setiap bahan memiliki internal ID yang stabil. Alias, nama supplier, dan variasi ejaan dipetakan ke ID tersebut.

```json
{
  "ingredient_id": "ING:NIACINAMIDE",
  "inci_name": "Niacinamide",
  "display_name": "Niacinamide",
  "aliases": ["niasinamida", "vitamin b3", "nicotinamide"],
  "functional_classes": ["active", "sebum_regulator"],
  "phase_compatibility": ["water"],
  "source_ids": ["INGREF-001"]
}
```

### 4.2 Formula snapshot

Formula snapshot tidak dapat diubah setelah disimpan. Setiap perubahan membuat versi baru.

```json
{
  "formula_version_id": "FORM-2026-001-V2",
  "journal_id": "J-2026-001",
  "product_family": "o_w_gel_cream_moisturizer",
  "ingredients": [
    {
      "ingredient_id": "ING:NIACINAMIDE",
      "concentration_pct_w_w": 5.0,
      "phase": "water"
    }
  ],
  "process": {
    "heating_temp_c": 75,
    "homogenization_rpm": 2500,
    "mixing_time_min": 15,
    "cooling_profile": "ambient_agitation",
    "final_ph": 5.7
  },
  "created_at": "ISO-8601"
}
```

### 4.3 Stability checkpoint

```json
{
  "checkpoint_id": "CHK-J-2026-001-T02-W4",
  "trial_id": "J-2026-001-T02",
  "week": 4,
  "storage_condition": {
    "temperature_c": 40,
    "humidity_pct": null
  },
  "measurements": {
    "ph": 5.93,
    "viscosity_cp": 12100,
    "color_delta_e": null
  },
  "observations": {
    "appearance": "slightly_nonuniform",
    "odor": "normal",
    "centrifuge_result": "not_tested",
    "freeze_thaw_result": "not_tested"
  },
  "capture_quality": "acceptable",
  "human_verified": true
}
```

### 4.4 Outcome final

```json
{
  "trial_id": "J-2026-001-T02",
  "final_status": "failed",
  "final_observation_week": 8,
  "failure_mode": "viscosity_collapse",
  "human_verified": true,
  "reviewer_role": "formulator"
}
```

---

## 5. Knowledge Pool

Knowledge pool bukan satu database campur-aduk. Setiap record memiliki source type, domain, quality state, visibility level, dan limitation.

```text
Knowledge Pool
├── ingredient_master
│   ├── INCI kanonis dan alias
│   ├── functional class serta metadata formulasi
│   └── source dan version metadata
├── formulation_rule_base
│   ├── compatibility rules
│   ├── pH dan concentration constraints
│   ├── allergen serta regulatory screening reference
│   └── supplier-document / verification status
├── evidence_corpus
│   ├── jurnal moisturizer sintetis terstruktur
│   ├── ringkasan dataset formulasi publik
│   ├── referensi ilmiah publik
│   └── source metadata yang disetujui
├── stability_dataset
│   ├── formula/process seed sintetis
│   ├── trajectory checkpoint numerik
│   ├── final outcome label terverifikasi skenario
│   └── provenance skenario
├── model_registry
│   ├── feature schema F3
│   ├── model version dan training provenance
│   └── metric serta domain coverage
└── journal_store
    ├── record jurnal/trial pengguna
    ├── output AI tersimpan
    └── audit event
```

### 5.1 Penggunaan data publik

Data publik digunakan hanya untuk peran yang didukungnya.

| Kelas sumber | Penggunaan yang benar |
|---|---|
| Referensi INCI dan bahan | Nama kanonis, alias, functional metadata |
| Regulatory reference | Sumber guardrail prototipe yang versioned dan direview manusia |
| Dataset formulasi publik | Referensi metodologi, feature inspiration, evidence corpus bila domain sesuai |
| Shampoo Formulations Dataset | Referensi pola formulation ML, bukan data training model moisturizer |
| Dataset mAb longitudinal | Referensi metodologi forecast awal-ke-akhir, bukan data training kosmetik |
| Data moisturizer sintetis | Training demo dan validasi workflow saja |

Tidak ada sumber publik yang disamarkan sebagai data Paragon.

---

## 6. Dataset Longitudinal Sintetis

### 6.1 Tujuan

Dataset sintetis membuktikan integrasi retrieval, rules, forecasting, voice capture, dan auditability. Dataset ini tidak membuktikan bahwa model prediktif telah tervalidasi secara ilmiah untuk produksi.

Setiap record memiliki:

```json
{
  "data_origin": "synthetic_demo",
  "scenario_generator_version": "v1",
  "scientific_validation_status": "not_validated_for_production"
}
```

### 6.2 Ukuran dataset

| Entitas | Jumlah |
|---|---:|
| Journal project | 200 |
| Trial per project | 3 |
| Total trial | 600 |
| Checkpoint per trial | 7: minggu 0, 1, 2, 4, 6, 8, 12 |
| Total checkpoint record | 4.200 |

### 6.3 Scenario family

Setiap trial seed berada dalam satu trajectory family terkontrol.

| Scenario family | Outcome yang dituju |
|---|---|
| `stable` | Lulus sampai minggu ke-12 |
| `early_viscosity_drop` | Penurunan awal yang dapat pulih atau gagal kemudian |
| `delayed_phase_separation` | Terlihat baik pada awal, gagal setelah checkpoint menengah |
| `ph_drift` | Pergeseran pH bertahap yang terhubung ke risk condition |
| `electrolyte_thickener_failure` | Elektrolit tinggi dan thickener sensitif memicu kegagalan viskositas |
| `process_parameter_failure` | Proses mixing/heating tidak ideal memicu pola instability |
| `borderline` | Evidence belum cukup, human review lebih tepat |

Distribusi harus mencakup trial stabil dan gagal. Generator harus menghindari pola trivial ketika satu feature langsung menentukan final label dengan sempurna.

### 6.4 Numeric trajectory generator

Generator deterministik atau seeded stochastic membuat field numerik.

```text
Seed formula + proses terstruktur
  → assignment skenario
  → latent risk factor
  → baseline pH dan viskositas
  → drift/noise per checkpoint
  → transition status observasi
  → final outcome dan failure week
```

Contoh hubungan konseptual:

```text
electrolyte load tinggi
+ thickener sensitif elektrolit
+ negative viscosity slope pada checkpoint awal
→ probabilitas trajectory viscosity collapse meningkat
```

```text
process deviation
+ emulsifier balance tidak ideal
→ probabilitas delayed visual separation meningkat
```

Ini adalah asumsi demo, bukan hukum universal formulasi kosmetik.

### 6.5 Batas penggunaan LLM

Teacher LLM hanya boleh membuat:

- judul jurnal;
- phrasing observasi peneliti;
- teks lesson learned singkat;
- variasi query natural language;
- draft penjelasan yang dibatasi oleh value terstruktur.

Teacher LLM tidak boleh membuat:

- nilai pH;
- nilai viskositas;
- failure week;
- final label;
- concentration value;
- keputusan regulatory.

---

## 7. F1: Copilot Evidence Riset

### 7.1 Peran

F1 menemukan evidence trial historis, termasuk failure pattern, lalu menunjukkan evidence coverage. F1 tidak membuat stability forecast itu sendiri.

### 7.2 Pipeline retrieval

```text
Natural-language query
  → normalisasi product / ingredient / failure mode
  → access-control filter
  → lexical retrieval + dense retrieval + metadata filter paralel
  → reciprocal-rank fusion / reranking
  → evidence sufficiency gate
  → grounded summary dengan source card
```

### 7.3 Output F1 terstruktur

```json
{
  "query_id": "Q-2026-014",
  "normalized_context": {
    "product_family": "o_w_gel_cream_moisturizer",
    "target_skin": "oily",
    "target_problem": "oil_control",
    "failure_mode": "viscosity_collapse"
  },
  "evidence_status": "sufficient",
  "related_cases": [
    {
      "source_id": "J-2025-044-T02",
      "relevance": 0.89,
      "outcome": "failed",
      "failure_mode": "viscosity_collapse",
      "data_origin": "synthetic_demo"
    }
  ],
  "summary_for_user": "...",
  "limitations": [
    "Evidence demo menggunakan data sintetis berbasis skenario."
  ]
}
```

### 7.4 Aturan integrasi F1 ke F3

Source ID dan failure pattern dari F1 disimpan sebagai evidence reference. Prosa F1 dan raw relevance score tidak masuk ke feature vector numerik F3.

Aturan ini mencegah model prediktif bergantung pada perilaku RAG yang berubah-ubah atau mengalami leakage final outcome melalui retrieval.

### 7.5 Acceptance criteria F1

- Ingredient exact-match, alias, dan trial ID dapat diambil.
- Query natural-language yang diparafrase dapat menemukan evidence relevan pada top-5.
- Setiap klaim faktual memiliki evidence card/source ID.
- Evidence yang kurang memicu abstention.
- Evidence restricted tidak masuk candidate set atau prompt LLM.

---

## 8. F2: Guardrail Formulasi Deterministik

### 8.1 Peran

F2 memvalidasi input formula dan mengeluarkan feature snapshot stabil untuk F3. F2 bukan regulatory approval engine.

### 8.2 Pipeline

```text
Input bahan
  → alias / INCI normalization
  → validasi concentration dan schema
  → compatibility rules
  → pH / emulsifier / electrolyte checks
  → regulatory serta supplier-document screening
  → warning, action, feature snapshot, audit event
```

### 8.3 Kontrak output F2

```json
{
  "formula_version_id": "FORM-2026-001-V2",
  "feature_schema_version": "stability-sentinel-v1",
  "derived_features": {
    "oil_phase_ratio": 0.11,
    "electrolyte_load": "high",
    "thickener_sensitivity": "high",
    "emulsifier_balance_status": "watch",
    "ph_compatibility_margin": 0.3,
    "ingredient_count": 9,
    "compatibility_warning_count": 1
  },
  "guardrail_results": [
    {
      "rule_id": "COMPAT-017",
      "severity": "warning",
      "source_id": "RULESRC-012",
      "rule_version": "2026.09",
      "requires_human_review": true
    }
  ],
  "model_coverage": {
    "status": "supported_demo_domain",
    "reason": "Formula dapat dipetakan ke O/W gel-cream synthetic feature schema."
  }
}
```

### 8.4 Aturan integrasi F2 ke F3

Hanya formula/process feature kanonis dan derived feature deterministik yang masuk F3. Raw warning message tidak menjadi input feature. Feature schema wajib versioned dan harus identik antara training serta inference.

### 8.5 Status aman

| Status | Makna |
|---|---|
| `clear_for_current_screening` | Tidak ada prototype rule yang aktif, bukan final approval |
| `warning` | Ada risiko atau evidence gap |
| `blocked_by_rule` | Explicit prototype constraint dilanggar |
| `unknown` | Data kurang, human review wajib |

---

## 9. F3: Predictive Stability Sentinel

### 9.1 Janji produk

> **F3 memakai sinyal formula dan checkpoint awal untuk mengestimasi risiko batch gagal sebelum minggu ke-12. F3 memprioritaskan perhatian peneliti dan reformulasi lebih awal. F3 tidak menggantikan formal stability validation.**

### 9.2 Dua mode F3

#### Mode A: konteks risiko sebelum trial

Sebelum lab execution, F3 dapat menampilkan risk context dari F2.

```text
Risiko electrolyte-thickener tinggi terdeteksi.
Model belum dapat membuat long-horizon forecast sebelum checkpoint tersedia.
Aksi: catat baseline measurement dan jalankan stability test plan.
```

Ini belum berupa model probability.

#### Mode B: forecast risiko longitudinal

Setelah observasi cukup, F3 memprediksi:

```text
P(gagal pada atau sebelum minggu 12 | formula, proses, data sampai minggu saat ini)
```

Minimum input adalah baseline dan satu checkpoint setelah baseline. Forecast MVP terkuat memakai data sampai minggu ke-4.

### 9.3 Feature vector F3

```json
{
  "feature_schema_version": "stability-sentinel-v1",
  "formula_features": {
    "oil_phase_ratio": 0.11,
    "electrolyte_load": "high",
    "thickener_sensitivity": "high",
    "emulsifier_balance_status": "watch",
    "final_ph": 5.7
  },
  "process_features": {
    "heating_temp_c": 75,
    "homogenization_rpm": 2500,
    "mixing_time_min": 15
  },
  "trend_features_at_week_4": {
    "viscosity_baseline_cp": 15000,
    "viscosity_current_cp": 12100,
    "viscosity_change_pct": -19.33,
    "viscosity_slope_per_week": -725,
    "ph_baseline": 5.6,
    "ph_current": 5.93,
    "ph_change": 0.33,
    "appearance_warning_count": 1,
    "storage_temperature_c": 40
  }
}
```

### 9.4 Model MVP

Gunakan baseline tabular yang explainable sebelum deep time-series model:

1. Logistic Regression sebagai baseline;
2. Random Forest sebagai baseline;
3. XGBoost atau LightGBM sebagai candidate model;
4. calibration step jika probability ditampilkan;
5. SHAP atau feature contribution untuk menjelaskan model terpilih.

LSTM, GRU, TCN, dan Transformer tidak masuk MVP. Dataset hanya memiliki 600 trajectory skenario, sehingga engineered trend feature lebih sesuai dan lebih mudah dijelaskan.

### 9.5 Kontrak output F3

```json
{
  "trial_id": "J-2026-001-T02",
  "forecast_week": 4,
  "forecast_horizon": "week_12",
  "prediction_type": "synthetic_demo_early_risk_forecast",
  "failure_risk": 0.78,
  "risk_band": "high",
  "likely_failure_mode": "viscosity_collapse",
  "confidence": "medium",
  "key_signals": [
    {
      "feature": "viscosity_change_pct",
      "value": -19.33,
      "interpretation": "Viskositas turun material dari baseline."
    },
    {
      "feature": "electrolyte_thickener_risk",
      "value": "high",
      "source": "COMPAT-017"
    }
  ],
  "evidence_ids": ["J-2025-044-T02", "J-2025-102-T01"],
  "recommended_action": "Minta review formulator sebelum melanjutkan siklus uji berikutnya.",
  "limitations": [
    "Forecast dilatih dan dievaluasi menggunakan synthetic demo data berbasis skenario.",
    "Forecast tidak menggantikan formal stability validation."
  ],
  "model_version": "stability-sentinel-xgb-v1"
}
```

### 9.6 Batas tanggung jawab F1, F2, F3

```text
F2:
Menormalisasi formula dan menyatakan risk factor deterministik.

F3:
Membuat forecast risiko dari F2 feature serta observed checkpoint trend.

F1:
Mencari trial historis dan evidence card yang menjelaskan mengapa warning F3 perlu diperhatikan.
```

### 9.7 Fallback aman F3

| Kondisi | Perilaku |
|---|---|
| Tidak ada post-baseline checkpoint | Tampilkan test plan, tanpa forecast |
| Formula di luar domain | Tampilkan `unsupported_domain`, tanpa probability |
| Measurement kritis kosong | Tampilkan `insufficient_observation`, minta field yang kurang |
| Sinyal saling bertentangan | Turunkan confidence dan minta human review |
| Model tidak tersedia | Tampilkan trend delta deterministik dan evidence F1 saja |

---

## 10. F5: Voice-to-Structured Logging

### 10.1 Pipeline

```text
Push-to-talk audio
  → local speech-to-text
  → normalisasi nama bahan dan angka
  → structured extraction
  → validasi JSON/range
  → confidence per field
  → user confirmation
  → write jurnal dan audit event
```

### 10.2 Output F5 harus menargetkan field kanonis

```json
{
  "trial_id": "J-2026-001-T02",
  "proposed_checkpoint_patch": {
    "measurements": {
      "ph": 5.93,
      "viscosity_cp": 12100
    },
    "observations": {
      "appearance": "slightly_nonuniform"
    }
  },
  "field_confidence": {
    "ph": 0.97,
    "viscosity_cp": 0.91,
    "appearance": 0.78
  },
  "requires_confirmation": true
}
```

F5 tidak boleh menulis langsung ke F3. F5 memperbarui checkpoint kanonis setelah user confirmation. F3 berjalan hanya jika checkpoint valid.

---

## 11. F_CV: Visual Screening sebagai Asisten Capture untuk F3

### 11.1 Peran

F_CV bukan classifier yang menghasilkan keputusan final. Perannya mempercepat capture checkpoint visual: peneliti memfoto sampel, model mengusulkan label appearance beserta confidence, peneliti mengonfirmasi atau mengoreksi sebelum data masuk journal kanonis. F_CV tidak pernah menulis langsung ke checkpoint atau ke F3 — pola ini identik dengan F5 (§10), modalitas berbeda (foto, bukan suara).

### 11.2 Pipeline

```text
Foto sampel (kamera lab terstandarisasi)
  → image quality check (blur, exposure, framing)
  → CV inference (4 kelas + confidence per kelas)
  → confidence gate
  → proposed_appearance_patch bila confidence memenuhi threshold, kosong bila tidak
  → user confirmation / correction
  → write checkpoint kanonis dan audit event
  → F3 berjalan hanya jika checkpoint valid
```

### 11.3 Pemetaan taksonomi CV ke appearance kanonis

CV menghasilkan 4 kelas internal yang dipetakan langsung ke enum `appearance` kanonis tanpa kehilangan informasi:

| Kelas CV | Appearance kanonis |
|---|---|
| `stable_uniform` | `uniform` |
| `creaming` | `creaming` |
| `heterogeneous` | `heterogeneous` |
| `phase_separation` | `separated` |

Mapping ini di-version terpisah dari `feature_schema_version` F3, lewat `visual_screening_contract_version`, supaya perubahan taksonomi CV tidak memaksa migrasi skema F3.

### 11.4 Confidence gate dan abstention

Enum `appearance` kanonis tidak mendapat nilai baru khusus untuk CV. Sebagai gantinya:

- confidence kelas teratas memenuhi threshold → sistem mengisi `proposed_appearance_patch` sebagai draft yang wajib dikonfirmasi peneliti.
- confidence di bawah threshold → sistem tidak mengisi apa pun; field `appearance` checkpoint tetap kosong dan diisi manual peneliti, identik dengan alur tanpa CV.

Threshold awal adalah starting point yang wajib dikalibrasi ulang dari data foto asli, bukan angka final yang dianggap sudah tepat.

### 11.5 Kontrak output F_CV

```json
{
  "checkpoint_id": "CHK-J-2026-001-T02-W04",
  "image_ref": "IMG-J-2026-001-T02-W04-01",
  "model_version": "cv-visual-screening-v1",
  "visual_screening_contract_version": "cv-appearance-map-v1",
  "predicted_label": "heterogeneous",
  "per_class_probabilities": {
    "uniform": 0.05,
    "creaming": 0.07,
    "heterogeneous": 0.80,
    "separated": 0.08
  },
  "confidence": 0.80,
  "proposed_appearance_patch": "heterogeneous",
  "requires_confirmation": true,
  "data_origin": "real_capture",
  "scientific_validation_status": "not_validated_for_production"
}
```

Ketika confidence di bawah threshold: `proposed_appearance_patch` bernilai `null`, `requires_confirmation` tetap `true`, dan UI menampilkan foto tanpa saran label — peneliti mengisi appearance dari nol seperti alur manual biasa.

### 11.6 Batas tanggung jawab dan status validasi domain

F_CV tidak boleh menulis langsung ke checkpoint kanonis. F_CV mengusulkan patch; checkpoint hanya terupdate setelah user confirmation. F3 berjalan hanya setelah checkpoint tervalidasi tersimpan.

Konfirmasi manusia ini punya peran ganda: memenuhi prinsip #10 (human sign-off wajib untuk semua output AI yang masuk journal), dan menjadi mitigasi interim untuk status domain yang belum tervalidasi — peneliti selalu jadi sumber kebenaran akhir, sehingga model yang belum teruji akurat di foto asli tidak bisa mencemari data checkpoint secara diam-diam. Setiap konfirmasi atau koreksi manusia direkam di audit event (§14.2) sebagai data untuk mengevaluasi akurasi CV di real-world usage — inilah dasar untuk mengkalibrasi ulang threshold confidence dan menentukan kapan gate validasi domain bisa dianggap terlewati.

MVP tidak boleh mengklaim phase-separation classification sebagai kebenaran final tanpa model visual tervalidasi domain. Label UI:

> **Visual evidence capture. AI visual screening menunggu validasi domain — konfirmasi peneliti wajib sebelum tersimpan.**

---

## 12. Dataset Generation dan Corpus Generation

### 12.1 Urutan generation

```text
1. Ingredient master dan rule KB
2. Formula/process seed terstruktur
3. Numeric stability trajectory serta final outcome
4. Synthetic journal metadata
5. Narrative field dari LLM yang dibatasi seed
6. Query RAG dan synthetic voice transcript
7. Embedding/index generation
8. Train/validation/test split berdasarkan trial family
```

### 12.2 Split discipline

Jangan pernah melakukan split checkpoint row secara random. Semua timepoint dari satu trial harus tetap berada dalam partition yang sama.

```text
Train: trial family A–N
Validation: trial family terpisah
Test: trial family terpisah dan query yang ditulis manusia
```

Ini mencegah model melihat latent trajectory yang sama pada train dan test.

### 12.3 File dataset

```text
data/
├── ingredient_master.json
├── formulation_rules.json
├── formula_seeds.jsonl
├── trial_trajectories.jsonl
├── checkpoints.jsonl
├── final_outcomes.jsonl
├── evidence_corpus.jsonl
├── rag_dev_queries.jsonl
├── rag_blind_test_queries.jsonl
└── metadata.json
```

### 12.4 Guardrail data sintetis

Seluruh synthetic UI content dan API response memiliki field machine-readable tersembunyi dan disclaimer user-visible. Demo script wajib menjelaskan bahwa prototype menggunakan scenario-based synthetic data karena data formulasi Paragon bersifat proprietary dan tidak tersedia untuk peserta.

---

## 13. Evaluasi

### 13.1 Evaluasi F1

| Metrik | Requirement |
|---|---|
| Recall@5 | Evidence relevan ditemukan pada top-5 |
| MRR@5 atau nDCG@5 | Kualitas ranking relevance |
| Citation precision | Klaim dipetakan ke source ID |
| Unsupported-claim rate | Wajib diukur |
| Correct abstention rate | Wajib diukur |
| Permission leakage | Wajib nol pada access-control test |

### 13.2 Evaluasi F2

| Test | Requirement |
|---|---|
| Rule determinism | Input sama menghasilkan output sama |
| Alias normalization | Kasus ambigu meminta confirmation |
| Source provenance | Setiap warning memiliki rule/source/version |
| Override audit | Human override disimpan |

### 13.3 Evaluasi F3

Lakukan retrospective forecast pada landmark tetap, misalnya minggu ke-4.

```text
Input: formula/process + checkpoint minggu 0–4
Target: final pass/fail sampai minggu ke-12
```

| Metrik | Alasan |
|---|---|
| Recall untuk failed trial | Batch high-risk tidak boleh terlewat |
| False-negative rate | Kesalahan forecast paling mahal |
| Precision high-risk alert | Jangan menghentikan trial sehat terlalu banyak |
| PR-AUC / ROC-AUC | Classification discrimination |
| Brier score / calibration curve | Probability yang ditampilkan bermakna atau tidak |
| Lead-time proxy | Warning muncul sebelum failure final |
| Coverage/abstention rate | Model mengakui kondisi unsupported |

Setiap metric wajib diberi label `synthetic-demo evaluation`, bukan production validation.

### 13.4 Evaluasi F5

- ingredient normalization accuracy;
- exact concentration extraction accuracy;
- pH extraction accuracy;
- unsafe auto-fill rate;
- confirmation correction rate;
- latency.

---

## 14. Security, Privacy, dan Auditability

### 14.1 Access control

Permission filtering diterapkan sebelum lexical retrieval, vector retrieval, reranking, dan prompt construction.

| Visibility level | Akses |
|---|---|
| Private | Peneliti tertentu |
| Team | Anggota project team |
| Cross-team summary | Lesson agregat tanpa detail formula |
| Restricted | Role dan approval eksplisit |

### 14.2 Audit event

Simpan:

- input formula version;
- F2 rule yang aktif dan rule version;
- F3 feature-schema/model version;
- checkpoint ID yang dipakai setiap forecast;
- F1 evidence source ID;
- generated output;
- user correction, acceptance, override, serta sign-off.

### 14.3 Privacy boundary

Synthetic demo data boleh memakai external teacher API hanya jika tidak memiliki proprietary atau personal information. Data internal Paragon di masa depan membutuhkan environment privat yang disetujui.

---

## 15. Demo Flow

### Cerita utama tiga menit

1. Peneliti memasukkan brief gel-cream untuk kulit berminyak.
2. F1 mengambil dua trial terdahulu yang relevan, termasuk kasus delayed viscosity collapse.
3. Peneliti membuat formula berdasarkan konteks jurnal.
4. F2 memberi warning electrolyte-thickener risk dan menyimpan normalized formula snapshot.
5. Peneliti mencatat checkpoint minggu ke-4 lewat suara, lalu mengonfirmasi pH, viscosity, dan observation hasil parsing.
6. F3 membaca penurunan viscosity awal, membuat forecast risiko gagal pada minggu ke-12, dan menunjukkan limitation synthetic-demo.
7. F1 membuka historical evidence card yang mendukung warning tersebut.
8. Peneliti meminta review/reformulasi, alih-alih menunggu final test window.

### Pernyataan untuk juri

> ParaLab tidak menggantikan formal stability test. ParaLab membawa keputusan go/no-go lebih awal untuk batch berisiko tinggi dengan menggabungkan formulation constraint terstruktur, trend measurement awal, dan institutional evidence. Prototype memvalidasi workflow ini dengan dataset berbasis skenario yang diberi label jelas, lalu dirancang untuk dilatih ulang memakai historical stability trajectory Paragon.

---

## 16. Definition of Done

### Core data

- [x] 200 project, 600 trial, dan 4.200 checkpoint record tergenerate.
- [x] Semua numeric value berasal dari seeded trajectory generator.
- [x] Setiap synthetic record diberi provenance label.
- [x] Train/validation/test split dilakukan berdasarkan trial family.

### F1

- [ ] Hybrid lexical+dense retrieval berjalan.
- [ ] Evidence card dengan source ID tampil.
- [ ] Evidence kurang menghasilkan abstention.
- [ ] Synthetic source status tampil.

### F2

- [ ] Ingredient alias ternormalisasi ke canonical ID.
- [ ] Deterministic rule menghasilkan source/versioned warning.
- [ ] Versioned F3 feature snapshot keluar.
- [ ] Human override tercatat.

### F3

- [ ] Input memakai F2 feature versioned dan checkpoint terverifikasi.
- [ ] Forecast minggu ke-4 berjalan terhadap outcome minggu ke-12.
- [ ] Output memiliki risk, confidence, signal, action, evidence ID, dan limitation.
- [ ] Kasus unsupported/missing data melakukan abstention.
- [ ] Evaluasi diberi label synthetic-demo.

### F5

- [ ] Voice extraction mengusulkan structured checkpoint update.
- [ ] User confirmation wajib sebelum write.
- [ ] F3 hanya berjalan sesudah checkpoint valid tersimpan.

---

## 17. Roadmap yang Ditunda

1. Ganti trajectory sintetis dengan historical stability data Paragon yang permissioned.
2. Kalibrasi F3 terhadap product-family-specific failure label nyata.
3. Tambahkan survival analysis atau dynamic landmark model untuk time-to-failure.
4. Tambahkan active-learning recommendation untuk measurement atau trial berikutnya.
5. Tambahkan visual instability classification setelah memperoleh dataset gambar berlabel yang sesuai domain.
6. Ekspansi dari O/W gel-cream ke product family lain hanya setelah model coverage test.

---

## 18. Keputusan Arsitektur Final

ParaLab v4 memilih satu end-to-end demo universe yang koheren, bukan beberapa model terpisah:

```text
Synthetic trajectory O/W gel-cream
    ↓
F1 mengambil historical evidence terstruktur
    ↓
F2 menghasilkan feature snapshot deterministik dan versioned
    ↓
F3 memprediksi risiko gagal minggu ke-12 dari checkpoint awal
    ↓
F5 menangkap observasi valid yang memperbarui forecast
    ↓
Human review memegang semua keputusan konsekuensial
```

Arsitektur ini mendemonstrasikan product loop yang nyata tanpa berpura-pura bahwa synthetic data sudah memberikan production-grade cosmetic stability validation.
