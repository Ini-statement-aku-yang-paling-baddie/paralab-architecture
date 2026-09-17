# FormuLab AI — Draft Arsitektur Teknis (v2)

> UI Hackathon 2026 · Sub-tema: AI untuk Riset & Prediksi Formulasi · Kolaborasi: ParagonCorp
> Status: draft keputusan tim — F1, F2, F3, F5 didefinisikan; F4 ditunda (hold) sampai tiga fitur lain solid.
> Prinsip arsitektur: **Jurnal Praktikum = single source of truth** (sesuai dokumen Workflow & Logika) — semua modul hanya baca/tulis ke situ, tidak ada modul yang menyimpan salinan data sendiri.

---

## 1. Diagram Arsitektur

```
                         ┌─────────────────────────────────────┐
                         │   JURNAL PRAKTIKUM (single source    │
                         │   of truth: resep, hasil uji, foto,  │
                         │   observasi, status entri)           │
                         └──┬───────────┬───────────┬──────┬───┘
                            │           │           │      │
              ┌─────────────┘           │           │      └────────────┐
              │                         │           │                   │
     ┌────────▼────────┐   ┌────────────▼──┐  ┌─────▼────────┐  ┌───────▼──────────┐
     │ F1 Semantic     │   │ F2 Health     │  │ F3 Stability │  │ F4 Next-Best-    │
     │ Copilot         │   │ Check         │  │ Scanner      │  │ Experiment       │
     │─────────────────│   │───────────────│  │──────────────│  │ (HOLD — lihat §7)│
     │ Embedding model │   │ Rules +       │  │ CNN kecil    │  │ Surrogate model  │
     │ (lokal)         │   │ lookup KB     │  │ fine-tuned   │  │ + acquisition    │
     │ + LLM distilasi │   │ (deterministik│  │ di dataset   │  │ fn (ML klasik)   │
     │ utk ringkasan   │   │ tanpa ML)     │  │ FLUID        │  │                  │
     └────────▲────────┘   └───────────────┘  └──────────────┘  └──────────────────┘
              │
     ┌────────┴─────────┐        ┌──────────────────────────────────────┐
     │ F5 Voice Logging │        │ KNOWLEDGE BASE statis (dummy realistis)│
     │ distil-whisper → │        │ • kompatibilitas bahan (pasangan +     │
     │ LLM distilasi    │        │   aturan pH/emulsifier)                │
     │ (ekstraksi ent.) │        │ • daftar halal MUI, restricted BPOM,   │
     └──────────────────┘        │   alergen                              │
                                 │ • properti bahan (komedogenik, INCI)   │
                                 │ • korpus jurnal historis sintetis      │
                                 │   (untuk F1)                           │
                                 └──────────────────────────────────────┘
```

## 2. Ringkasan Komputasi

| Komponen | Jenis | Ukuran kasar | Dipakai oleh | Status |
|---|---|---|---|---|
| Embedding model (multilingual, mis. sentence-transformers) | Encoder kecil | ~100M | F1 | ✅ |
| **LLM distilasi (satu-satunya)** | Decoder 1.5–3B + LoRA | ~3B | F1 (ringkasan) + F5 (ekstraksi entitas) | ✅ inti narasi |
| distil-whisper (STT terdistilasi) | STT kecil | ~750M | F5 | ✅ bonus narasi |
| Classifier stabilitas | CNN kecil fine-tuned (FLUID) | <50M | F3 | ✅ |
| Surrogate model + acquisition | Random Forest / GP | <1M | F4 | ⏸ hold |
| KB rules | Lookup + aturan | statis | F2 (+ fuzzy-match utk F5) | ✅ |

Semua komponen jalan lokal (on-premise) — tanpa GPU berat. Ini fondasi narasi privasi (menjawab K5 PRD).

## 3. F1 — Semantic Research Copilot

- **Pipeline:** query bebas → embedding (lokal) → cosine similarity ke korpus jurnal sintetis → top-k → reranking → LLM distilasi merangkum pola (2–3 kalimat).
- **Reranking:** `skor = 0.7·kemiripan_semantik + 0.2·kebaruan + 0.1·kedekatan_kategori`.
- **Korpus:** 150–300 entri jurnal sintetis (lihat `CORPUS-PLAN.md`). Kualitas korpus = kendali penuh tim, karena data internal Paragon tidak tersedia.
- **Perilaku khusus** (dari Alur-Layar): entri mirip dengan status "sedang berjalan" ditampilkan dengan penanda koordinasi antar-tim, bukan sekadar ringkasan.

## 4. F2 — Formulation Health Check (tanpa ML — kekuatan, bukan kelemahan)

- **Pipeline:** baris bahan diketik → normalisasi nama INCI (fuzzy match ke KB) → pengecekan berurutan **fail-fast**: kompatibilitas → halal MUI → BPOM/alergen → badge hijau/kuning/merah + saran substitusi.
- **Deterministik & auditable** — sesuai K2 PRD: keputusan kepatuhan harus bisa dipertanggungjawabkan, jadi rule-based adalah pilihan desain yang benar, bukan kekurangan.
- **KB prototipe:** 50–100 bahan populer dengan atribut lengkap, cukup untuk skenario demo (moisturizer oil-control pria).

