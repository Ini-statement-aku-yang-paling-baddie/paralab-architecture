# Model lokal (tidak masuk Git)

Folder ini berisi **3,6 GB** bobot model yang di-gitignore (lihat `.gitignore` root: `models/`). Dokumen ini menjelaskan isinya supaya siapa pun yang menemukan folder ini di mesin lokal tahu asal-usulnya tanpa perlu menebak dari nama file.

> [!IMPORTANT]
> Sama seperti seluruh repository ini, model di folder ini dilatih dan diuji hanya pada data **synthetic_demo**. Lihat batas per model di bawah.

## Isi

| Path | Ukuran | Apa ini |
|---|---|---|
| `Qwen2.5-1.5B-Instruct/` | 2,9 GB | Base model [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct), 1,54B parameter, dipakai apa adanya dari Qwen tanpa modifikasi |
| `formulab-qwen-lora/` | 86 MB | Adapter LoRA (rank 16, target `q/k/v/o/gate/up/down_proj`) hasil fine-tune Qwen2.5-1.5B-Instruct untuk task **`f1_evidence_summary`**: meringkas satu evidence card F1 (outcome, failure mode, narrative, lesson learned) jadi ringkasan grounded + catatan limitasi, tanpa mengarang angka atau membocorkan formula lengkap |
| `formulab_qwen_lora/sft_data/f1_sft_test.jsonl` | 33 baris | Test split data fine-tuning: contoh pasangan evidence card → ringkasan yang dipakai model. Berguna untuk sanity check (lihat `scripts/run_f1_summarizer.py`), bukan untuk retraining |
| `embedding_model/` | 466 MB | SentenceTransformer 384-dim, arsitektur sama dengan `paraphrase-multilingual-MiniLM-L12-v2` yang dipakai F1 dense retrieval (`docs/data/f1_dense_evaluation.md`). Ini bentuk unzipped; pipeline lama (`scripts/evaluate_f1_dense.py`) masih mengharapkan arsip zip di `sentence-transformer/embedding_model.zip`, folder ini adalah salinan terpisah, bukan pengganti otomatis |

## Cara menjalankan

Lihat [`docs/deploy/local_llm_hosting.md`](../docs/deploy/local_llm_hosting.md) untuk requirements, instalasi, dan dua cara menjalankan model-model ini:

1. `scripts/run_f1_summarizer.py` — sanity check langsung ke model, tanpa server.
2. `api/model_gateway.py` — server FastAPI lokal yang membungkus F1 (retrieval + summarizer di atas), plus F2, F4, dan F5 di endpoint terpisah. Ini yang dipakai kalau mau F1 diakses lewat HTTP, bukan cuma dari sanity check.

## Status koneksi

`api/model_gateway.py` **sudah** menghubungkan model-model ini ke endpoint HTTP (`/v1/f1/query`, `/v1/f2/health-check`, `/v1/f4/next-validation`, `/v1/f5/transcribe-draft`) — ini terpisah sengaja dari `api/app.py` (F3), yang tetap jalan di `.venv-f3` dengan versi paket dipatok persis untuk `model_manifest.json`. Gateway ini baru untuk **hosting lokal**; belum ada rencana deploy ke cloud untuk model 3,6 GB ini (lihat batas ukuran di `docs/deploy/local_llm_hosting.md`).
