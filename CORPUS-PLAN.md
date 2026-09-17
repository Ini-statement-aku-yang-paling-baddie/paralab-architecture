# FormuLab AI — Rencana Korpus Dummy & Training Set (v1)

> Pelengkap `ARCHITECTURE.md` §3 (F1) dan §8 (distilasi). Dokumen ini mendefinisikan struktur korpus jurnal sintetis (untuk embedding F1) dan template prompt untuk meng-generate training set (untuk LoRA F1+F5).
> Prinsip: **teacher LLM besar tidak menulis acak** — ia hanya menulis narasi di atas *seed terstruktur* yang kita tentukan. Ini menjaga konsistensi angka, mencegah duplikat, dan membuat korpus bisa diregenerasi deterministik.

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
