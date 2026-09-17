# ParaLab: Arsitektur v5

> **Status:** arsitektur implementasi saat ini, diperbarui dari seluruh artefak yang sudah ada di repository.
>
> **Menggantikan:** [architecture_v4.md](../archive/architecture/architecture_v4.md) sebagai dokumen arsitektur utama.
>
> **Batas utama:** ParaLab adalah prototipe local-first untuk R&D moisturizer gel-cream O/W kulit berminyak. Ia membantu peneliti menelusuri evidence, menyaring formula, dan menandai risiko lebih awal. Ia **bukan** pengganti formulator, uji stabilitas formal, persetujuan regulasi, atau keputusan produksi.

---

## 1. ParaLab dalam satu menit

ParaLab menyatukan empat alur yang saling terkait:

1. **F1, Evidence Retrieval:** menemukan trial dan evidence relevan dari corpus yang diizinkan.
2. **F2, Formulation Guardrail:** menormalkan bahan dan menjalankan aturan yang hasilnya dapat diaudit.
3. **F3, Stability Sentinel:** memakai formula, proses, dan tren checkpoint awal untuk menandai risiko kegagalan sebelum minggu ke-12.
4. **F5, Structured Logging:** kontrak data untuk mengubah catatan lab menjadi draft checkpoint yang wajib dikonfirmasi manusia.
5. **F4, Next Validation Step:** heuristic deterministik yang memprioritaskan observasi atau review berikutnya dari output F2/F3 terstruktur.

Ada juga **pilot CV** terpisah. Pilot ini dapat mengusulkan observasi visual dari gambar sintetis, tetapi belum dihubungkan ke pipeline utama dan tidak tervalidasi untuk foto kosmetik nyata.

```text
Pertanyaan riset / formula
        │
        ├── F1: cari evidence dan kasus serupa
        │
        └── F2: normalisasi bahan + jalankan rule deterministik
                    │
                    ▼
              formula / proses valid
                    │
      checkpoint lab terkonfirmasi manusia
                    │
                    ▼
        F3: alert risiko tinggi atau lanjutkan observasi
                    │
                    ▼
       peneliti review dan memulai reformulasi paralel bila perlu
```

**Janji yang tepat:** F3 dapat membantu memulai reformulasi lebih awal ketika risiko tinggi terdeteksi. Uji stabilitas tetap diteruskan sesuai protokol. ParaLab tidak pernah memberi status *early pass*.

---

## 2. Apa yang sudah benar-benar diimplementasikan

| Area | Status | Implementasi saat ini | Bukan klaimnya |
|---|---|---|---|
| Data dan provenance | Implemented | Generator deterministik, manifest SHA-256, schema, split anti-leakage, dan validator | Data lab nyata atau ground truth ilmiah |
| F1 dense retrieval | Implemented sebagai evaluator baseline | SentenceTransformer lokal `paraphrase-multilingual-MiniLM-L12-v2`, embedding lokal, dan evaluator blind pool | RAG produksi lengkap atau evaluasi expert |
| F2 Guardrail | Implemented | Normalisasi INCI/alias, rule versioned, warning/blocked/unknown, dan derived feature | Approval BPOM, halal, atau formulasi otomatis |
| F3 Stability Sentinel | Implemented sebagai baseline synthetic-demo | Baseline tabular, feature F2 + proses + tren sampai landmark, threshold one-sided alert | Prediksi stabilitas kosmetik nyata atau pengganti formal test |
| F5 | Kontrak data dan contoh sintetis tersedia | `f5_examples.jsonl`, field confirmation, dan provenance transcript | Speech-to-text atau aplikasi voice logging end-to-end |
| F4 Next Validation Step | Implemented sebagai heuristic API | `modules/f4_next_validation.py` dan `POST /v1/f4/next-validation` memakai field F2/F3 terstruktur | Formula optimizer, instruksi reformulasi, atau autonomous experiment design |
| CV visual screening | Pilot terpisah | Generator gambar sintetis dan notebook training `TinyVialCNN` | Klasifikasi foto kosmetik asli atau input otomatis F3 |
| API F3 | Implemented sebagai adaptor lokal | FastAPI memuat model hash-verified, menjalankan F2 + feature engineering, lalu forecast/abstain | Web, auth, database runtime, dan sistem siap produksi |

Arsitektur v5 membedakan **yang berjalan dalam kode** dari **desain target**, agar demo tidak memberi kesan kapabilitas yang belum tersedia.

---

## 3. Scope dan prinsip keselamatan

### Scope data yang didukung

