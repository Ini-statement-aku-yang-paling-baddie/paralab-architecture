# ParaLab AI: Arsitektur v2

> **ARSIP HISTORIS:** dokumen ini telah digantikan oleh [Architecture v5](../../architecture/architecture_v5.md). Jangan gunakan sebagai panduan implementasi aktif.

> **Status:** proposed implementation architecture untuk hackathon
>
> **Relasi ke dokumen sebelumnya:** dokumen ini memperkuat `ARCHITECTURE.md` v2 tanpa menggantinya. Keputusan inti v2 tetap dipertahankan: jurnal sebagai sumber kebenaran, F2 rule-based, F4 ditahan, local-first, dan human sign-off. Perubahan utama adalah hybrid evidence RAG, access control sebelum retrieval, evaluasi tanpa data leakage, batas klaim F3, serta terminologi distillation yang lebih akurat.

---

## 1. Ringkasan Keputusan Produk

### 1.1 Posisi terhadap Smart Lab 2.0

ParaLab AI **bukan pengganti Smart Lab 2.0** dan bukan mesin formulasi tandingan. ParaLab adalah:

> **researcher-facing evidence, guardrail, and institutional-memory layer yang dapat diintegrasikan ke alur Smart Lab.**

Smart Lab membantu Paragon melakukan AI-driven formulation, ingredient discovery, dan intelligent experiment design. ParaLab memastikan bahwa keputusan di dalam alur tersebut:

1. menggunakan evidence eksperimen yang dapat ditemukan kembali;
2. dibatasi oleh aturan kompatibilitas dan compliance yang dapat diaudit;
3. mempertahankan human sign-off;
4. tidak mengekspos formula sensitif lintas tim;
5. menghasilkan pembelajaran yang dapat digunakan kembali oleh eksperimen berikutnya.

### 1.2 Value proposition

> **ParaLab mengubah jurnal eksperimen dari arsip pasif menjadi memori riset aktif yang membantu peneliti menemukan kegagalan terdahulu, mencegah kesalahan formula yang dapat dideteksi lebih awal, dan mencatat evidence baru tanpa mengganggu pekerjaan di lab.**

### 1.3 Scope hackathon

| Prioritas | Modul | Status | Janji yang harus benar-benar didemokan |
|---|---|---|---|
| P0 | F1 Evidence Research Copilot | Wajib | Hybrid retrieval, evidence cards, citation, dan respons `evidence tidak cukup` |
| P0 | F2 Formulation Guardrail | Wajib | Rule-based, explainable, versioned source, dan human review |
| P0 | F5 Voice-to-Structured Logging | Wajib | Push-to-talk, normalisasi bahan, confidence per field, confirm-before-save |
| P1 | F3 Visual Instability Screening | Gated | Hanya jika dataset telah diperoleh dan lolos QC; output berupa visual risk screening |
| P2 | F4 Next-Best Experiment | Roadmap | Tidak dipaksakan dalam MVP; fallback DOE/template dan integrasi engine Smart Lab |
| P2 | Biological Data-Gap Intelligence | Extension | Metadata/evidence coverage, bukan pemrosesan raw omics dan bukan penciptaan biological ground truth |

---

## 2. Prinsip Arsitektur

1. **Canonical source, derived indexes.** Jurnal Praktikum adalah sumber kebenaran kanonis. Search index, vector index, dan cache adalah turunan yang dapat dibangun ulang, bukan sumber kebenaran kedua.
2. **Evidence before generation.** LLM tidak menjawab sebelum retrieval menghasilkan evidence yang cukup.
3. **Authorization before retrieval.** Dokumen yang tidak boleh dilihat pengguna harus disaring sebelum ranking dan generation, bukan disensor setelah jawaban dibuat.
4. **Deterministic decisions for compliance.** Kompatibilitas, batas bahan, regulatory screening, dan supplier verification berasal dari rule/knowledge base, bukan keputusan generatif LLM.
5. **Human remains accountable.** AI menghasilkan rekomendasi, ekstraksi, atau ringkasan. Perubahan formula dan keputusan compliance memerlukan konfirmasi manusia.
6. **Abstention is a feature.** Sistem harus dapat menjawab `evidence tidak cukup`, `data tidak tersedia`, atau `perlu review manusia`.
7. **Local-first inference.** Formula dan jurnal rahasia dapat diproses di lingkungan privat. Teacher model eksternal hanya boleh digunakan pada data sintetis/publik yang diizinkan.
8. **Modular monolith for the hackathon.** Satu backend dengan modul terpisah lebih cepat dan lebih aman daripada microservices prematur. Batas modul tetap jelas agar dapat dipisahkan saat scale-up.
9. **Every AI output is traceable.** Simpan model version, rule version, source IDs, confidence, user confirmation, dan timestamp.
10. **Claims follow validation.** Nama fitur dan output UI tidak boleh melebihi kemampuan dataset serta evaluasi yang sudah dilakukan.

