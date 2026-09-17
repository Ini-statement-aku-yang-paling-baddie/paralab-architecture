# Pipeline data pilot ParaLab

## Status dan batas keselamatan

Pipeline **sudah dijalankan**, bukan hanya rencana. Implementasi menggunakan Python 3 stdlib, seed default `17`, tanpa unduhan, training ML, pembuatan embedding, LLM, audio, atau gambar. Pilot ini menggantikan target ekspansi 600 trial pada tahap implementasi data saja; tidak mengubah `ARCHITECTURE-V4.md`.

**Seluruh trajectory merupakan simulasi belum direview. Jangan meracik formula ini.** Total formula 100% hanya menjamin kelengkapan aritmetika: emulsifier dan preservative masih placeholder tanpa identitas/spesifikasi. Formula tidak menjamin emulsi O/W yang dapat dibuat, keamanan, efektivitas, kompatibilitas, atau compliance. Tidak ada `human_verified: true` yang dibuat.

Corpus lama tetap terpisah dari simulasi baru. Narasi lama, fungsi bahan, hasil trial, dan konsentrasi tidak dinaikkan menjadi evidence ilmiah. `authentic_rules.json` sengaja mempunyai daftar rules dan sumber kosong. `simulation_assumptions.json` menjelaskan asumsi buatan; **tidak ada sitasi atau aturan ilmiah yang dikarang**. Batas pH 0–14 dan viskositas 0–1.000.000 cP adalah sanity input perangkat lunak, bukan acceptance criteria stabilitas.

## Menjalankan

Dari direktori repositori:

```bash
python3 -m unittest discover -s tests -p test_data_pilot.py -v
python3 scripts/build_data_pilot.py build
python3 scripts/build_data_pilot.py validate
```

Output alternatif/seed eksplisit:

```bash
python3 scripts/build_data_pilot.py build --output /tmp/paralab-pilot --seed 17
python3 scripts/build_data_pilot.py validate --output /tmp/paralab-pilot
```

Exit code `0` berarti valid; selain itu kegagalan. `build` menulis ulang artefak turunan di direktori output dan memvalidasinya melalui pembacaan kembali. Gunakan direktori khusus; jangan simpan artefak lain di sana. Snapshot raw atau hash sumber yang berbeda dari build sebelumnya ditolak, bukan ditimpa diam-diam. Tidak ada opsi ekspansi 600 trial.

## Satu sumber kanonis

Urutan: audit corpus → alias tidak terverifikasi → penetapan keluarga/split proyek → formula/trial → series storage → checkpoint/outcome → view F1/F3/F5 → validasi → manifest SHA-256.

- `P-001`–`P-012`: proyek, semuanya domain demo `o_w_gel_cream_moisturizer`, target `oily`.
- `FAMILY-01`–`FAMILY-06`: grup varian formula; dua proyek per keluarga. Empat keluarga train, satu validation, satu test. Formula identik dalam keluarga tetap satu partition. Keluarga bukan klaim independensi kimia.
- `P-001-FORM1`: snapshot formula; dua per proyek, komponen dan proses tersimpan terstruktur.
- `P-001-T1`: trial; dua per proyek.
- `P-001-T1-S25` / `S40`: **dua series storage per trial**, bukan dua proyek atau sampel independen.
- `…-W00`, `…-W01`, `…-W02`, `…-W04`, `…-W06`, `…-W08`, `…-W12`: checkpoint teramati.
- `…-OUT`: outcome per series. Endpoint memiliki foreign key checkpoint.

Tabel JSONL di `data/canonical/`: `projects`, `formulas`, `trials`, `observation_series`, `checkpoints`, `outcomes`. Setiap entitas memuat ID, provenance generator/seed/assumption, label synthetic, status belum tervalidasi, dan `human_verified: false`. Semua tabel kanonis/turunan terikat project dan split; proyek sendiri memakai `id` sebagai project key.

Tanggal awal simulasi tetap `2026-01-01`, ditambah minggu × 7 hari. Hanya checkpoint hingga observasi terakhir yang dibuat. Failure minggu 2 atau 8 menghentikan series itu; **tidak ada pengukuran sesudah stop**. Trial dapat memiliki kondisi storage dengan outcome berbeda. Right censor minggu 6 bukan pass; uncertain di minggu 12 bukan label biner.