- Satu product family: **moisturizer gel-cream oil-in-water untuk kulit berminyak**.
- Formula sintetis berstatus `unreviewed_not_lab_recipe`.
- Seluruh record demo memakai `data_origin: synthetic_demo` dan `scientific_validation_status: not_validated_for_production`.
- Data publik dapat menjadi evidence F1 atau konteks F2, tetapi saat ini **tidak ada** record publik yang layak masuk supervised F3 karena tidak memenuhi kontrak trajectory longitudinal dan outcome yang dibutuhkan.

### Prinsip yang wajib dipertahankan

1. **Manusia memegang keputusan akhir.** AI hanya menyarankan, mengurutkan evidence, atau menandai risiko.
2. **F2 tetap deterministik.** LLM tidak menjalankan rule engine dan tidak menggantikan pemeriksaan aturan.
3. **F3 tidak membaca persentase bahan mentah.** Ia hanya memakai fitur formula yang diturunkan F2, parameter proses, serta tren observasi.
4. **F1 tidak menyuntikkan narasi ke model F3.** Source ID dapat dipakai sebagai konteks penjelasan, tetapi prosa retrieval dan relevance score bukan fitur numerik F3.
5. **Tidak ada early pass.** Keluaran risiko rendah berarti `continue_observation`, bukan formula dinyatakan aman.
6. **Output yang masuk jurnal harus dikonfirmasi manusia.** Ini berlaku untuk F5 dan desain integrasi CV.
7. **Abstain lebih aman daripada mengarang.** Data kurang, domain tidak didukung, atau checkpoint tidak lengkap harus menghentikan forecast.
8. **Synthetic demo tidak boleh dipromosikan sebagai bukti ilmiah.** Ia menguji konsistensi kontrak, alur, dan software, bukan kinerja di laboratorium nyata.

---

## 4. Peta komponen dan aliran data

```text
                         ┌───────────────────────────┐
                         │ Peneliti / formulator      │
                         │ query · formula · catatan │
                         └─────────────┬─────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│ F1 Evidence      │         │ F2 Guardrail     │         │ F5 / CV proposal │
│ Retrieval        │         │ deterministic    │         │ draft only       │
└───────┬──────────┘         └────────┬─────────┘         └────────┬─────────┘
        │                              │                            │
        │ source IDs                   │ derived feature            │ human confirmation
        │                              ▼                            ▼
        │                    ┌──────────────────────────────────────────┐
        │                    │ Checkpoint kanonis                       │
        │                    │ baseline + pengukuran + observasi        │
        │                    └──────────────────┬───────────────────────┘
        │                                       │
        │                                       ▼
        │                    ┌──────────────────────────────────────────┐
        └───────────────────►│ F3 Stability Sentinel                    │
             explanation     │ alert risiko / continue observation      │
                             └──────────────────────────────────────────┘
```

### Sumber data dan artefak

| Lokasi | Isi | Konsumen utama |
|---|---|---|
| `data/ingredient_master.json` | 80 bahan dengan ID kanonis dan alias | F1, F2, F5 |
| `data/formulation_rules.json` | 165 rule versioned dengan source ID | F2 |
| `data/evidence_rag_text.jsonl` | 600 teks evidence siap embedding | F1 |
| `data/labeling/rag_blind_v1/` | 10 query blind × 30 kandidat, label machine-adjudicated | evaluator F1 |
| `data/full_synthetic/canonical/` | proyek, formula, trial, checkpoint, outcome | generator dan audit F3 |
| `data/training/` | split F1/F3 yang aman terhadap family leakage | training/evaluasi F3 |
| `modules/f2_guardrail.py` | engine F2 | F2 dan feature F3 |
| `modules/f3_stability_sentinel/` | training, sweep, sensitivity, output F3 | F3 |
| `cv/` | pilot visual sintetis dan notebook evaluasi | eksperimen CV |

`data/` dipertahankan sebagai lokasi kanonis. Dokumen, modul, notebook, dan laporan dipisah berdasarkan tujuan agar artefak yang direferensikan manifest dan generator tidak berpindah tanpa kebutuhan.

---

## 5. Kontrak data yang menyatukan sistem

### 5.1 Formula dan hasil F2

Peneliti memasukkan pasangan `bahan` dan `pct`. F2 mencoba meresolusi nama ke `ingredient_id`, menjalankan rule yang relevan, lalu mengembalikan hasil yang dapat dilacak ke rule/source/version.

```json
{
  "overall_status": "warning",
  "derived_features": {
    "feature_schema_version": "stability-sentinel-v1",
    "electrolyte_load": "high",
    "thickener_sensitivity": "high",
    "electrolyte_thickener_risk": "high",
    "emulsifier_balance_status": "watch"
  },
  "requires_human_signoff": true
}
```

