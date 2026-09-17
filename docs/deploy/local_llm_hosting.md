# Hosting lokal: gateway F1, F2, F4, F5

Panduan ini menjalankan `api/model_gateway.py` — server FastAPI lokal yang membungkus:

- **F1**: hybrid retrieval (lexical + dense RRF) atas 600 evidence, lalu ringkasan grounded dari `Qwen2.5-1.5B-Instruct` + LoRA adapter `formulab-qwen-lora` (lihat [`models/README.md`](../../models/README.md) untuk isi lengkap `models/`).
- **F2**: `screen_formula` yang sudah ada, dibungkus jadi endpoint.
- **F4**: `recommend_next_validation` yang sudah ada, dibungkus jadi endpoint.
- **F5**: parser transkrip Indonesia (angka lisan, deteksi appearance) yang selalu `requires_confirmation: true` dan tidak pernah menulis checkpoint sendiri.

> [!IMPORTANT]
> Ini **sengaja terpisah** dari `api/app.py` (F3). F3 tetap jalan di `.venv-f3` dengan versi paket dipatok persis ke `model_manifest.json`. Gateway ini pakai environment lain karena model 3,6 GB dan kebutuhan versinya beda — jangan digabung jadi satu proses.

## 1. Kebutuhan mesin

| | Minimum | Rekomendasi |
|---|---|---|
| RAM | ~6 GB bebas | 8 GB+ bebas |
| GPU | Tidak wajib, jalan di CPU | NVIDIA ≥6 GB VRAM (mis. RTX 4050 laptop) — otomatis terdeteksi dan dipakai |
| Disk | 3,5 GB untuk `models/` + ~1 GB dependency | — |
| Python | 3.11 | sama |

## 2. Buat environment dan install

```bash
cd paralab-architecture
python3.11 -m venv .venv-f1-llm
.venv-f1-llm/bin/pip install -r requirements/model_gateway.txt
```

`requirements/model_gateway.txt` meng-include `requirements/f1_summarizer.txt` (torch, transformers, peft, accelerate, sentence-transformers) ditambah `fastapi`/`uvicorn` untuk server-nya.

### Kalau `--extra-index-url` PyTorch tidak terjangkau

`requirements/f1_summarizer.txt` menunjuk index CPU-only PyTorch (`download.pytorch.org`). Beberapa jaringan/sandbox tidak bisa menjangkau host itu meski PyPI biasa bisa. Kalau macet di situ, pakai build PyPI biasa (lebih besar unduhannya karena menyertakan dukungan CUDA, tapi tetap jalan di mesin CPU-only — CUDA hanya aktif kalau ada GPU dan driver-nya, terverifikasi jalan di kedua kondisi):

```bash
.venv-f1-llm/bin/pip install torch numpy
.venv-f1-llm/bin/pip install transformers peft accelerate safetensors sentence-transformers fastapi uvicorn httpx
```

## 3. Jalankan test suite dulu

```bash
.venv-f1-llm/bin/python -m unittest tests.test_model_gateway_contract -v
```

Test ini pakai `FakeF1Service` untuk F1 (supaya cepat, tidak memuat model 2,9 GB), tapi F2/F4/F5 dites terhadap kode asli. Semua harus `OK` sebelum lanjut.

## 4. Jalankan server

```bash
.venv-f1-llm/bin/python -m uvicorn api.model_gateway:app --host 127.0.0.1 --port 8100
```

Panggilan pertama ke `/v1/f1/query` akan lambat (memuat base model 2,9 GB + adapter). Panggilan berikutnya cepat karena model tetap di memori (`@lru_cache` pada `default_f1_service`).

## 5. Contoh panggilan (sudah diverifikasi jalan)