---

## 3. Arsitektur Logis

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                         RESEARCHER WORKSPACE                                 │
│ Dashboard · Journal Editor · Ingredient Table · Voice Input · Evidence Cards│
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │ HTTPS / authenticated session
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     MODULAR BACKEND / API LAYER                              │
│                                                                              │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ Journal Module │  │ Access & Audit  │  │ Background Job Orchestrator  │  │
│  │ CRUD + states  │  │ ACL + provenance│  │ ingest, embed, transcribe     │  │
│  └───────┬────────┘  └────────┬────────┘  └──────────────┬───────────────┘  │
│          │                    │                           │                  │
│  ┌───────▼────────┐  ┌────────▼────────┐  ┌──────────────▼───────────────┐  │
│  │ F1 Evidence RAG│  │ F2 Rule Engine │  │ F5 Voice Structuring         │  │
│  │ hybrid retrieval│ │ deterministic  │  │ STT + entity extraction     │  │
│  └───────┬────────┘  └────────┬────────┘  └──────────────┬───────────────┘  │
│          │                    │                           │                  │
│  ┌───────▼────────────────────▼───────────────────────────▼───────────────┐  │
│  │                 Shared Validation & Explanation Layer                 │  │
│  │ schema validation · evidence sufficiency · confidence · human review │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Optional gated module: F3 Visual Instability Screening                      │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│                                                                              │
│  PostgreSQL                  Derived Retrieval Indexes                       │
│  ├─ journals                 ├─ full-text/BM25-like index                    │
│  ├─ trials                   ├─ pgvector dense embeddings                    │
│  ├─ formulas                 └─ rebuildable document chunks                  │
│  ├─ ingredients                                                               │
│  ├─ rules                    Object storage                                   │
│  ├─ evidence metadata        ├─ permitted documents                          │
│  ├─ permissions              ├─ sample images                                │
│  └─ audit events             └─ permitted audio                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         LOCAL MODEL RUNTIME                                  │
│ multilingual embedder · reranker · 1.5–3B student LLM · STT · optional CNN │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Kenapa modular monolith

Untuk hackathon, backend tunggal memberi keuntungan:

- deployment lebih cepat;
- transaksi journal, rule result, dan audit event lebih sederhana;
- tidak membutuhkan message broker kompleks;
- model dapat dipanggil melalui adapter yang sama;
- modul tetap dapat dipisahkan menjadi service ketika volume dan tim membesar.

---

## 4. Model Data Kanonis

### 4.1 Experiment journal

```json
{
  "journal_id": "J-2026-0017",
  "project_id": "P-2026-004",
  "title": "Gel-Cream Oil Control untuk Pria Aktif",
  "product_category": "moisturizer",
  "formulation_type": "oil_in_water",
  "target_profile": {
    "skin_type": ["oily"],
    "usage_context": ["daytime", "outdoor"],
    "target_segment": "premium"
  },
  "visibility": "team_private",
  "status": "active",
  "owner_team": "team-rnd-03",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### 4.2 Trial

```json
{
  "trial_id": "J-2026-0017-T03",
  "journal_id": "J-2026-0017",
  "formula_version": 3,
  "ingredients": [
    {
      "ingredient_id": "INCI:NIACINAMIDE",
      "supplier_material_id": "SUP-123",
      "concentration_pct_w_w": 5.0,
      "phase": "water"
    }
  ],
  "process": {
    "mixing_speed_rpm": 2500,
    "mixing_time_min": 15,
    "temperature_c": 75,
    "final_ph": 5.8
  },
  "measurements": {
    "viscosity_cp": 12300
  },
  "observations": ["sedikit keruh setelah pendinginan"],
  "result": "needs_iteration",
  "review_state": "human_verified"
}
```

### 4.3 Evidence record

```json
{
  "evidence_id": "EV-0042",
  "evidence_type": "historical_trial",
  "source_id": "J-2024-0017-T02",
  "title": "Viscosity drop pada electrolyte load tinggi",
  "summary": "Ringkasan faktual yang dapat ditampilkan sesuai hak akses.",
  "product_category": "moisturizer",
  "ingredients": ["Niacinamide", "Zinc PCA", "Xanthan Gum"],
  "access_level": "cross_team_summary",
  "owner_team": "team-rnd-02",
  "source_version": "1",
  "quality_status": "reviewed"
}
```

### 4.4 Rule record

```json
{
  "rule_id": "COMPAT-017",
  "rule_type": "electrolyte_thickener_risk",
  "conditions": {
    "thickener_in": ["Xanthan Gum"],
    "electrolyte_load": "high"
  },
  "severity": "warning",
  "message": "Risiko penurunan viskositas pada beban elektrolit tinggi.",
  "source_reference": "KB-SOURCE-008",
  "rule_version": "2026.09",
  "requires_human_review": true
}
```

---

## 5. F1 — Evidence Research Copilot

### 5.1 Tujuan

F1 bukan chatbot dokumen. F1 adalah mesin retrieval yang menjawab pertanyaan riset dengan evidence yang dapat ditelusuri, termasuk kegagalan eksperimen yang sebelumnya sulit ditemukan.

### 5.2 Pipeline

```text
Natural-language query
        │
        ▼
