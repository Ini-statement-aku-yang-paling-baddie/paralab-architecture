# Deployment

Panduan menjalankan API F3 di luar mesin lokal. Ini bukan bagian dari arsitektur inti — lihat [Architecture v5](../architecture/architecture_v5.md) untuk itu — melainkan cara mengekspos adaptor `api/app.py` yang sudah ada ke internet.

| Dokumen | Isi |
|---|---|
| [huggingface_spaces.md](huggingface_spaces.md) | Deploy API F3 sebagai Docker Space gratis di Hugging Face |
| [local_llm_hosting.md](local_llm_hosting.md) | Menjalankan F1 evidence summarizer (Qwen2.5-1.5B + LoRA) di mesin lokal |
| [public_api_gateway.md](public_api_gateway.md) | Production Compose: satu origin HTTPS untuk F1–F5, plus overlay Cloudflare Tunnel gratis untuk backend laptop |

Untuk deployment produksi dengan website publik, gunakan panduan gateway. Ia menetapkan satu origin HTTPS, CORS origin website eksplisit, dan jaringan internal untuk service backend. Semua respons tetap `synthetic_demo` dan deployment ini tidak menambahkan autentikasi aplikasi.
