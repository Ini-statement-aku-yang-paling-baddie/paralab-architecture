# Dataset penuh sintetis ParaLab

## Status

Target Core Data [`Architecture v5`](../architecture/architecture_v5.md) sudah digenerasikan:

| Entitas | Jumlah |
|---|---:|
| Proyek | 200 |
| Formula | 600 |
| Trial | 600 |
| Observation series | 600 |
| Checkpoint | 4.800 |
| Outcome | 600 |
| Dokumen historis F1 | 600 |
| Corpus F1 train | 420 |
| Contoh F5 | 4.800 |
| Pasangan feature/label F3 eligible | 579 |
| F3 excluded karena outcome ambigu | 21 |

Seluruh record memakai `data_origin: synthetic_demo`, `human_verified: false`, dan `scientific_validation_status: not_validated_for_production`. Formula memakai INCI kanonis yang dapat diresolusi F2 serta status `unreviewed_not_lab_recipe`. Dataset ini bukan hasil laboratorium, validasi ilmiah, aturan kimia, atau resep yang boleh diracik.

## Model label (v2)

Kajian lengkap beserta sitasinya ada di [`F3-EARLY-DETECTION-STUDY.md`](../reports/f3_early_detection_study.md). Ringkasnya:

Versi `full-synthetic-v1` menentukan outcome dari lookup nama skenario, sehingga tiga skenario selalu `failed` dan dua selalu `passed`. Akibatnya laju peluruhan viskositas minggu-4 berfungsi sebagai sidik jari skenario, dan model F3 mencapai PR-AUC ~0.99 hanya dengan menebak ulang aturan generator. Hubungannya juga non-monotonik: penurunan ~7% berarti lulus sementara ~3% berarti gagal.

Versi `full-synthetic-v2` memakai **model survival dengan onset**:

1. **Hazard laten** (`instability_hazard`) dihitung dari faktor risiko terdokumentasi — interaksi elektrolit dengan thickener sensitif elektrolit (bobot terbesar), ketiadaan emulsifier, storage 40 °C, deviasi parameter proses, dan jarak pH awal dari target 5,5.
2. **Waktu onset** (`sample_onset_week`) ditarik dari distribusi eksponensial yang rata-ratanya memendek seiring hazard. Sebelum onset sampel hanya berfluktuasi normal; sesudahnya ia terdegradasi dengan laju sebanding hazard.
3. **Outcome dibaca dari spesifikasi rilis** di readout minggu 12, seperti praktik uji stabilitas nyata: gagal bila viskositas turun >12% atau pH bergeser >0,5 dari baseline.

Konsekuensinya:

- keacakan hidup di waktu onset, bukan di label, sehingga tren awal informatif tanpa menentukan hasil;
- **informasi bertambah seiring waktu** — ROC-AUC naik 0,785 (minggu 1) → 0,894 (minggu 4) → 0,972 (minggu 8). Ini properti yang tidak dimiliki versi hazard statis sebelumnya, dan yang membuat pertanyaan "berapa lama perlu observasi" bermakna;
- trial ber-onset lambat memang tidak dapat dibedakan dari trial stabil pada minggu 4, apa pun modelnya — batas ini disengaja karena mencerminkan kenyataan;
- `scenario_family` hanya mewarnai *mode* kegagalan, bukan menentukannya (spread fail rate antar skenario 0,19, turun dari 1,00 di v1).

Noise viskositas sengaja dibuat lebih besar (±750 cP) daripada noise pH (±0,012), mengikuti temuan Postles (2018) bahwa pH jauh lebih andal daripada viskositas sebagai penanda reaksi yang mendasari.

Outcome `uncertain` muncul saat pembacaan berada tepat di ambang spesifikasi, dan record tersebut masuk `forecast_excluded.jsonl`.

## Titik waktu

Checkpoint mengikuti protokol accelerated ISO/TR 18811:2018 / Cosmetics Europe: **minggu 0, 1, 2, 4, 6, 8, 12, dan 16**. Horizon label F3 tetap minggu 12; minggu 16 menutup jendela protokol. Total 4.800 checkpoint.

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

Generator menggunakan seed default `2026` dan dapat direplay secara byte-identik. Tujuh scenario family adalah `stable`, `early_viscosity_drop`, `delayed_phase_separation`, `ph_drift`, `electrolyte_thickener_failure`, `process_parameter_failure`, dan `borderline`.

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

- `data/training/f3_train.jsonl`: 405 row;
- `data/training/f3_validation.jsonl`: 88 row;
- `data/training/f3_test.jsonl`: 86 row;
- `data/training/f1_evidence_catalog.jsonl`: 420 dokumen demo train dan 15 evidence publik.

Feature F3 hanya berisi formula, proses, storage, dan observasi minggu 0, 1, 2, serta 4. Label minggu ke-12 disimpan terpisah lalu dijoin oleh builder. Trial dengan outcome ambigu tidak dipaksa menjadi pass/fail dan disimpan di `forecast_excluded.jsonl`.

Konsumen F3 (`modules/f3_stability_sentinel/train_stability_sentinel.py`) tidak membaca persentase bahan mentah. Formula feature diturunkan lewat `modules.f2_guardrail.derive_features()` sesuai batas tanggung jawab [`Architecture v5`](../architecture/architecture_v5.md) §8.

Data paper publik tetap dipakai sebagai evidence F1 dan konteks F2. Saat ini 0 row publik masuk supervised F3 karena belum ada sumber yang memenuhi kontrak longitudinal landmark minggu ke-4 dan outcome minggu ke-12.