Query understanding
├─ normalize ingredient aliases to INCI
├─ detect product category, phenotype, failure mode
└─ preserve exact numbers, IDs, and chemical terms
        │
        ▼
Authorization filter
├─ user/team permissions
├─ document visibility
└─ field-level redaction policy
        │
        ▼
Parallel retrieval
├─ lexical retrieval for INCI, codes, concentrations, exact terms
├─ dense multilingual retrieval for semantic similarity
└─ metadata filters for category, status, cohort, evidence type
        │
        ▼
Rank fusion + reranking
        │
        ▼
Evidence sufficiency gate
├─ sufficient → grounded summary
├─ partial → answer with explicit gaps
└─ insufficient → abstain and recommend data needed
        │
        ▼
Student LLM grounded generation
        │
        ▼
Evidence cards + citations + access-safe summary
```

### 5.3 Ranking

Jangan hard-code satu weighted cosine score sebagai satu-satunya ranking. Gunakan dua tahap:

1. **Candidate generation:** lexical retrieval + dense retrieval + metadata filter.
2. **Reranking:** relevance terhadap query, category fit, recency sebagai tie-breaker, evidence quality, dan access-safe availability.

Recency tidak boleh mengalahkan evidence lama yang lebih relevan. Formula scoring final harus divalidasi pada development set, bukan dipilih hanya karena terlihat masuk akal.

### 5.4 Evidence sufficiency gate

Sebelum LLM merangkum, hitung kelayakan evidence berdasarkan:

- jumlah evidence relevan;
- relevance score;
- kualitas/review status;
- cakupan metadata penting;
- apakah sumber saling mendukung atau bertentangan.

Contoh respons aman:

```text
Status evidence: terbatas

Ditemukan dua trial gel-cream dengan target kulit serupa, tetapi keduanya tidak
memiliki data sensory terstandar. Sistem belum dapat menyimpulkan bahwa perubahan
bahan yang sama akan memperbaiki tackiness pada formula ini.

Aksi: gunakan dua trial tersebut sebagai referensi awal dan lakukan review formulator.
```

### 5.5 Jenis evidence dalam MVP

- historical experiment journal;
- trial result dan lesson learned;
- ingredient/property reference;
- compatibility/rule source;
- project-active coordination summary;
- optional biological study/cohort summary.

Raw genomic, metabolomic, dan microbiome files tidak dimasukkan ke LLM context pada MVP.

### 5.6 Acceptance criteria

- Query paraphrase menemukan evidence relevan di top-5.
- Exact ingredient dan trial ID tidak hilang akibat semantic retrieval.
- Setiap klaim faktual pada ringkasan memiliki source ID.
- User tanpa izin tidak dapat menemukan keberadaan atau isi dokumen restricted.
- Sistem dapat abstain jika evidence kurang.
- Project aktif yang sangat mirip memunculkan coordination warning, bukan membocorkan formula.

---

## 6. F2 — Deterministic Formulation Guardrail

### 6.1 Tujuan

F2 melakukan early screening yang explainable. F2 **tidak memberikan regulatory approval final** dan tidak menentukan status halal hanya dari nama bahan.

### 6.2 Pipeline

```text
Ingredient row saved/debounced
        │
        ▼
