# FormuLab AI — Rencana Korpus & Distilasi (v1.2)

> **Konteks update (2026-09-17):** dokumen ini kini selaras dengan `ARCHITECTURE-V4.md` — korpus V4 (200 jurnal / 600 trial, satu vertical O/W gel-cream) ada di `data/` dan sudah terealisasi via `FormuLab-V4-Corpus-Generator.ipynb`. Bagian yang masih aktif dan menjadi kontrak distilasi: **§3 (prinsip seed-driven), §4a/§4b (template prompt tugas), §5 (volume & split), §6 (anti-pattern)**. Struktur korpus §1 mengikuti `data/evidence_corpus.jsonl` (sudah berbeda dari yang tertulis di sini — lihat `data/README.md`).
>
> **PEMBAGIAN KERJA:** track ini (F1 + F2) sudah selesai sampai KB + korpus + F2 contract; **F5 STT = teammate**, **web UI = teammate**, **F3/trajectory = Arlen (selesai, `data/full_synthetic/`)**. **Distilasi LLM = track ini.** Teacher model: **GPT-5.5 via API** (akses disediakan teman) — hanya untuk GENERATE training set, bukan inference demo (demo = model student lokal, narasi on-premise V4 §8).
>
> **Status: SIAP DIEKSEKUSI** — korpus sudah ada, tinggal generate training set + LoRA.

---

## 1. Struktur Entri Jurnal Sintetis (unit korpus F1)

Satu entri = satu file JSON. Target: **200 entri** (cukup untuk demo RAG tanpa biaya generate besar).

```json
{
  "id": "J-2024-017",
  "tahun": 2024,
  "peneliti": "Tim Riset 3",
  "judul": "Gel-Cream Oil Control Wajah Pria untuk Aktivitas Outdoor",
  "kategori_produk": "moisturizer",
  "target_kulit": "berminyak",
  "konteks_pakai": "siang_hari_outdoor",
  "segmen": "menengah",
  "status": "sedang_berjalan | selesai | draft",
  "target_spec": "Tekstur ringan non-lengket, oil control ≥8 jam, finish matte",
  "formula": [
    {"bahan": "Niacinamide", "pct": 4.0, "fungsi": "oil control"},
    {"bahan": "Zinc PCA", "pct": 1.0, "fungsi": "sebum regulation"},
    {"bahan": "Squalane", "pct": 2.0, "fungsi": "emolien ringan"}
  ],
  "trial": [
    {"trial_ke": 1, "ph": 5.4, "viskositas_cps": 18000, "hasil": "agak lengket, oil control 5 jam"},
    {"trial_ke": 2, "ph": 5.6, "viskositas_cps": 22000, "hasil": "target tercapai"}
  ],
  "observasi_narasi": "Trial 1 menunjukkan lengket setelah 2 jam pemakaian. Penambahan dimethicone ringan pada trial 2 memperbaiki slip.",
  "pelajaran": "Dimethicone 1.5% efektif mengurangi lengket tanpa menaikkan viskositas melebihi batas fill-pack.",
  "flag_kepatuhan": []
}
```

**Distribusi yang dijaga (biar korpus tidak bias):**
- Kategori: moisturizer 40%, sunscreen 15%, serum 15%, shampoo 10%, sabun wajah 10%, toner 10%
- Status: selesai 50%, sedang_berjalan 30%, draft 20% (yang "sedang berjalan" penting untuk fitur penanda koordinasi di Layar 2)
- Min. 8 entri "dekat" dengan skenario demo (moisturizer pria berminyak outdoor) dengan kemiripan bertingkat — satu dari ini jadi "MattePro" di demo
- Min. 5 entri berisi kegagalan spesifik (lengket, pemisahan fase, iritasi) — supaya F1 bisa menemukan "kesalahan yang pernah dialami tim lain"

## 2. KB Bahan (dipakai F2 + fuzzy-match F5)

Satu file JSON/CSV, target **80 bahan** populer skenario demo:

```json
{
  "inci": "Niacinamide",
  "alias": ["vitamin B3", "nicotinamide"],
  "fungsi": ["oil control", "brightening"],
  "rentang_pct": [2.0, 5.0],
  "halal_mui": "halal",
  "bpom": "diizinkan",
  "alergen": false,
  "komedogenik": 0,
  "kompatibilitas": [
    {"dengan": "Vitamin C (L-AA)", "status": "konflik", "alasan": "pH kerja berbeda, risiko degradasi"},
    {"dengan": "Zinc PCA", "status": "sinergetik"}
  ]
}
```

Field `alias` dipakai juga oleh F5 untuk fuzzy-match hasil STT.

## 3. Template Prompt — Generate Korpus Jurnal (teacher LLM)