Status F2 memiliki arti terbatas:

| Status | Makna |
|---|---|
| `clear_for_current_screening` | Tidak ada rule prototipe yang aktif. Bukan approval final. |
| `warning` | Ada faktor yang perlu diperiksa manusia. |
| `blocked` | Constraint prototipe dilanggar. |
| `unknown` | Bahan/data belum dapat dipetakan dengan aman. |

### 5.2 Checkpoint longitudinal

F3 membutuhkan baseline dan checkpoint setelah baseline. Input observasi mencakup pH, viskositas, appearance, kondisi storage, dan proses. Dataset penuh memiliki titik minggu **0, 1, 2, 4, 6, 8, 12, dan 16**.

Field yang tidak ada tidak boleh diisi oleh model. Jika baseline atau checkpoint landmark tidak tersedia, F3 harus abstain.

### 5.3 Outcome dan pemisahan label

Target F3 adalah:

```text
P(gagal pada atau sebelum minggu ke-12 | formula + proses + observasi sampai landmark)
```

Label disimpan terpisah dari feature. Formula family tidak boleh melintasi train, validation, dan test. Ini mencegah model mengenali keluarga formula yang sama, bukan belajar dari informasi yang seharusnya tersedia pada waktu forecast.

---

## 6. F1: Evidence Retrieval saat ini

### Implementasi

F1 saat ini adalah **baseline dense-only**, bukan hybrid retrieval. Query dan 600 evidence document di-embed dengan `paraphrase-multilingual-MiniLM-L12-v2` dari export lokal.

```text
query
  → SentenceTransformer lokal
  → cosine similarity ke embedding evidence
  → ranking kandidat
  → metrik pada judged pool
```

- Evaluator: `scripts/evaluate_f1_dense.py`
- Dokumentasi eksekusi: [`../data/f1_dense_evaluation.md`](../data/f1_dense_evaluation.md)
- Model dan embedding: `sentence-transformer/` local-only, di-ignore Git karena sekitar 417 MB.
- Tidak ada BM25 atau fallback lexical pada baseline ini.

### Batas evaluasi

Blind benchmark berisi 10 query dan 30 kandidat per query, total 300 pasangan. Labelnya **machine-adjudicated internal**, bukan label formulator atau gold standard ilmiah. Metrik hanya mengukur kualitas reranking dalam judged pool tersebut, bukan recall terhadap seluruh corpus atau kualitas evidence kosmetik nyata.

F1 belum menyediakan API, authorization runtime, reranker, grounded answer generator, maupun integrasi `evidence_ids` ke output F3.

---

## 7. F2: Guardrail Formulasi

F2 sudah berjalan di `modules/f2_guardrail.py`.

```text
nama bahan / alias
  → resolusi ke INCI kanonis
  → cek konsentrasi, pasangan bahan, dan konteks
  → hasil rule versioned
  → derived feature stabil untuk F3
  → human sign-off bila warning, blocked, atau unknown
```

F2 menyediakan:

- alias dan fuzzy matching terbatas;
- evaluasi rentang konsentrasi, pasangan kompatibilitas, konteks oily skin, dan beberapa screening prototipe;
- `rule_id`, `rule_version`, `source_id`, rationale, dan flag review manusia;
- feature schema `stability-sentinel-v1`.

F2 tidak boleh disebut mesin persetujuan BPOM, halal, keselamatan, atau kompatibilitas kimia yang lengkap. Data rule tetap perlu diverifikasi terhadap sumber resmi sebelum penggunaan nyata.

---

## 8. F3: Stability Sentinel

### Tujuan operasional

F3 memprioritaskan perhatian peneliti terhadap trial yang patut direformulasi lebih awal, sambil uji stabilitas tetap berjalan.

| Keluaran | Tindakan |
|---|---|
| `flag_high_risk` | Minta review formulator dan boleh mulai reformulasi paralel. Uji berjalan tetap diteruskan. |
| `continue_observation` | Belum ada alert. Ini bukan pass, approval, atau alasan menghentikan uji. |
| abstain | Data belum cukup atau domain tidak didukung. Minta checkpoint/data yang kurang. |

### Feature yang digunakan

F3 memakai 18 feature tabular dari tiga kelompok:

1. **Feature F2:** electrolyte load, sensitivitas thickener, risiko electrolyte-thickener, status emulsifier, jumlah bahan, dan rasio fase minyak.
2. **Feature proses/kondisi:** suhu heating, homogenization RPM, mixing time, dan suhu storage.
3. **Tren observasi:** baseline/current/change pH, baseline/current/change/slope viskositas, serta jumlah warning appearance.

