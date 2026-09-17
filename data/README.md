# Data ParaLab

Folder ini adalah pusat data kanonis, view turunan, provenance, dan artefak evaluasi. Sebagian besar file dihasilkan oleh script, sehingga jangan diedit manual tanpa menjalankan ulang validator.

> [!WARNING]
> Dataset ParaLab mayoritas merupakan **synthetic-demo** dan bukan data laboratorium, resep, atau ground truth ilmiah. Periksa `data_origin`, `human_verified`, dan `scientific_validation_status` pada setiap alur konsumsi.

## Mulai dari mana

| Kebutuhan | Lokasi |
|---|---|
| Dataset longitudinal utama F3 | `full_synthetic/` |
| Split siap training F3 dan catalog F1 | `training/` |
| Evidence retrieval F1 | `evidence_corpus.jsonl`, `evidence_rag_text.jsonl` |
| Ingredient ontology dan rule F2 | `ingredient_master.json`, `formulation_rules.json` |
| Benchmark F1 | `labeling/rag_blind_v1/`, `evaluation/` |
| Evidence publik | `public_observed/`, `open_sources/` |
| Pilot integrasi awal | `canonical/`, `derived/` dan metadata root data |
| Sumber lama yang masih dibutuhkan pilot | `legacy_sources/` |

## Hierarki data

```text
data/
├── full_synthetic/           # dataset longitudinal synthetic-demo utama
│   ├── canonical/            # project, formula, trial, checkpoint, outcome
│   └── derived/              # view F1, F3, dan contoh F5
├── training/                 # split konsumsi model dan catalog evidence
├── labeling/rag_blind_v1/    # queue serta label machine-adjudicated F1
├── evaluation/               # hasil evaluator F1
├── public_observed/          # evidence publik yang lolos pipeline
├── open_sources/             # hasil ingestion sumber terbuka
├── legacy_sources/           # input pilot lama, tidak tampil di root repo
├── canonical/ dan derived/   # pilot integrasi awal yang masih reproducible
├── ingredient_master.json    # ontology bahan kanonis
├── formulation_rules.json    # rule F2 versioned
└── sha256_manifest.json      # integritas snapshot data
```

## Dataset utama

Dataset `full_synthetic/` berisi:

- 200 proyek;
- 600 formula dan trial;
- 4.800 checkpoint;
- 600 outcome;
- 579 pasangan feature/label F3 eligible;
- 21 outcome ambigu yang dikeluarkan dari supervised forecast.

Detail generator, label, titik waktu, dan split terdapat di [`docs/data/full_dataset.md`](../docs/data/full_dataset.md).

## Konsumsi per capability

### F1

- `evidence_rag_text.jsonl` adalah teks siap embedding.
- Baseline aktif memakai dense retrieval SentenceTransformer tanpa BM25 fallback.
- Blind benchmark menggunakan label machine-adjudicated, bukan review formulator.
- Model dan embedding evaluator aktif disimpan lokal di `sentence-transformer/` dan di-ignore Git.

### F2

- `ingredient_master.json` menyediakan `ingredient_id`, INCI, alias, dan metadata.
- `formulation_rules.json` menyediakan `rule_id`, version, source, severity, dan rationale.
- Rule ini masih prototipe dan tidak boleh dipakai sebagai approval regulasi atau halal.

### F3

- `training/f3_train.jsonl`: 405 row.
- `training/f3_validation.jsonl`: 88 row.
- `training/f3_test.jsonl`: 86 row.
- Hanya feature formula turunan F2, proses, storage, dan observasi sampai landmark yang boleh masuk model.
- Evidence publik saat ini tidak masuk supervised F3 karena tidak memenuhi kontrak longitudinal.

### F5

`full_synthetic/derived/f5_examples.jsonl` berisi transcript teks deterministik dan target patch. File ini bukan rekaman audio atau hasil STT yang tervalidasi. `requires_confirmation` selalu dipertahankan.

## Build dan validasi

```bash
python3 scripts/build_data_pilot.py validate
python3 scripts/build_full_dataset.py validate
python3 scripts/build_public_evidence.py validate
python3 scripts/build_training_views.py validate
```

Untuk regenerasi dataset utama:

```bash
python3 scripts/build_full_dataset.py build
python3 scripts/build_training_views.py build
```

Setelah regenerasi, selalu jalankan validator sebelum memakai atau melakukan commit pada output.

## Provenance dan larangan pencampuran

- `synthetic_demo` membuktikan integrasi software, bukan performa ilmiah.
- `observed_public` dapat dipakai sebagai evidence jika lisensi dan provenance jelas.
- Record cross-sectional publik tidak boleh diubah menjadi trajectory F3 buatan.
- Label `machine_adjudicated` tidak boleh disebut human review atau expert gold label.
- Formula sintetis lengkap harus tetap berstatus `unreviewed_not_lab_recipe`.

## Dokumen terkait

- [Dataset penuh dan F3](../docs/data/full_dataset.md)
- [Evaluasi F1 dense](../docs/data/f1_dense_evaluation.md)
- [Pipeline evidence publik](../docs/data/public_evidence_pipeline.md)
- [Pipeline pilot awal](../docs/data/data_pipeline.md)