**Strategi:** kita generate seed secara programatik (Python), LLM hanya menulis field naratif. Satu panggilan = satu entri.

```
[SYSTEM]
Anda penulis teknis R&D kosmetik personal care di Indonesia. Anda menulis
entri jurnal praktikum yang realistis dan faktual sesuai seed yang diberikan.
ATURAN:
1. JANGAN mengubah angka (persentase, pH, viskositas) dari seed.
2. Bahasa Indonesia baku, istilah teknis boleh INCI latin.
3. observasi_narasi: 2–4 kalimat, gaya catatan peneliti sungguhan
   (termasuk keraguan/kondisi lapangan bila seed menyebut kegagalan).
4. pelajaran: 1–2 kalimat, action-oriented, mengacu hasil trial.
5. Output HANYA JSON valid mengikuti skema entri.

[USER]
Seed entri:
- id: {id}
- kategori: {kategori}, target kulit: {target_kulit}, konteks: {konteks}, segmen: {segmen}
- status: {status}
- formula seed: {formula_json}
- trial seed: {trial_json}
- arah narasi: {arah}   # salah satu dari: "sukses mulus" | "gagal lalu berhasil" | "gagal & berjalan"
- detail kegagalan (bila ada): {gagal_detail}

Tulis field berikut: judul, target_spec, observasi_narasi, pelajaran.
```

**Seed generator (Python, deterministik):** kombinasi `kategori × target_kulit × konteks × segmen × arah_narasi` di-sample dengan seed tetap (`random.seed(42)`) → 200 seed unik → loop panggil API teacher → simpan JSON per entri. Duplikat dicek via hash atas (formula + trial seed).

## 4. Template Prompt — Training Set LoRA

### 4a. Tugas Summarization (untuk F1)

```
[SYSTEM]
Anda asisten riset FormuLab AI. Ringkas pola entri jurnal berikut dalam
2–3 kalimat Bahasa Indonesia untuk peneliti yang mempertimbangkan proyek serupa.
Sebutkan: apa yang dicoba, hasil akhirnya, dan satu pelajaran kunci.
JANGAN menyebut angka persentase formula (ringkasan pola, bukan resep).

[USER]
Entri jurnal: {entri_json}
Query peneliti: "{query_pencarian}"

[ASSISTANT (target output)]
{ringkasan_2_3_kalimat}
```

`query_pencarian` di-generate dengan variasi phrasing (3–5 variasi per entri) supaya model belajar robust terhadap kata yang berbeda dari entri asli — ini kriteria penerimaan F1 di PRD ("query dengan kata berbeda tetap menemukan entri relevan").

### 4b. Tugas Entity Extraction (untuk F5)

```
[SYSTEM]
Anda parser observasi lab FormuLab AI. Ubah ucapan peneliti menjadi JSON.
Skema: {"bahan": str|null, "konsentrasi_pct": float|null, "observasi": str|null,
"parameter": {str: float}|null}
ATURAN:
1. Field yang tidak disebut → null. JANGAN menebak.
2. Angka lisan → numerik ("dua persen" → 2.0, "lima koma delapan" → 5.8).
3. Nama bahan → bentuk INCI standar jika dikenali; jika tidak dikenali,
   tulis apa adanya dan set "kondisional": true di objek terluar.

[USER]
Transkrip: "{hasil_stt_dengan_typo}"

[ASSISTANT (target output)]
{"bahan": "Niacinamide", "konsentrasi_pct": 2.0,
 "observasi": "larutan agak keruh", "parameter": {"ph": 5.8}}
```

**Kunci kualitas:** transkrip input harus **disimulasikan dengan noise khas STT Indonesia** — typo fonetik ("niasinamida", "gliseren"), angka lisan, urutan acak. Bukan teks bersih. Kalau dilatih di teks bersih, model gagal persis di kondisi nyata.

### 4c. Volume & split

| Tugas | Jumlah contoh | Split |
|---|---|---|
| Summarization (4a) | ~600 (200 entri × 3 variasi query) | train 480 / val 60 / test 60 |
| Extraction (4b) | ~800 (100 pola ucapan × 8 noise) | train 640 / val 80 / test 80 |

### 4d. Evaluasi sebelum LoRA

- Summarization: 30 sampel direview manual tim (apakah ringkasan jujur terhadap entri, tidak mengarang angka).
- Extraction: uji 20 transkrip ber-noise terhadap teacher zero-shot **sebelum** generate dataset — kalau teacher sendiri gagal parse, pola ucapannya terlalu ekstrem dan harus diubah. Ini quality gate termurah yang bisa dilakukan.

## 5. Anti-pattern yang dihindari