F3 secara sengaja tidak memakai raw ingredient percentage dan tidak memakai teks warning F2 atau narasi F1.

### Baseline yang berjalan

`modules/f3_stability_sentinel/train_stability_sentinel.py` membandingkan Logistic Regression, Random Forest, Gradient Boosting, dan bila dependency tersedia, XGBoost. Model dipilih berdasarkan PR-AUC validation. Output run saat ini memilih **Random Forest**.

Pada test split synthetic-demo saat landmark minggu ke-4, report saat ini mencatat:

- recall gagal: **94,4%**;
- precision alert risiko tinggi: **75,0%**;
- ROC-AUC: **85,8%**;
- decision threshold: **0,321**, dipilih pada validation dengan F-beta (`beta=2`);
- 86 row test, seluruhnya synthetic-demo.

Angka ini hanya menunjukkan baseline berjalan terhadap generator sintetis. Ia bukan estimasi kinerja pada data kosmetik nyata.

### Keterbatasan yang sedang diketahui

- `likely_failure_mode` belum ada karena label F3 masih biner `failed_by_12`.
- `appearance_warning_count` belum informatif karena observasi full synthetic saat ini berlabel `uniform`.
- `evidence_ids` kosong karena integrasi F1 ke baseline F3 belum dibangun.
- F3 tidak memiliki data longitudinal publik yang memenuhi syarat.
- Data onset lambat memang tidak bisa dibedakan dari trial stabil pada minggu ke-4. Sistem harus menyatakan ketidakpastian ini, bukan menyembunyikannya.

Kajian alasan keputusan one-sided alert tersedia di [`../reports/f3_early_detection_study.md`](../reports/f3_early_detection_study.md).

### Deployment bundle dan API lokal

Setiap training F3 menghasilkan `model_manifest.json` di samping model `joblib`. Manifest mengikat model pada hash, urutan feature, threshold hasil validation, versi rule F2, provenance `synthetic_demo`, dan batas CV `concept_only_synthetic_render_pilot`.

Adaptor `api/app.py` menyediakan `GET /health` dan `POST /v1/f3/forecasts`. Ia hanya memuat model jika hash dan feature schema sesuai manifest. Input menggunakan istilah domain, lalu F2 dan feature engineering menghitung feature internal. Jika formula blocked/unknown atau checkpoint tidak lengkap, API mengembalikan `abstain_human_review_required` tanpa skor risiko.

API ini lokal untuk integrasi web dan demonstrasi. Auth, database, rate limiting, audit persistence, dan deployment cloud tetap belum diimplementasikan.

---

## 9. F5 dan pilot CV

### F5: logging terstruktur

F5 sudah memiliki contoh training/kontrak di `data/full_synthetic/derived/f5_examples.jsonl`. Setiap contoh memakai transcript deterministik, bukan rekaman audio. Oleh karena itu, F5 yang sudah ada hanya memvalidasi **bentuk data**, bukan kualitas speech-to-text.

Desain targetnya:

```text
rekaman / catatan
  → transkripsi
  → ekstraksi field checkpoint
  → validasi range dan schema
  → draft patch + confidence per field
  → konfirmasi peneliti
  → simpan checkpoint kanonis
```

Tidak ada STT, UI konfirmasi, atau write path jurnal runtime yang sudah diimplementasikan.

### CV: visual screening

Pilot CV melatih `TinyVialCNN` pada render prosedural sintetis dengan empat kelas: `stable_uniform`, `creaming`, `phase_separation`, dan `heterogeneous`.

Run terbaik mencatat **89,6% test accuracy (86/96)** pada dataset render sintetis v3. Hasil ini tidak berlaku untuk foto kosmetik nyata, karena belum ada data foto berlabel dan terdapat domain gap besar antara render dan kondisi lab.

Desain integrasi yang aman sudah ditetapkan, tetapi belum diimplementasikan:

```text
foto → quality check → usulan appearance + confidence
     → konfirmasi/koreksi peneliti → checkpoint kanonis → F3
```

CV tidak boleh menulis langsung ke checkpoint atau F3. Detail dan batas pilot ada di [`../reports/cv_pilot_report.md`](../reports/cv_pilot_report.md).

---

## 10. Dataset, reproducibility, dan provenance

### Dataset penuh synthetic-demo

Dataset full synthetic memiliki:

- 200 proyek;
- 600 formula dan trial;
- 4.800 checkpoint;
- 600 outcome;
- 579 pasangan feature/label F3 eligible;
- 21 outcome ambiguous yang sengaja dikeluarkan dari training forecast.