## Berkas dan kontrak konsumsi

| Berkas di `data/` | Fungsi |
|---|---|
| `raw/corpus_paralab.json` | Salinan byte-identik corpus asli; tidak diedit |
| `audit_original.json` | Hitungan sumber, total formula per ID, warning provenance |
| `ingredient_aliases.json` | 23 nama/alias impor; ID `ALIAS-*`, source IDs dan hash; **tanpa authoritative properties** |
| `demo_components.json` | Enam ID `DEMO:*` untuk formula buatan; terpisah dari alias asli, belum terverifikasi |
| `simulation_assumptions.json` | Asumsi skenario dan batas sanity; bukan rule ilmiah |
| `authentic_rules.json` | Registry evidence/rule autentik kosong secara eksplisit |
| `schema_contract.json` | Kontrak JSON machine-readable: field wajib, foreign key, enum, range, missingness, forecast allowlist |
| `metadata.json` | Seed, versi, hash skrip dan sumber, scope, limitations |
| `metrics.json` | Hitungan nyata dan kesalahan validator; **bukan metrik ML** |
| `sha256_manifest.json` | SHA-256 semua file output kecuali dirinya; hash kedua sumber asli |

`schema_contract.json` adalah **schema contract semantik**, bukan klaim kompatibilitas JSON Schema Draft. CLI menjalankan validasi relasi/semantik kontrak; tidak memerlukan library eksternal. ID komponen formula harus terdapat dalam registry demo. Alias yang kebetulan cocok namanya tetap kandidat belum diverifikasi, bukan pemetaan INCI yang disahkan.

### F1: journal dan corpus aman untuk evaluasi integrasi

- `derived/journal_documents.jsonl`: seluruh 48 dokumen, masing-masing diberi split. Dokumen historis boleh merangkum outcome akhir, dengan source IDs.
- **Hanya** `derived/f1_train_corpus.jsonl` (32 dokumen train) boleh menjadi corpus retrieval untuk evaluasi holdout. Jangan mengindeks seluruh journal lalu mengklaim holdout bersih.
- Catatan checkpoint awal dirender hanya dari week, nilai/quality/raw, dan appearance checkpoint itu. Tidak ada future outcome di catatan tersebut.
- Dokumen historis **bukan input fitur F3**; teks dan outcome historis tidak masuk feature snapshot. Ini corpus uji integrasi sintetis, bukan evidence lab dan bukan benchmark retrieval yang sudah dievaluasi. Belum ada query manusia atau metrik ranking.

### F3: landmark 4, horizon 12

- `derived/forecast_features.jsonl`: input terstruktur formula/proses/storage dan observasi minggu 0,1,2,4. `checkpoint_ids` memberikan lineage. Tidak menyimpan label, failure week, skenario, atau narasi jurnal.
- `derived/forecast_labels.jsonl`: target `failed_by_12`, join melalui `feature_id`; label berasal dari skenario, bukan verifikasi manusia.
- At-risk berarti belum gagal pada/hingga minggu 4. Event failure diketahui setelah minggu 4 dan sebelum/hingga 12 tetap label positif meskipun series dihentikan pada minggu 8. Pass perlu follow-up sampai minggu 12.
- `derived/forecast_censored.jsonl`: right censor terpisah, menyimpan feature snapshot awal dan last observed week untuk kemungkinan analisis survival kelak, **tanpa label biner**. Jangan memperlakukan last observed week sebagai fitur prediksi landmark.
- `derived/forecast_excluded.jsonl`: early failure, uncertain, atau observasi kritis tidak lengkap/invalid; alasan eksplisit.
- Kebijakan konservatif: semua pH/viskositas minggu 0–4 harus valid. Tidak mengimputasi missing atau mengubah invalid menjadi angka valid.
- Konsumsi model hanya empat kelompok allowlist: `temperature_c`, `formula_concentrations`, `process`, `observations`. ID, split, seed, provenance, checkpoint IDs adalah metadata, **bukan fitur training**. Penamaan ID dapat berkorelasi dengan jadwal skenario.
- Split ditetapkan sebelum semua turunan. Bentuk skenario dan bahan dasar masih dibagi antarkeluarga; split demo ini tidak membuktikan generalisasi ke formulasi atau lab lain.

### F5 dan lampiran

