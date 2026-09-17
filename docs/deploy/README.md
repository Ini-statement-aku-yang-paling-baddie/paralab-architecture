# Deployment

Panduan menjalankan API F3 di luar mesin lokal. Ini bukan bagian dari arsitektur inti — lihat [Architecture v5](../architecture/architecture_v5.md) untuk itu — melainkan cara mengekspos adaptor `api/app.py` yang sudah ada ke internet.

| Dokumen | Isi |
|---|---|
| [huggingface_spaces.md](huggingface_spaces.md) | Deploy API F3 sebagai Docker Space gratis di Hugging Face |

Batas yang tetap berlaku setelah deploy sama seperti lokal: seluruh response berstatus `synthetic_demo`, tidak ada auth/rate limiting, dan CORS wajib diisi origin situs yang sebenarnya lewat environment variable `PARALAB_CORS_ORIGINS` — lihat [`api/README.md`](../../api/README.md).
