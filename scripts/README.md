# Script dan pipeline

Semua perintah dijalankan dari root repository. Builder umumnya menerima subcommand `build` dan `validate`.

## Peta script

| Script | Fungsi | Output utama |
|---|---|---|
| `build_data_pilot.py` | Mempertahankan pilot integrasi awal secara deterministik | tabel pilot di `data/` |
| `build_full_dataset.py` | Membuat dataset longitudinal synthetic-demo v2 | `data/full_synthetic/` |
| `build_public_evidence.py` | Mengubah sumber publik terverifikasi menjadi evidence | `data/public_observed/` |
| `ingest_open_sources.py` | Ingestion snapshot open source yang diaudit | `data/open_sources/` |
| `build_training_views.py` | Membuat view konsumsi F1/F3 tanpa mencampur provenance | `data/training/` |
| `build_rag_label_pilot.py` | Membuat queue kandidat evaluasi retrieval F1 | `data/labeling/` |
| `evaluate_f1_dense.py` | Mengevaluasi dense reranking pada judged pool | `data/evaluation/` |

## Workflow data utama

```bash
python3 scripts/build_full_dataset.py build
python3 scripts/build_full_dataset.py validate
python3 scripts/build_public_evidence.py build
python3 scripts/build_public_evidence.py validate
python3 scripts/build_training_views.py build
python3 scripts/build_training_views.py validate
```

## Evaluasi F1

Evaluator F1 memerlukan dependency dan model lokal terpisah. Lihat [`docs/data/f1_dense_evaluation.md`](../docs/data/f1_dense_evaluation.md).

```bash
.venv/bin/python scripts/evaluate_f1_dense.py
```

## Aturan penggunaan

- Jangan mengedit output generated secara manual lalu menganggap manifest tetap valid.
- Jalankan `validate` setelah build atau pemindahan sumber data.
- Data publik, synthetic-demo, dan label machine-adjudicated harus tetap dibedakan.
- Script yang menghasilkan data F3 tidak boleh memasukkan outcome masa depan ke feature landmark.
