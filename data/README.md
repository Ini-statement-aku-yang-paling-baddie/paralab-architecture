# data/ — Artefak Dataset FormuLab V4

Semua file di sini dihasilkan oleh `FormuLab-V4-Corpus-Generator.ipynb` (source: `notebooks/corpus_v4_source.py`).
Regenerasi deterministik: seed `42`. Jalankan ulang notebook untuk mereproduksi persis.

> ⚠️ **Semua data sintetis** (`data_origin: synthetic_demo`, `scientific_validation_status: not_validated_for_production`).
> Tidak merepresentasikan data riset Paragon maupun produk nyata. Nilai numerik dari generator deterministik;
> narasi dibatasi oleh seed (tidak ada angka yang dikarang LLM).

## Domain (V4 §1.1)

Satu vertical saja: **moisturizer gel-cream O/W untuk kulit berminyak**.
Variasi dibuat di dalam keluarga ini (sistem aktif, emulsifier, rasio fase minyak, thickener, parameter proses).

## Peta konsumsi per tim

| File | Konsumen | Peran |
|---|---|---|
| `formula_seeds.jsonl` | **tim F3** (trajectory generator) | **KONTRAK**: 600 trial, tiap trial punya `scenario_family` + `expected_outcome`/`expected_failure_mode`/`expected_failure_week`. Trajectory numerik harus konsisten dengan keluarga skenario ini |
| `evidence_corpus.jsonl` | **tim web** + F1 | 600 evidence card (judul, observasi, pelajaran, outcome, `source_id`) untuk render dashboard & kartu hasil pencarian |
| `evidence_rag_text.jsonl` | F1 retrieval | teks siap-embed per `source_id` |
| `embeddings_formulab.npy` | F1 retrieval | matriks 600×384 (dihasilkan notebook) |
| `rag_dev_queries.jsonl` | evaluasi F1 | 40 query berlabel (`label_source: generated`) untuk tuning |
| `rag_blind_test_queries.jsonl` | evaluasi F1 | 10 query ditulis manusia — **`relevant_source_ids` masih kosong, perlu pelabelan manusia** (§12.2) |
| `ingredient_master.json` | F1 + F2 + F5 | ontology bahan kanonis (80 bahan, `ingredient_id` stabil) |
| `formulation_rules.json` | **F2** | 165 aturan versioned (`rule_id`, `rule_version`, `source_id`) |
| `f2_screen_example.json` | tim web | **contoh** output kontrak F2 (bentuk API response) |
| `metadata.json` | semua | ringkasan, distribusi, disclaimer, peran file |

## Kontrak antar-track

1. **F1 ↔ F3**: `source_id` di evidence corpus dipakai F3 sebagai `evidence_ids` (V4 §7.3).
   Formula seed yang sama menjadi dasar trajectory, sehingga relasi evidence↔forecast konsisten *by construction*.
2. **F2 → F3**: `derived_features` dari `f2_guardrail_v4.py` (`electrolyte_thickener_risk`, dll) memakai
   `feature_schema_version = stability-sentinel-v1` — skema ini harus identik saat training dan inference F3.
3. **F5 → F2**: fuzzy-match nama bahan hasil STT memakai `aliases` di `ingredient_master.json`
   (sudah diuji untuk typo seperti `niasinamida` → `ING:NIACINAMIDE`).

## Catatan kualitas yang diketahui

- Retrieval semantik murni (MiniLM) belum diskriminatif untuk query berbasis *failure mode*
  (contoh: query "fase minyak dan air memisah" mengembalikan kasus `pass` di top-5).
  → Ini alasan teknis F1 memakai **hybrid retrieval** (lexical + dense + RRF) sesuai V4 §7.2, bukan dense saja.
- 116/200 judul jurnal unik (58%). Wajar karena semua proyek berada di satu keluarga produk.
- `literature` di luar scope: tidak ada dataset stabilitas longitudinal kosmetik yang publik —
  karena itu trajectory (tim F3) digenerate dengan kalibrasi, bukan diunduh.

## Disclaimer

Status halal/BPOM/batas konsentrasi di KB adalah **pendekatan data publik** untuk prototipe dan
**bukan** pengganti verifikasi ke daftar resmi MUI / BPOM / CosIng. Wajib diverifikasi ulang
sebelum dipakai untuk keputusan nyata.
