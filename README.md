---
title: ParaLab F3 API
emoji: 🧪
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

<!-- Blok YAML di atas adalah metadata Hugging Face Spaces (SDK Docker, port
     7860), dibaca hanya saat repository ini di-push ke remote Space. GitHub
     merendernya sebagai teks biasa dan mengabaikan artinya. Jangan dihapus —
     lihat docs/deploy/huggingface_spaces.md. -->

# ParaLab

ParaLab adalah prototipe local-first untuk membantu riset formulasi **moisturizer gel-cream oil-in-water bagi kulit berminyak**. Sistem menggabungkan pencarian evidence, guardrail formulasi deterministik, structured logging, dan deteksi dini risiko stabilitas.

> [!IMPORTANT]
> Seluruh formula, trajectory, metrik F3, dan hasil CV dalam repository ini merupakan **synthetic-demo**. ParaLab belum tervalidasi untuk keputusan laboratorium, produksi, regulasi, halal, keamanan, atau shelf life.

## Navigasi cepat

| Tujuan | Mulai dari |
|---|---|
| Memahami sistem dan batas klaim | [Architecture v5](docs/architecture/architecture_v5.md) |
| Melihat status implementasi tiap fitur | [Ringkasan capability](#status-capability) |
| Memahami dataset dan provenance | [Panduan data](data/README.md) |
| Menjalankan generator dan evaluator | [Panduan script](scripts/README.md) |
| Menjalankan F2 atau F3 | [Panduan modul](modules/README.md) |
| Memahami evaluasi F1 dense | [Evaluasi F1](docs/data/f1_dense_evaluation.md) |
| Membaca kajian F3 | [Kajian early-risk detection](docs/reports/f3_early_detection_study.md) |
| Membaca hasil pilot CV | [Laporan CV](docs/reports/cv_pilot_report.md) |
| Menelusuri seluruh dokumentasi | [Indeks dokumentasi](docs/README.md) |

## Cara kerja

```text
Pertanyaan riset ──► F1 mencari evidence dan trial serupa
Formula          ──► F2 menormalisasi bahan dan menjalankan rule
Checkpoint lab   ──► F3 membaca tren awal dan menandai risiko
Catatan/foto     ──► F5/CV mengusulkan draft, manusia mengonfirmasi

Hasil akhir tetap diputuskan peneliti atau formulator.
```

### Status capability

| Capability | Status repository | Batas utama |
|---|---|---|
| **F1 Evidence Retrieval** | Evaluator dense-only dengan SentenceTransformer lokal | Benchmark masih machine-adjudicated dan hanya judged pool |
| **F2 Formulation Guardrail** | Rule engine deterministik yang dapat dijalankan | Bukan approval regulasi, halal, atau keamanan |
| **F3 Stability Sentinel** | Baseline tabular, landmark sweep, dan sensitivity analysis | Dilatih dan diuji hanya pada synthetic-demo |
| **F5 Structured Logging** | Kontrak dan contoh data tersedia | STT dan workflow konfirmasi end-to-end belum dibangun |
| **CV Visual Screening** | Pilot pada render sintetis | Belum tervalidasi pada foto kosmetik nyata |
| **API F3** | Adaptor FastAPI lokal tersedia | Web, auth, database, dan deployment cloud belum dibangun |

## Quick start

### 1. Prasyarat

- Python 3.11
- Git
- `uv` direkomendasikan untuk environment terisolasi

### 2. Buat environment F3

```bash
uv venv .venv-f3 --python 3.11
uv pip install --python .venv-f3/bin/python -r requirements/f3_stability_sentinel.txt
uv pip install --python .venv-f3/bin/python -r requirements/cv.txt
```

### 3. Jalankan test dan validator utama

```bash
.venv-f3/bin/python -m unittest discover -s tests -v
.venv-f3/bin/python scripts/build_data_pilot.py validate
.venv-f3/bin/python scripts/build_full_dataset.py validate
.venv-f3/bin/python scripts/build_public_evidence.py validate
.venv-f3/bin/python scripts/build_training_views.py validate
```

### 4. Jalankan baseline F3

```bash
.venv-f3/bin/python modules/f3_stability_sentinel/train_stability_sentinel.py
.venv-f3/bin/python modules/f3_stability_sentinel/landmark_sweep.py
.venv-f3/bin/python modules/f3_stability_sentinel/weight_sensitivity.py
```

Output tersimpan di `modules/f3_stability_sentinel/outputs/1/`.

### 5. Jalankan evaluator F1

F1 membutuhkan model dan embedding lokal yang sengaja tidak dipush karena berukuran besar. Ikuti [panduan F1 dense](docs/data/f1_dense_evaluation.md).

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements/f1_dense.txt
.venv/bin/python scripts/evaluate_f1_dense.py
```

## API F3 lokal

Setelah menjalankan training F3, jalankan adaptor API lokal:

```bash
uv pip install --python .venv-f3/bin/python -r requirements/api.txt
.venv-f3/bin/python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Kontrak endpoint dan environment deploy ada di [`api/README.md`](api/README.md).

## Struktur repository

```text
.
├── README.md                 # entry point proyek
├── docs/                     # arsitektur aktif, dokumentasi data, laporan, arsip
├── modules/                  # capability inti F2 dan F3
├── scripts/                  # builder, validator, ingestion, evaluator
├── data/                     # data kanonis, turunan, manifest, provenance
├── tests/                    # regression, determinisme, safety, anti-leakage
├── requirements/             # dependency per workflow
├── notebooks/                # notebook dan source generator corpus
├── api/                      # adaptor HTTP lokal untuk F3
├── cv/                       # pilot computer vision sintetis
├── resources/                # PDF dan materi referensi proyek
└── sources/                  # snapshot sumber publik yang diaudit
```

Setiap folder utama memiliki `README.md` sendiri. File arsitektur lama dan catatan awal ditempatkan di `docs/archive/` agar tidak mengganggu jalur utama pembaca.

## Hasil baseline saat ini

### F3 pada synthetic-demo

Model terpilih saat ini adalah Random Forest. Pada test split sintetis minggu ke-4:

- recall kegagalan: **94,4%**;
- precision alert: **75,0%**;
- ROC-AUC: **85,8%**;
- early pass: **0**, sesuai kontrak keselamatan.

Angka ini tidak memprediksi performa pada formulasi atau laboratorium nyata.

### CV pada render sintetis

Run terbaik mencatat **89,6% test accuracy** pada dataset render prosedural V3. Hasil ini membuktikan pipeline training berjalan pada domain sintetis, bukan kemampuan mengenali ketidakstabilan kosmetik dari foto nyata.

## Aturan keselamatan dan data

1. F2 tetap deterministik dan wajib menunjukkan rule/source/version.
2. F3 hanya memberi `flag_high_risk`, `continue_observation`, atau abstain.
3. `continue_observation` tidak boleh ditafsirkan sebagai formula lolos.
4. F1 tidak memasukkan narasi atau relevance score sebagai feature F3.
5. F5 dan CV tidak boleh menulis checkpoint tanpa konfirmasi manusia.
6. Data sintetis tidak boleh disebut data lab, resep, atau ground truth ilmiah.
7. Data publik cross-sectional tidak boleh dipaksa menjadi label longitudinal F3.

## Pengembangan berikutnya

Prioritas tertinggi bukan menambah model baru, melainkan membangun satu vertical slice:

```text
input formula → F2 → buat trial → checkpoint → F3 → review manusia → audit event
```

Setelah itu, lanjutkan dengan evaluasi F1 oleh reviewer manusia, pengumpulan data longitudinal nyata, calibration F3, serta validasi CV pada foto lab.

## Dokumentasi

Dokumentasi aktif dan arsip dipisahkan dengan jelas di [docs/README.md](docs/README.md). Untuk memahami keputusan teknis terbaru, selalu mulai dari [Architecture v5](docs/architecture/architecture_v5.md), bukan versi historis.