INCI and supplier-material normalization
        │
        ▼
Schema and range validation
        │
        ▼
Parallel deterministic checks
├─ formula compatibility and pH constraints
├─ concentration/internal policy limits
├─ regulatory/restricted-substance screening
├─ allergen checks
└─ supplier-document / halal verification status
        │
        ▼
Aggregate severity without hiding other warnings
        │
        ▼
Explainable warning + source + version + suggested action
        │
        ▼
Human review / formula revision
```

### 6.3 Perbaikan terhadap fail-fast murni

Fail-fast boleh dipakai untuk menentukan severity utama, tetapi sistem tetap perlu menampilkan warning independen lain. Jika compatibility gagal, informasi supplier-document atau regulatory risk tidak boleh hilang dari audit trail.

### 6.4 Status yang aman

| Status | Makna |
|---|---|
| Clear for current screening | Tidak ada masalah pada rules yang tersedia, bukan approval final |
| Warning | Ada risiko atau bukti belum lengkap |
| Blocked by rule | Melanggar constraint eksplisit pada KB prototipe |
| Unknown | Data tidak cukup; wajib review manusia |

### 6.5 Substitution ranking

Candidate substitution difilter secara deterministik berdasarkan fungsi, fase, pH, regulatory status, supplier availability, dan target produk. Ranking dapat menggunakan weighted heuristic yang transparan. LLM hanya menjelaskan hasil ranking, bukan menciptakan candidate di luar KB.

### 6.6 Acceptance criteria

- Rule yang sama menghasilkan hasil yang sama.
- Setiap warning memiliki `rule_id`, sumber, versi, dan action.
- Ingredient alias dipetakan ke canonical INCI dengan confidence.
- Ambiguous mapping meminta konfirmasi, bukan memilih diam-diam.
- Semua override manusia masuk audit log.

---

## 7. F5 — Voice-to-Structured Logging

### 7.1 Pipeline

```text
Push-to-talk audio
        │
        ▼
Audio quality gate
        │
        ▼
Local speech-to-text candidate
        │
        ▼
Terminology normalization
├─ ingredient alias dictionary
├─ fuzzy matching to F2 ingredient KB
└─ number/unit normalization
        │
        ▼
Student LLM structured extraction
        │
        ▼
JSON schema validation + range validation
        │
        ▼
Confidence per field
        │
        ▼
User confirmation
        │
        ▼
Write journal + audit event
```

### 7.2 Output contract

```json
{
  "transcript": "tambah dua persen niasinamida, larutan agak keruh, pH lima koma delapan",
  "ingredient_updates": [
    {
      "raw_name": "niasinamida",
      "canonical_inci": "Niacinamide",
      "concentration_pct": 2.0,
      "confidence": 0.93
    }
  ],
  "measurements": {
    "ph": {
      "value": 5.8,
      "confidence": 0.97
    }
  },
  "observations": ["larutan agak keruh"],
  "requires_confirmation": true
}
```

### 7.3 Model selection gate

Jangan menetapkan STT hanya dari WER publik. Benchmark kandidat menggunakan audio Indonesia/code-switching milik tim yang tidak mengandung data rahasia.

Metrik utama:

- ingredient entity accuracy;
- concentration exact-match accuracy;
- pH exact-match accuracy;
- unsafe auto-fill rate;
- latency pada hardware target.

WER umum hanya metrik pendukung.

### 7.4 Safety rule

Tidak ada hasil voice yang langsung mengubah formula final. Semua perubahan harus melalui confirmation screen. Nilai ambigu, ingredient tidak dikenal, atau confidence rendah diberi highlight.

---

## 8. F3 — Visual Instability Screening, Gated Module

### 8.1 Batas klaim

Jika menggunakan FLUID, F3 hanya diklaim sebagai:

> **screening indikasi ketidakstabilan visual pada formulated liquid.**

F3 bukan:

- prediksi shelf-life kosmetik;
- pengganti stability test;
- pengukur droplet size dari foto makro;
- bukti bahwa formula aman atau stabil;
- model kosmetik tervalidasi.

### 8.2 Go/no-go gate

F3 hanya masuk demo jika:

1. dataset benar-benar tersedia;
2. lisensi/penggunaan mengizinkan;
3. distribusi kelas dan duplikasi telah diperiksa;
4. train/validation/test split dipisahkan per sample sequence, bukan per frame;
5. baseline mengalahkan majority-class classifier;
6. contoh prediksi benar dan gagal telah direview tim;
7. UI menyatakan domain limitation secara eksplisit.

Pemisahan per sample sequence penting agar frame dari vial yang sama tidak bocor ke train dan test.

### 8.3 Pipeline

```text
Standardized image capture
        │
        ▼
