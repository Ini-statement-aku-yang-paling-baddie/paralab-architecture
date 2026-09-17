# Deploy API F3 ke Hugging Face Spaces

Panduan ini menjalankan `api/app.py` sebagai Docker Space gratis di Hugging Face. Space bersifat publik dan tanpa kartu kredit pada tier gratis.

> [!IMPORTANT]
> Space yang dihasilkan tetap melayani forecast `synthetic_demo` saja, tanpa auth, tanpa rate limiting, sama seperti menjalankannya lokal. Jangan promosikan endpoint publik ini sebagai layanan produksi.

## 1. Berkas yang terlibat

Sudah disiapkan di repository ini, tidak perlu dibuat ulang:

- [`Dockerfile`](../../Dockerfile) — image minimal, hanya `api/`, `modules/`, dan dua file `data/*.json` yang dibaca F2.
- [`.dockerignore`](../../.dockerignore) — memangkas `data/full_synthetic`, `cv/`, `notebooks/`, `.venv-f3/`, dan folder besar lain dari build context.
- [`requirements/serve.txt`](../../requirements/serve.txt) — versi dependency dipatok persis ke `model_manifest.json` supaya `validate_runtime()` tidak menolak model.

## 2. Buat Space

1. Buka [huggingface.co/new-space](https://huggingface.co/new-space) (perlu akun Hugging Face — buat sendiri, bukan lewat asisten).
2. Pilih **SDK: Docker**, visibility sesuai kebutuhan (Public untuk tier gratis tanpa kartu; Private butuh paket berbayar).
3. Setelah dibuat, Space punya git remote sendiri, formatnya:
   ```
   https://huggingface.co/spaces/<username>/<nama-space>
   ```

## 3. Tambahkan frontmatter Space ke README

Hugging Face membaca metadata Space (SDK, port, judul) dari blok YAML di baris paling atas `README.md`. Blok ini sudah disiapkan di bagian atas [`README.md`](../../README.md) repository ini, ditandai komentar `HUGGINGFACE SPACE METADATA`. Jangan hapus blok itu — GitHub mengabaikannya sebagai teks biasa, tapi Hugging Face membacanya untuk tahu ini Docker Space dengan `app_port: 7860`.

## 4. Push repository ke Space

```bash
cd paralab-architecture
git remote add space https://huggingface.co/spaces/<username>/<nama-space>
git push space main
```

Space akan build otomatis begitu menerima push. Build pertama memakan waktu beberapa menit (instalasi `pandas`/`scikit-learn`). Pantau progres di tab **Logs** pada halaman Space.

## 5. Set environment variable

Di halaman Space → **Settings** → **Variables and secrets**, tambahkan sebagai **Variable** (bukan Secret, karena bukan rahasia):

| Nama | Nilai |
|---|---|
| `PARALAB_CORS_ORIGINS` | Origin situs yang sebenarnya, mis. `https://paralab-website.<akun>.workers.dev`. Pisahkan dengan koma bila lebih dari satu origin |

Tanpa ini, API tetap jalan tapi browser menolak membaca responsnya dari origin manapun selain default (`localhost:3000`, `localhost:5173`) — persis gejala "API mati" yang pernah muncul saat CORS salah alamat di lokal.

## 6. Verifikasi

```bash
curl https://<username>-<nama-space>.hf.space/health
```

Harus mengembalikan `{"status":"ok", "model_version": "...", "data_origin": "synthetic_demo", ...}`. Kalau 503, cek tab Logs — kemungkinan besar `validate_runtime()` menolak karena versi paket di image tidak cocok dengan `model_manifest.json` (lihat komentar di `requirements/serve.txt`).

## 7. Sambungkan ke website

Set `VITE_PARALAB_F3_URL` pada build website ke URL Space (`https://<username>-<nama-space>.hf.space`), sesuai `.env.example` di repository `paralab-website`.

## Perilaku idle

Space CPU gratis bisa masuk mode tidur setelah lama tanpa trafik. Permintaan pertama setelah tidur akan lambat (Space perlu "bangun" dan me-restart container) sebelum kembali responsif. Untuk demo langsung, buka `/health` beberapa menit sebelum sesi dimulai supaya Space sudah dalam kondisi bangun.