`derived/f5_examples.jsonl` memuat satu transkrip teks deterministik per checkpoint dan target patch yang identik dengan nilai, quality, raw, missing reasons, appearance, week, tanggal kanonis. `requires_confirmation: true`; bukan rekaman audio atau hasil STT yang telah diuji. Tidak ada penulisan observasi nyata tanpa konfirmasi.

`derived/image_manifest.jsonl` kosong secara sengaja. **Tidak ada path gambar palsu**, file gambar, label CV, atau klaim performa visual.

### Missingness dan negative cases

- `observed`: angka finite dalam sanity range, sama dengan raw.
- `missing`: nilai dan raw `null`, quality `missing`, alasan `not_recorded`.
- `invalid`: nilai normalisasi `null`, raw string salah (contoh `99.0` untuk pH), quality `invalid`, alasan `out_of_range`. Input buruk tetap dapat diaudit, bukan dipakai sebagai measurement.
- `uncertain`: appearance/outcome eksplisit; tidak dipaksa menjadi pass/fail.

## Validasi dan hasil eksekusi

Delapan metode unittest lulus, termasuk subtest mutasi. Pengerjaan dilakukan dalam slice RED → GREEN: audit, generator, validator, turunan, CLI ekspor, penguatan kontrak/provenance, coverage split, lalu penolakan field future yang disisipkan. Kegagalan diuji sebelum implementasi tiap slice.

Validator menguji: ID unik, field wajib, join dan kepemilikan proyek, komponen formula, total 100%, finite/range, tanggal/jadwal monotonic, grouping keluarga/storage/split, provenance/seed, larangan verifikasi manusia palsu, satu outcome per series, endpoint/status/censor, tidak ada observasi pascastop, kesamaan catatan dengan checkpoint, missingness, dan larangan field proses/measurement di luar kontrak. Turunan divalidasi dengan exact replay kanonis sehingga perubahan transkrip, label, corpus split, atau future checkpoint ditolak. CLI juga memeriksa hash file, raw, dan kedua sumber asli.

Hasil default seed 17:

| Entitas/artefak | Jumlah |
|---|---:|
| Proyek / formula / trial | 12 / 24 / 24 |
| Series storage / outcome | 48 / 48 |
| Checkpoint / contoh F5 | 282 / 282 |
| Dokumen semua split / corpus F1 train | 48 / 32 |
| Feature / label supervised | 19 / 19 |
| Censored terpisah / excluded lain | 6 / 23 |
| Outcome passed / failed / right-censored / uncertain | 17 / 18 / 6 / 7 |
| Nilai observed / missing / invalid | 548 / 8 / 8 |
| Proyek train / validation / test | 8 / 2 / 2 |
| Label train pass/fail | 5 / 7 |
| Label validation pass/fail | 1 / 2 |
| Label test pass/fail | 3 / 1 |
| Kesalahan validator | 0 |

Audit corpus asli: **200 entri, 200 ID unik, 492 trial, 90 moisturizer, 23 nama bahan, 200 formula parsial**. Bukan sumber longitudinal siap training.

Build diulang dan **24 file output identik byte/hash**, termasuk manifest. Test CLI juga membandingkan seluruh byte sebelum/sesudah rerun di temporary directory dan memastikan perubahan checkpoint menyebabkan exit nonzero. Manifest bukan tanda tangan kriptografis; ia mendeteksi perubahan terhadap snapshot, bukan menjamin integritas jika manifest ikut diganti penyerang.

Hash sumber terjaga dan dibandingkan dengan Git HEAD:

```text
corpus_paralab.json
40302c85d2018208e3a8fda23aeabd92f37c38d84e7cb3c426c03d4e9d3e3856
embeddings_paralab.npy
a02ba85cc669d3dd33f218cd0b57c4b4bad56b8258cb1e93d8b00940efde8373
```

Embedding asli hanya dibaca untuk hashing; tidak disalin/dipakai ulang sebagai embedding corpus pilot. Formula dan numeric trajectory baru **tidak diturunkan sebagai kebenaran kimia dari corpus lama**. Ukuran kecil dan jadwal skenario buatan hanya cukup untuk smoke test workflow. Human review, evidence publik terverifikasi, formula lab yang layak, pemisahan permission produksi, evaluasi retrieval/STT/ML, dan validasi ilmiah tetap belum dilakukan.