```bash
curl http://127.0.0.1:8100/health

curl -X POST http://127.0.0.1:8100/v1/f1/query -H "Content-Type: application/json" \
  -d '{"query":"viskositas turun setelah beberapa minggu"}'

curl -X POST http://127.0.0.1:8100/v1/f2/health-check -H "Content-Type: application/json" \
  -d '{"formula":[{"bahan":"Niacinamide","pct":4},{"bahan":"Ascorbic Acid","pct":10}],"context":{"target_skin":"oily"}}'

curl -X POST http://127.0.0.1:8100/v1/f4/next-validation -H "Content-Type: application/json" \
  -d '{"f3_forecast":{"decision":"continue_observation","risk_band":"low","confidence":"low","data_origin":"synthetic_demo","f2_screening":{"derived_features":{}}}}'

curl -X POST http://127.0.0.1:8100/v1/f5/transcribe-draft -H "Content-Type: application/json" \
  -d '{"selected_trial_id":"prj-gelcream-oily-b1","transcript":"pH nya lima koma dua, viskositas 6100 cP, sampelnya homogen"}'
```

`/v1/f5/transcribe-draft` pada contoh di atas mengembalikan `measurements.ph: 5.2`, `measurements.viscosity_cp: 6100.0`, `observations.appearance: "uniform"`, dan `requires_confirmation: true` — cocok dengan gerbang konfirmasi manusia yang sama seperti checkpoint F3 di website (lihat `PanelCheckpoint` di `paralab-website`).

## 6. Bug yang ditemukan dan diperbaiki: evidence card kosong

Saat pertama dites, `LocalF1Service` memuat `data/evidence_rag_text.jsonl` sebagai satu-satunya sumber baris evidence. File itu cuma punya `source_id` dan `text` gabungan — cukup untuk retrieval (lexical + dense), **tidak cukup** untuk `prepare_summary_request()` yang butuh field terstruktur (`outcome`, `failure_mode`, `journal_title`, `narrative_excerpt`, `lesson_learned`). Akibatnya evidence card yang dikirim ke LLM nyaris kosong.

Field yang hilang itu ada di `data/evidence_corpus.jsonl` (600 baris, `source_id` sama persis dengan `evidence_rag_text.jsonl`). Perbaikannya: `LocalF1Service._load_retrieval` sekarang meng-enrich tiap baris dengan field dari `evidence_corpus.jsonl` lewat lookup `source_id`, sambil mempertahankan **urutan baris** dari `evidence_rag_text.jsonl` karena `embeddings_paralab.npy` sejajar secara posisi (bukan dicocokkan lewat id) dengan file itu.

Sudah diverifikasi ulang setelah perbaikan: `evidence` di respons `/v1/f1/query` sekarang membawa `outcome`/`failure_mode`/`journal_title`, dan ringkasan LLM benar-benar mengacu ke isi evidence, bukan cuma menerka dari `source_id` kosong.

## 7. Rough edge yang diketahui (bukan pelanggaran keamanan)

Redaksi angka (`redact_f1_numbers`) kadang menyisakan simbol `%` sendirian setelah digit di depannya dihapus (mis. "...turun lebih dari %"). Tidak ada angka yang bocor — simbolnya kosong makna — tapi estetika kalimat sedikit janggal. Belum diperbaiki karena bukan masalah keamanan, dicatat di sini supaya tidak mengejutkan saat demo.

## 8. Batas yang wajib ikut kalau ini ditampilkan ke pengguna

- `data_origin: synthetic_demo` di F1, `browser_stt_transcript` di F5 — bukan data lab nyata.
- `requires_human_review: true` (F1, F4) dan `requires_confirmation: true` (F5) — tidak ada satu pun dari keempat modul ini yang boleh menulis checkpoint atau memberi approval sendiri.
- Guardrail F1 dua lapis: `redact_f1_numbers` membersihkan angka dari evidence **sebelum** masuk prompt LLM, dan `finalize_summary` menolak keluaran yang masih mengandung pola persen/pH/cP/rpm/°C **setelah** LLM generate. Kalau nanti mengganti model atau prompt, pertahankan kedua lapis ini.