Image quality gate
        │
        ▼
Visual classifier
        │
        ▼
Class probabilities
        │
        ▼
Risk band + explanation of visible cues
        │
        ▼
Human review + lab test recommendation
```

### 8.4 Output

Gunakan class probability dan risk band. Jangan mengubah class menjadi skor 0–100 kecuali skor tersebut dikalibrasi dan definisinya terdokumentasi.

---

## 9. Distillation and Local Model Strategy

### 9.1 Terminologi

Metode MVP adalah:

> **teacher-generated synthetic instruction tuning menggunakan LoRA pada student model kecil.**

Ini bukan full logit atau hidden-state knowledge distillation. Istilah `distillation` boleh digunakan sebagai payung narasi hanya jika metode aktual dijelaskan dengan jujur.

### 9.2 Pembagian tugas student

Satu base student model dapat memiliki dua task adapters atau task prompts yang terpisah:

- `TASK_SUMMARIZE_EVIDENCE`: ringkasan grounded untuk F1;
- `TASK_EXTRACT_LAB_NOTE`: structured extraction untuk F5.

Pemakaian satu model menghemat deployment, tetapi evaluasi harus dipisahkan per tugas. Jika multitask training menurunkan salah satu tugas, gunakan adapter terpisah pada base model yang sama.

### 9.3 Data yang boleh diberikan kepada teacher eksternal

- data sintetis;
- public references yang lisensinya mengizinkan;
- schema dan template generik;
- contoh tanpa formula atau identitas internal.

Data yang tidak boleh dikirim:

- formula internal;
- raw participant biological data;
- identifiable researcher/participant data;
- restricted supplier documents;
- proprietary experiment results.

### 9.4 Training vs inference

- Training/LoRA dapat menggunakan GPU terkontrol di lingkungan yang disetujui.
- Inference student dirancang agar dapat dijalankan lokal dengan quantization jika kualitas tetap memenuhi acceptance criteria.
- Jangan menjanjikan `tanpa GPU berat` sebelum mengukur latency dan memory pada hardware target.

### 9.5 Distillation evaluation

Bandingkan setidaknya:

| Sistem | Tujuan |
|---|---|
| Base student zero-shot | Baseline sebelum tuning |
| Teacher output | Upper-reference, bukan ground truth otomatis |
| Tuned student | Kandidat deployment |
| Deterministic parser baseline untuk F5 | Menilai apakah LLM benar-benar diperlukan |

Kriteria:

- kualitas student tidak boleh hanya dinilai dari kemiripan terhadap teacher;
- F1 dinilai terhadap sumber/evidence;
- F5 dinilai terhadap human-labeled structured fields;
- laporkan latency, memory, dan task accuracy.

---

## 10. Corpus and Evaluation Plan

[`CORPUS-PLAN.md`](../../data/corpus_plan.md) tetap menjadi dasar generation. Tambahkan pengamanan berikut.

### 10.1 Corpus tiers

| Tier | Isi | Fungsi |
|---|---|---|
| Tier A | Seed terstruktur dan jurnal sintetis | Demo retrieval dan instruction tuning |
| Tier B | Public ingredient/reference material yang tervalidasi | Evidence dan KB prototipe |
| Tier C | Aggregated biological study/cohort metadata | Data-gap demonstration |
| Tier D | Internal Paragon data | Di luar hackathon; membutuhkan governance dan environment resmi |

Synthetic journal harus selalu diberi label `synthetic_demo_data`. Jangan tampilkan seolah data milik Paragon.

### 10.2 Split tanpa leakage

- Corpus retrieval: 160 entries.
- Development queries: minimal 20, dengan relevance labels manual.
- Blind test queries: minimal 20, ditulis manusia dan tidak digunakan untuk generation/tuning.
- LoRA train/validation/test dipisah berdasarkan journal/seed family, bukan hanya random rows.
- Variasi query dari jurnal yang sama tidak boleh tersebar ke train dan test.

### 10.3 RAG metrics

- Recall@5;
- MRR@5 atau nDCG@5;
- citation precision;
- unsupported-claim rate;
- correct-abstention rate;
- permission leakage rate, target wajib 0 pada test cases.

### 10.4 F5 metrics

- exact match untuk ingredient, concentration, pH, dan process parameters;
- field-level precision/recall/F1;
- unsafe auto-fill rate;
- confirmation correction rate;
- end-to-end latency.

### 10.5 Human review

Review acak 30 entry sintetis tetap dilakukan, tetapi tambahkan:

- scientific plausibility;
- internal numerical consistency;
- duplicate/near-duplicate detection;
- unsupported regulatory/halal claims;
- label synthetic terlihat jelas;
- adversarial query test.

---

## 11. Biological Evidence and Data-Gap Extension

### 11.1 Masalah yang dapat dibantu

ParaLab tidak menciptakan data skin genomics, metabolomics, atau microbiome. ParaLab membantu Paragon mengetahui:

- evidence apa yang tersedia;
- cohort mana yang underrepresented;
- modality apa yang hilang;
- data apa yang belum terhubung ke formula-response outcome;
- eksperimen atau data collection apa yang perlu diprioritaskan.

### 11.2 Metadata model

```json
{
  "evidence_id": "BIO-MICRO-042",
  "evidence_type": "microbiome_study",
  "cohort": {
    "skin_type": ["oily", "acne_prone"],
    "sex": "male",
    "age_range": [18, 25],
    "environment": ["urban", "humid"]
  },
  "sample_count": 73,
  "linked_formula_response_count": 18,
  "modalities": ["microbiome"],
  "missing_modalities": ["metabolomics"],
  "follow_up_quality": "limited",
  "access_level": "aggregated_only",
  "quality_status": "reviewed"
}
```

### 11.3 Query example

> Apakah evidence internal cukup untuk melatih model respons anti-acne pada pria usia 18–25 dengan kulit berminyak di lingkungan urban lembap?

Jawaban tidak boleh hanya berupa paragraf generatif. UI menampilkan:

- jumlah study/cohort relevan;
- sample coverage;
- modality coverage;
- linked outcome coverage;
- limitation;
- source cards;
- status `cukup`, `terbatas`, atau `tidak cukup`.

### 11.4 Roadmap active learning

F4 dapat berkembang menjadi rekomendasi eksperimen/data acquisition berdasarkan uncertainty dan representativeness. Ini ditempatkan sebagai roadmap karena memerlukan real cohort data dan outcome labels.

---

## 12. Security, Privacy, and Governance

### 12.1 Visibility levels

| Level | Akses |
|---|---|
| Private | Pemilik/peneliti tertentu |
| Team | Anggota tim proyek |
| Cross-team summary | Insight agregat tanpa formula penuh |
| Restricted | Role khusus dan explicit approval |

### 12.2 Retrieval security

ACL filter diterapkan sebelum:

- lexical retrieval;
- vector retrieval;
- reranking;
- prompt construction.

Model tidak boleh menerima chunk yang tidak diizinkan. Post-generation redaction bukan mekanisme keamanan utama.

### 12.3 Audit event

Simpan event untuk:

- query dan evidence IDs yang digunakan;
- rule IDs yang terpicu;
- model dan prompt version;
- AI output;
- user edit/override;
- approval/rejection;
- final saved values.

Untuk demo, tampilkan satu panel `Why this answer?` yang membuka source, rule, dan review status.

### 12.4 Biological data

MVP hanya memakai metadata sintetis atau agregat. Raw biological data dan participant identity berada di luar scope. Arsitektur produksi harus memisahkan identity/consent system, pseudonymized research data, dan aggregated model-training data.

---

## 13. Failure Modes and Safe Fallbacks

| Failure | Perilaku aman |
|---|---|
| Retrieval tidak menemukan evidence cukup | Abstain dan tampilkan data yang dibutuhkan |
| Sumber saling bertentangan | Tampilkan disagreement, jangan gabungkan menjadi satu kepastian |
| Ingredient alias ambigu | Minta user memilih canonical INCI |
| Rule source kedaluwarsa | Tandai `needs regulatory review` |
| STT salah mendengar angka | Highlight dan wajib konfirmasi |
| Structured output tidak valid | Reject output, retry terkontrol, lalu fallback manual |
| Model lokal tidak tersedia | F1 menampilkan raw retrieval cards; F5 menyimpan transcript untuk koreksi manual |
| F3 image buruk | Minta pengambilan ulang, jangan keluarkan prediksi |
| Unauthorized document | Dokumen tidak pernah masuk candidate set maupun prompt |
| Index rusak/stale | Rebuild dari canonical journal database |

Graceful degradation memastikan aplikasi tetap berguna sebagai jurnal dan search system walaupun model generatif tidak tersedia.

---

## 14. Deployment Topology

### 14.1 Hackathon

```text
Browser
  ↓
