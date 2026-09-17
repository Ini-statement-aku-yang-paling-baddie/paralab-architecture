# Dataset penuh sintetis ParaLab

## Status

Target Core Data `ARCHITECTURE-V4.md` sudah digenerasikan:

| Entitas | Jumlah |
|---|---:|
| Proyek | 200 |
| Formula | 600 |
| Trial | 600 |
| Observation series | 600 |
| Checkpoint | 4.200 |
| Outcome | 600 |
| Dokumen historis F1 | 600 |
| Corpus F1 train | 420 |
| Contoh F5 | 4.200 |
| Pasangan feature/label F3 eligible | 515 |
| F3 excluded karena `borderline` | 85 |

Seluruh record memakai `data_origin: synthetic_demo`, `human_verified: false`, dan `scientific_validation_status: not_validated_for_production`. Formula memakai placeholder serta status `unreviewed_not_lab_recipe`. Dataset ini bukan hasil laboratorium, validasi ilmiah, aturan kimia, atau resep yang boleh diracik.

## Generator

```bash
python3 scripts/build_full_dataset.py build
python3 scripts/build_full_dataset.py validate
```

Output berada di `data/full_synthetic/`:

```text
canonical/
  projects.jsonl
  formulas.jsonl
  trials.jsonl
  observation_series.jsonl
  checkpoints.jsonl
  outcomes.jsonl
derived/
  journal_documents.jsonl
  f1_train_corpus.jsonl
  forecast_features.jsonl
  forecast_labels.jsonl
  forecast_excluded.jsonl
  f5_examples.jsonl
generation_contract.json
metrics.json
sha256_manifest.json
```

Generator menggunakan seed default `2026` dan dapat direplay secara byte-identik. Checkpoint tersedia pada minggu 0, 1, 2, 4, 6, 8, dan 12. Tujuh scenario family adalah `stable`, `early_viscosity_drop`, `delayed_phase_separation`, `ph_drift`, `electrolyte_thickener_failure`, `process_parameter_failure`, dan `borderline`.

## Split dan konsumsi model

Seratus formula family masing-masing mempunyai dua proyek. Family tidak pernah melintasi partition:

- train: 140 proyek;
- validation: 30 proyek;
- test: 30 proyek.

Builder view training:

```bash
python3 scripts/build_training_views.py build
python3 scripts/build_training_views.py validate
```

Output siap konsumsi terdapat di:

- `data/training/f3_train.jsonl`: 360 row;
- `data/training/f3_validation.jsonl`: 78 row;
- `data/training/f3_test.jsonl`: 77 row;
- `data/training/f1_evidence_catalog.jsonl`: 420 dokumen demo train dan 15 evidence publik.

Feature F3 hanya berisi formula, proses, storage, dan observasi minggu 0, 1, 2, serta 4. Label minggu ke-12 disimpan terpisah lalu dijoin oleh builder. Scenario `borderline` tidak dipaksa menjadi pass/fail dan disimpan di `forecast_excluded.jsonl`.

Data paper publik tetap dipakai sebagai evidence F1 dan konteks F2. Saat ini 0 row publik masuk supervised F3 karena belum ada sumber yang memenuhi kontrak longitudinal landmark minggu ke-4 dan outcome minggu ke-12.
