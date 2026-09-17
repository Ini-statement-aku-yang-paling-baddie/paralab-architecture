# Pipeline evidence publik dan train/test ParaLab

## Tujuan

Pipeline ini menambahkan data yang benar-benar dilaporkan sumber open-access tanpa mengubah `data/legacy_sources/corpus_paralab.json`, embedding lama, atau mengklaim bahwa semua data ParaLab menjadi data lab nyata.

Ada tiga origin yang tetap terpisah:

| Origin | Lokasi | Peran yang diizinkan |
|---|---|---|
| `synthetic_demo` | `data/canonical/`, `data/derived/` | Smoke test workflow F1/F3/F5. Bukan validasi ilmiah. |
| `observed_public` | `data/public_observed/` | Evidence F1 dan konteks F2 dengan sitasi. |
| `observed_open_dataset` | `data/open_sources/figshare_shampoo/` | Dataset proxy yang disimpan utuh dengan provenance. Tidak otomatis bergabung ke F3 moisturizer. |

## Sumber yang sudah di-ingest

### 1. Paper cream O/W open access

- DOI: `10.3390/pharmaceutics12070647`
- Judul: *Progressing Towards the Sustainable Development of Cream Formulations*
- Lisensi: CC BY 4.0
- Tabel: Table 2 dan Table 5
- Artefak sumber: `sources/public/PMC7407566_tables_2_5.json`
- Output: `data/public_observed/`

Ekstraksi pertama berisi **15 formulasi DoE yang benar-benar dilaporkan**, dengan tiga variabel yang tersedia di tabel: glycerol monostearate, isopropyl myristate, dan laju homogenisasi. Ia juga menyimpan pH hari ke-1 serta instability index hari ke-4 beserta SD dan status compliance yang dilaporkan tabel.

Formula ini **bukan resep**. Paper tidak menyediakan keseluruhan komposisi pada tabel yang di-ingest, domainnya cream hidrokortison farmasi, dan pH serta instability index berasal dari waktu/protokol berbeda.

### 2. Dataset shampoo Figshare berlisensi CC0

- Koleksi: `10.6084/m9.figshare.c.7132624`
- Artikel/dataset: `10.6084/m9.figshare.25451878.v1`
- Lisensi: CC0
- Output: `data/open_sources/figshare_shampoo/`
- Jumlah record hasil fetch: **812**

Nilai sumber dipertahankan verbatim di `normalized/liquid_formulations.jsonl` dalam field `source_values`; pipeline tidak mengganti `NA` menjadi angka atau menyulap label menjadi outcome moisturizer. Dataset ini adalah shampoo rinse-off dengan horizon observasi sekitar 36 jam, sehingga bukan dataset F3 minggu-4 hingga minggu-12.

## Integrasi seamless, tanpa leakage

Jalankan dari root repository:

```bash
python3 scripts/build_data_pilot.py build
python3 scripts/build_full_dataset.py build
python3 scripts/ingest_open_sources.py fetch-build
python3 scripts/build_public_evidence.py build
python3 scripts/build_training_views.py build
```

`build_training_views.py` membangun view konsumsi bersama secara otomatis:

- `data/training/f1_evidence_catalog.jsonl`: 15 dokumen evidence publik bersitasi ditambah 420 dokumen demo train.
- `data/training/f3_forecast_train.jsonl`: seluruh 515 pasangan feature/label yang eligible, tetap membawa field split.
- `data/training/f3_train.jsonl`, `f3_validation.jsonl`, dan `f3_test.jsonl`: view partition siap konsumsi model tanpa random row split ulang.
- `data/training/training_report.json`: hitungan dan kebijakan inclusion/exclusion.

Saat ini F3 berisi **515** row `synthetic_demo` dan **0** row publik. Dari 600 trajectory penuh, 85 scenario `borderline` dikeluarkan dari supervised binary forecast karena outcome-nya uncertain. Ini disengaja dan benar: 15 record paper adalah snapshot cross-sectional proxy, tidak punya observasi hingga landmark minggu ke-4 atau outcome minggu ke-12. Mereka dicatat di `data/public_observed/f3_excluded_candidates.jsonl`, bukan dibuang atau dipalsukan menjadi label.

Ketika paper/dataset baru benar-benar mempunyai formula atau process, checkpoint sebelum/hingga minggu ke-4, outcome sesudahnya hingga minggu ke-12, dan unit split sumber/paper yang jelas, tambahkan adapter baru dengan `f3: eligible`. Builder train/test harus split berdasarkan **source/paper group**, bukan mengacak formulasi dari paper yang sama ke train dan test.

## Validasi

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_data_pilot.py validate
python3 scripts/ingest_open_sources.py validate
python3 scripts/build_public_evidence.py validate
python3 scripts/build_training_views.py validate
```

Validator memeriksa replay dari source, provenance DOI/lisensi/hash, manifest SHA-256, join feature-label, dan penolakan entry publik yang belum memenuhi kontrak F3. Tidak ada model ML yang dilatih oleh pipeline ini.