## 5. F3 — Stability & Texture Scanner

- **Dataset utama: FLUID** (IEEE BigMM 2022) — 47.000+ foto formulated liquid, dilabel ahli, 5 kelas: `stable / phase_separation / creaming / cracking / flocculation`. Publik: `github.com/mauriziodemiccounina/FLUID`. *(QC dataset sedang berjalan terpisah.)*
- **Pipeline level 1 (wajib):** CNN kecil (ResNet/ViT-tiny) fine-tune klasifikasi 5 kelas → mapping ke skor 0–100 → pita Stabil / Waspada / Berisiko → plot tren antar-batch.
- **Pipeline level 2 (bonus):** deteksi droplet → DSD → coefficient of variation sebagai fitur tambahan (dataset droplet anotasi dari paper Chem. Eng. 2024, ±120 gambar mikroskopis publik).
- **Catatan jujur:** FLUID = foto sampel softener, bukan mikroskopis kosmetik — tapi kategori kegagalan fisiknya identik dengan kebutuhan F3. Disebutkan transparan di pitch.
- Training dijalankan di Kaggle (sesuai preferensi tim).

## 6. F5 — Hands-Free Voice Logging

- **Pipeline:** push-to-talk → **distil-whisper** (STT) → transkrip → **LLM distilasi** ekstraksi entitas `{bahan, konsentrasi%, observasi, parameter}` → field jurnal terisi + confidence per field → field low-confidence di-highlight kuning untuk konfirmasi manual.
- **Temuan riset WER Bahasa Indonesia:** whisper-large-v3 ≈ 14% WER (audio nyata, code-switching), Medium ≈ 28%, base 18–47%; **distil-whisper/turbo terbaik ≈ 8%** (studi Polibatam JAIC 2025). → pemilihan distil-whisper bukan cuma hemat, tapi paling akurat + memperkuat narasi distilasi.
- **Mitigasi istilah bahan salah transkripsi:** fuzzy-match hasil STT ke KB bahan F2 ("niasinamida" → Niacinamide) — F5 mendapat peningkatan akurasi gratis dari infrastruktur F2.
- **Scope demo:** push-to-talk, satu instruksi per push, confirm-before-save. Tanpa continuous listening.

## 7. F4 — Next-Best-Experiment ⏸ HOLD

Ditunda sampai F1 + F3 + F5 solid. Ketika diaktifkan, opsi terurut:
- **Opsi B (favorit):** Random Forest surrogate + UCB manual — robust untuk data simulasi sangat sedikit (5–15 titik); framing jujur: "surrogate model + acquisition heuristic, terinspirasi BO".
- **Opsi A:** GP + Expected Improvement (BO sejati) — hanya jika sempat generate response surface sintetis yang bagus.
- **Opsi C:** simulasi + template DOE — fallback terakhir.
- Jawaban juri saat hold: fallback DOE template per kategori produk (sudah tertulis di dokumen Workflow §3.4 & §5).

## 8. Narasi Distilasi (inti cerita teknis)

> *"Satu teacher LLM besar dipakai di balik layar untuk menghasilkan data latih (synthetic instruction data); hasilnya satu model kecil terdistilasi yang melayani pemahaman bahasa (F1 ringkasan + F5 ekstraksi), plus STT terdistilasi (distil-whisper). Semuanya jalan on-premise — karena formula Paragon adalah rahasia dagang yang tidak boleh keluar."*

- **Metode:** distillation via synthetic instruction data — teacher (LLM besar) dipanggil sekali di awal untuk generate training set; model 1.5–3B di-LoRA di atasnya. **Bukan** logit/hidden-state distillation penuh (diakui sebagai roadmap fase lanjut).
- Menjawab sekaligus: **K5** (kerahasiaan formula → on-premise) dan **K2** (akuntabilitas → human sign-off untuk semua output AI).

## 9. Keputusan & Open Questions

| # | Keputusan | Status |
|---|---|---|
| D1 | Satu LLM distilasi melayani F1 + F5 | ✅ disetujui |
| D2 | F2 tetap rule-based murni | ✅ disetujui |
| D3 | F3 pakai CV klasik (fine-tune di FLUID) | ✅ disetujui — menunggu QC dataset |
| D4 | F4 ditunda | ✅ disetujui |
| D5 | Distilasi = synthetic instruction data + LoRA, bukan full logit distillation | ✅ disetujui |
| Q1 | QC kualitas dataset FLUID | ⚠️ **gated** — repo GitHub hanya berisi README; akses via Google Form (link dikirim via email setelah disetujui; kontak: maurizio.demicco@unina.it). QC visual cover: foto vial latar hitam seragam, pencahayaan standar, pemisahan fase & creaming terlihat jelas — format ideal untuk classifier. Aksi: isi form ASAP, karena waktu persetujuan di luar kendali kita. |
| Q2 | Struktur korpus + template prompt generate training set | 🔄 draft berikutnya (`CORPUS-PLAN.md`) |