Generator memakai seeded hazard model dengan waktu onset. Ini menghindari versi lama yang labelnya dapat ditebak dari nama skenario. Namun, perbaikan generator tidak mengubah status dataset: ia tetap demo sintetis.

### Reproducibility

- Generator dataset memverifikasi schema dan manifest SHA-256.
- Split F3 berbasis formula family.
- Folder model F1 lokal dan virtual environment tidak ditrack Git.
- Test suite mencakup determinisme, anti-leakage, kontrak F2/F3, F1 dense-only, dan provenance pilot CV.

Perintah utama:

```bash
.venv-f3/bin/python -m unittest discover -s tests -v
.venv-f3/bin/python scripts/build_full_dataset.py validate
.venv-f3/bin/python modules/f3_stability_sentinel/train_stability_sentinel.py
.venv-f3/bin/python modules/f3_stability_sentinel/landmark_sweep.py
.venv-f3/bin/python modules/f3_stability_sentinel/weight_sensitivity.py
```

Lihat [`../data/full_dataset.md`](../data/full_dataset.md) untuk struktur dataset dan kontrak generator.

---

## 11. Struktur repository

```text
ParaLab/
├── data/                         # data kanonis, view training, provenance
├── modules/
│   ├── f2_guardrail.py           # F2 deterministic guardrail
│   └── f3_stability_sentinel/    # training dan analisis F3
├── scripts/                      # builder, validator, evaluator
├── api/                          # adaptor FastAPI lokal untuk F3
├── cv/                           # pilot visual synthetic, belum terintegrasi
├── notebooks/corpus_generator/   # generator corpus F1
├── tests/                        # kontrak dan regression tests
├── docs/
│   ├── architecture/             # dokumen ini dan versi sebelumnya
│   ├── data/                     # kontrak/pipeline/evaluasi data
│   ├── reports/                  # kajian F3 dan laporan CV
│   └── product/                  # konsep produk
├── resources/                    # referensi non-eksekusi
└── sources/                      # materi sumber proyek
```

Konvensi nama file baru adalah lowercase `snake_case` untuk portability dan kemudahan pencarian lintas platform. Nama produk tetap ditulis **ParaLab** dalam narasi dan UI.

---

## 12. Roadmap yang jelas

### Sebelum mengklaim lebih dari synthetic-demo

1. Kumpulkan checkpoint longitudinal nyata dengan persetujuan dan provenance yang benar.
2. Tetapkan label outcome dan failure mode yang diverifikasi formulator.
3. Validasi F2 rule per sumber resmi dan kebijakan organisasi.
4. Evaluasi F1 dengan reviewer manusia/domain expert, bukan machine-adjudicated labels saja.
5. Uji F3 secara holdout temporal/site/formula family pada data nyata, termasuk calibration dan false-negative review.
6. Kumpulkan foto lab berlabel manusia sebelum mengaktifkan CV pada workflow nyata.

### Integrasi software berikutnya

1. Integrasikan API F3 dengan UI researcher serta persistence trial/checkpoint/audit event local-first.
2. UI researcher yang menampilkan evidence, status rule, limitation, dan human sign-off secara eksplisit.
3. Implementasi F5 speech-to-text dan halaman konfirmasi field.
4. Sambungkan evidence ID F1 sebagai explanation layer F3 tanpa menjadi feature model.
5. Integrasikan CV hanya setelah validation gate foto nyata terpenuhi.

---

## 13. Definisi demo yang jujur

Demo ParaLab dianggap berhasil bila dapat memperlihatkan alur berikut tanpa klaim berlebihan:

1. Peneliti memasukkan formula dan F2 menampilkan bahan tak dikenal, warning, atau rule yang aktif beserta source/version.
2. Peneliti melihat checkpoint terstruktur yang jelas status konfirmasi manusianya.
3. F3 menerima data sampai minggu ke-4 dan hanya memberi alert risiko atau instruksi melanjutkan observasi.
4. Jika ada alert, UI menerangkan bahwa reformulasi dapat dimulai paralel, sementara uji stabilitas tetap berjalan.
5. F1 menampilkan evidence retrieval beserta status bahwa corpus/benchmark masih synthetic-demo dan machine-adjudicated.
6. Semua layar memisahkan evidence, rule deterministik, prediksi synthetic-demo, dan keputusan manusia.

Dengan batas tersebut, ParaLab adalah fondasi prototipe yang dapat diuji dan diaudit, tanpa menyamarkan desain masa depan sebagai fitur yang sudah berjalan.