1. ❌ Minta LLM besar "buat 200 jurnal kosmetik" dalam satu prompt — hasilnya repetitif, angka tidak konsisten, susah dikontrol distribusinya.
2. ❌ Latih extraction di transkrip bersih — gagal saat ketemu output STT sungguhan.
3. ❌ Ringkasan menyebut resep lengkap — melanggar K5 PRD (visibilitas lintas tim).
4. ❌ Korpus tanpa entri gagal — F1 jadi tidak bisa menampilkan "pola kegagalan", yang justru jadi value proposisi utamanya.

## 6. Checklist eksekusi

- [ ] Script seed generator (Python, deterministik, `seed=42`)
- [ ] 80 bahan KB (manual kurasi + verifikasi ke cekbahan.id/CosIng)
- [ ] Panggil API teacher untuk 200 entri korpus (~200 calls)
- [ ] Quality gate: review 30 entri acak
- [ ] Generate training set 4a + 4b (~1.400 contoh)
- [ ] Quality gate 4d (uji zero-shot teacher)
- [ ] Embedding seluruh korpus + index (F1 siap dipasang ke prototipe)

---

## 7. Spesifikasi Eksekusi Distilasi (kontrak dengan teacher = GPT-5.5 via API)

> Bagian ini adalah **spesifikasi kerja** untuk notebook distilasi. Semua input sudah ada di `data/`.

### 7.1 Dua tugas yang dilatih

| Tugas | Melayani | Input (dari `data/`) | Target output model student |
|---|---|---|---|
| **A. Evidence summarization** | F1 (ringkasan kartu) | `evidence_corpus.jsonl` (600 record) | ringkasan 2-3 kalimat pola trial, TANPA menyebut konsentrasi persentase (K5) |
| **B. Voice-log extraction** | F5 (teammate, STT) | `full_synthetic/derived/f5_examples.jsonl` (4.200) | JSON kanonis: `{checkpoint_id, measurements{ph,viscosity_cp}, observations{appearance}, field_confidence{...}, requires_confirmation:true}` — SKEMA HARUS SAMA dengan `f5_examples.jsonl` (kontrak F5 V4 §10.2) |

### 7.2 Volume, split, seed

- Task A: ~600 contoh (1 per evidence record) + 2 parafrase query → ~1.400
- Task B: subsample 800 dari 4.200 (jaga distribusi `observed/missing/invalid/uncertain`)
- Split 80/10/10 **by journal family / trial** (jangan random row-level, §12.2 V4); seed 42
- Setiap record training menyimpan `source_id` lineage ke data aslinya

### 7.3 Aturan teacher (V4 §6.5 — tidak bisa ditawar)

1. Teacher **TIDAK BOLEH** mengarang angka: pH, viskositas, konsentrasi, minggu gagal, outcome, keputusan regulatory — semua angka disalin dari seed/data terstruktur
2. Teacher hanya menulis: judul, narasi observasi, pelajaran, parafrase query, draft penjelasan
3. Untuk Task B: teacher menghasilkan variasi transcript bicara (typo fonetik, angka lisan "dua persen" → 2.0) — label tetap dari `f5_examples.jsonl`
4. Zero-shot gate: uji 20 sampel pola terkeras (transkrip berisik) SEBELUM bayar full generation — kalau teacher gagal, perbaiki pola, bukan prompt-nya

### 7.4 Student & runtime

| Aspek | Pilihan | Alasan |
|---|---|---|
| Base model | **Qwen2.5-1.5B-Instruct** (fallback: Llama-3.2-3B) | muat LoRA di T4 Kaggle gratis, cukup untuk tugas sempit |
| Method | LoRA (peft + trl, SFT) | standar, cepat, checkpoint kecil |
| Training | Kaggle GPU T4, ~1-2 jam per tugas | preferensi tim (training di Kaggle) |
| Export | GGUF (llama.cpp, Q4_K_M) + tokenizer | jalan lokal laptop demo tanpa GPU |
| Serving demo | llama-cpp-python / ollama, prompt per tugas | inference lokal, mendukung narasi on-premise |

### 7.5 Definition of Done distilasi

- [ ] Training set A + B tergenerate via GPT-5.5 API, semua angka traceable ke seed (`source_id` di tiap record)
- [ ] Quality gate 7.3.4 lolos (20/20 sampel terkeras)
- [ ] LoRA A dan B selesai training di Kaggle, loss curve tidak overfit
- [ ] Evaluasi student vs teacher pada holdout: Task A (ringkasan jujur, tanpa % konsentrasi), Task B (field accuracy ≥95%, `requires_confirmation` selalu true)
- [ ] GGUF exported + smoke test inference lokal (tanpa internet)
- [ ] Model & training report di-commit (`models/`, `reports/`), hash tercatat di manifest

