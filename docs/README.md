# Dokumentasi ParaLab

Folder ini memisahkan dokumentasi aktif dari materi historis. Pembaca baru cukup mengikuti jalur **Mulai di sini** dan tidak perlu membuka arsip.

## Mulai di sini

1. [Architecture v5](architecture/architecture_v5.md) menjelaskan sistem, status implementasi, kontrak antarmodul, dan batas klaim.
2. [Dataset penuh](data/full_dataset.md) menjelaskan data longitudinal sintetis dan konsumsi F3.
3. [Kajian F3](reports/f3_early_detection_study.md) menjelaskan keputusan one-sided alert dan larangan early pass.
4. [Laporan CV](reports/cv_pilot_report.md) menjelaskan hasil pilot serta domain gap ke foto nyata.

## Indeks dokumentasi aktif

### Arsitektur

| Dokumen | Isi |
|---|---|
| [architecture_v5.md](architecture/architecture_v5.md) | Sumber utama arsitektur dan status implementasi terkini |

### Data dan evaluasi

| Dokumen | Isi |
|---|---|
| [full_dataset.md](data/full_dataset.md) | Dataset full synthetic, split, schema, dan konsumsi F3 |
| [f1_dense_evaluation.md](data/f1_dense_evaluation.md) | Menjalankan dan menafsirkan evaluator F1 dense-only |
| [public_evidence_pipeline.md](data/public_evidence_pipeline.md) | Ingestion evidence publik serta aturan provenance |
| [labeling_pilot.md](data/labeling_pilot.md) | Queue pelabelan blind retrieval F1 |
| [data_pipeline.md](data/data_pipeline.md) | Pipeline pilot awal yang masih dipertahankan untuk reproducibility |
| [corpus_plan.md](data/corpus_plan.md) | Kontrak corpus dan rencana distilasi lokal |

### Laporan

| Dokumen | Isi |
|---|---|
| [f3_early_detection_study.md](reports/f3_early_detection_study.md) | Audit generator F3, literatur, evaluasi, dan pivot klaim |
| [cv_pilot_report.md](reports/cv_pilot_report.md) | Kronologi run CV, bug model, hasil, dan batas integrasi |

## Arsip

`archive/` berisi versi arsitektur terdahulu, ide awal, dan catatan riset mentah. File tersebut dipertahankan untuk jejak keputusan, tetapi bukan rujukan implementasi saat ini.

Lihat [panduan arsip](archive/README.md) hanya jika perlu menelusuri sejarah proyek.