Web application
  ↓
Single backend process
  ├─ REST/API modules
  ├─ retrieval and rule engine
  ├─ local-model adapters
  └─ background jobs
  ↓
PostgreSQL + pgvector + object storage
```

Pilihan implementasi pragmatis:

- frontend: framework web yang dikuasai tim;
- backend: Python API agar integrasi ML mudah;
- relational store: PostgreSQL;
- vector index: pgvector;
- lexical search: PostgreSQL full-text untuk MVP;
- files: local/S3-compatible object storage;
- model runtime: adapter agar backend tidak terkunci pada satu engine/model.

### 14.2 Production evolution

Ketika volume meningkat, pisahkan hanya bottleneck yang terukur:

- ingestion/indexing worker;
- model inference service;
- image inference service;
- audit/analytics pipeline.

Tidak perlu membuat microservices sebelum ada kebutuhan throughput atau isolation yang nyata.

---

## 15. Observability

Minimal log/metric:

- request latency per module;
- retrieval candidate count;
- top-k score distribution;
- abstention rate;
- unsupported-claim flags;
- rule trigger frequency;
- STT/extraction correction rate;
- model failure/fallback count;
- permission-denied events;
- index freshness.

Jangan log raw formula, raw audio, atau biological data ke console/analytics tanpa kebijakan eksplisit.

---

## 16. Demo Flow yang Menang

### Skenario utama, 3–4 menit

1. **Brief:** peneliti membuat jurnal moisturizer pria, kulit berminyak, penggunaan siang hari.
2. **F1:** hybrid RAG menemukan eksperimen relevan, termasuk satu kegagalan akibat tackiness dan satu proyek aktif yang perlu koordinasi.
3. **Evidence:** peneliti membuka `Why this answer?`, melihat source ID, lesson learned, serta batas akses formula.
4. **F2:** peneliti memasukkan bahan/parameter yang memicu warning. Sistem menunjukkan rule, sumber, versi, dan alternatif.
5. **Human control:** peneliti memilih substitusi atau override dengan alasan.
6. **F5:** peneliti mendiktekan hasil trial. Sistem mengisi bahan, konsentrasi, pH, dan observasi, tetapi meminta konfirmasi sebelum menyimpan.
7. **Learning loop:** entry baru masuk jurnal kanonis dan menjadi evidence setelah review.
8. **Penutup:** tampilkan bahwa semua proses lokal/private, traceable, dan dapat diintegrasikan ke Smart Lab.

### Demo tambahan jika waktu dan dataset memungkinkan

- F3 melakukan visual screening dengan disclaimer domain dan rekomendasi lab test.
- Biological evidence query menunjukkan `data tidak cukup` serta gap cohort/modality.

### Kalimat pitch

> Smart Lab membantu Paragon merancang eksperimen yang lebih cerdas. ParaLab memastikan setiap eksperimen menggunakan evidence yang dapat dipercaya, mematuhi guardrail yang dapat diaudit, dan meninggalkan pembelajaran yang tidak hilang ketika proyek atau penelitinya berpindah.

---

## 17. Definition of Done

### F1

- [ ] Hybrid lexical + dense retrieval berjalan.
- [ ] ACL diterapkan sebelum retrieval.
- [ ] Evidence cards dan source IDs tampil.
- [ ] Grounded summary hanya memakai retrieved evidence.
- [ ] Sistem dapat abstain.
- [ ] Blind retrieval evaluation tersedia.

### F2

- [ ] Ingredient normalization dan ambiguity confirmation berjalan.
- [ ] Rule engine deterministik.
- [ ] Warning memiliki rule/source/version.
- [ ] Override dan human sign-off tercatat.
- [ ] UI tidak mengklaim regulatory approval final.

### F5

- [ ] Push-to-talk menghasilkan transcript.
- [ ] Ingredient, concentration, pH, dan observation diekstrak.
- [ ] JSON dan numerical range tervalidasi.
- [ ] Confidence per field ditampilkan.
- [ ] Confirm-before-save wajib.

### Distillation

- [ ] Baseline student, teacher reference, dan tuned student dibandingkan.
- [ ] Test split dipisah berdasarkan seed family.
- [ ] F1 dinilai terhadap evidence, bukan teacher wording.
- [ ] F5 dinilai terhadap human-labeled fields.
- [ ] Latency dan memory diukur pada target runtime.

### F3, jika diaktifkan

- [ ] Dataset tersedia dan lisensi jelas.
- [ ] Split per sample sequence, bukan frame.
- [ ] Domain limitation terlihat di UI.
- [ ] Tidak ada klaim shelf-life atau cosmetic validation.

---

## 18. Architecture Decision Records

| ID | Keputusan | Alasan |
|---|---|---|
| ADR-01 | ParaLab sebagai extension layer Smart Lab | Menghindari overlap strategic dan memperkuat complementarity |
| ADR-02 | Journal DB canonical, indexes derived | Konsistensi data dan rebuildability |
| ADR-03 | Modular monolith untuk MVP | Delivery cepat tanpa distributed-system overhead |
| ADR-04 | Hybrid RAG | Semantic retrieval saja lemah untuk INCI, angka, dan kode |
| ADR-05 | ACL before retrieval | Mencegah formula leakage ke prompt/model |
| ADR-06 | Evidence sufficiency and abstention | Mengurangi hallucination dan overclaim |
| ADR-07 | F2 deterministic | Compliance membutuhkan auditability |
| ADR-08 | Teacher-generated LoRA disebut secara akurat | Menghindari klaim distillation yang menyesatkan |
| ADR-09 | F3 gated and scoped to visual screening | Domain shift FLUID ke kosmetik belum tervalidasi |
| ADR-10 | F4 roadmap | Overlap Smart Lab dan keterbatasan trial data |
| ADR-11 | Biological extension menggunakan metadata agregat | Membantu data-readiness tanpa mengklaim menciptakan omics data |
| ADR-12 | Confirm-before-save untuk voice input | Kesalahan angka/bahan berisiko tinggi |

---

## 19. Risiko Tersisa

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Synthetic corpus terlalu seragam | Retrieval tampak bagus tetapi tidak generalize | Blind human-authored queries, seed-family split, adversarial test |
| Student 1.5–3B tidak cukup kuat | Ringkasan/JSON tidak konsisten | Grounded prompt, schema validator, retry terbatas, fallback template |
| F3 dataset tidak tersedia | Modul gagal dibangun | Jadikan gated bonus, core demo tidak bergantung pada F3 |
| Public ingredient sources tidak cukup untuk keputusan perusahaan | Warning menyesatkan | Label prototype, versioned sources, human review, no approval claim |
| Scope kembali melebar | Core demo tidak selesai | Freeze P0: F1, F2, F5; roadmap tidak boleh menghambat P0 |
| Distillation tidak selesai tepat waktu | Narasi teknis tidak terbukti | Tampilkan baseline local model terlebih dahulu; klaim tuning hanya setelah evaluasi nyata |
| Demo data dianggap data Paragon | Masalah trust | Label `synthetic demo data` pada UI dan pitch |

---

## 20. Urutan Implementasi

1. Bekukan schema jurnal, trial, evidence, ingredient, rule, permission, dan audit event.
2. Generate corpus sintetis terstruktur serta blind test set terpisah.
3. Implementasikan lexical retrieval, dense retrieval, fusion, dan evidence cards.
4. Tambahkan permission filtering dan evidence sufficiency gate.
5. Implementasikan F2 rule engine beserta source/version/audit trail.
6. Implementasikan F5 dari audio sampai confirmation UI.
7. Buat baseline/evaluation sebelum LoRA.
8. Jalankan teacher-generated instruction tuning hanya jika baseline dan test set sudah siap.
9. Integrasikan student dan ukur kualitas/latency.
10. Aktifkan F3 hanya setelah seluruh gate terpenuhi.
11. Polish satu demo flow end-to-end sebelum menambah fitur roadmap.

---

## Keputusan Akhir

Arsitektur v3 mempertahankan fondasi v2, tetapi memusatkan project pada tiga kemampuan yang dapat dibuktikan:

1. **Evidence-grounded research memory melalui hybrid RAG**
2. **Deterministic and auditable formulation guardrails**
3. **Low-friction, human-confirmed data capture melalui voice logging**

Distillation menjadi strategi deployment untuk privasi dan efisiensi, bukan gimmick. F3 tetap mungkin dibangun dengan batas klaim yang benar. F4 dan biological active learning ditempatkan sebagai roadmap yang terhubung langsung ke visi Smart Lab, tanpa menjadikan ParaLab pesaing platform Paragon yang sudah ada.
