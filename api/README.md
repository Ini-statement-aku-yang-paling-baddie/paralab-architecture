# API ParaLab

API ini adalah adaptor HTTP minimal untuk **F3 Stability Sentinel**. API membaca deployment bundle lokal yang hash-nya diverifikasi sebelum model `joblib` dimuat.

> [!IMPORTANT]
> Seluruh response F3 berstatus `synthetic_demo`. CV dinyatakan eksplisit sebagai `concept_only_synthetic_render_pilot`, bukan analisis foto lab nyata. Tidak ada endpoint yang memberi early pass.

## Menjalankan lokal

```bash
uv venv .venv-f3 --python 3.11
uv pip install --python .venv-f3/bin/python -r requirements/f3_stability_sentinel.txt
uv pip install --python .venv-f3/bin/python -r requirements/api.txt
.venv-f3/bin/python modules/f3_stability_sentinel/train_stability_sentinel.py
.venv-f3/bin/python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Buka dokumentasi interaktif di `http://127.0.0.1:8000/docs`.

## Endpoint

| Endpoint | Fungsi |
|---|---|
| `GET /health` | Memastikan artifact dapat dimuat dan menyatakan provenance model/CV. |
| `POST /v1/f3/forecasts` | Menjalankan F2, feature engineering F3, lalu forecast atau abstain. |
| `POST /v1/f4/next-validation` | Mengubah output F2/F3 terstruktur menjadi satu langkah validasi/review berikutnya yang wajib direview manusia. |

Client mengirim formula, kondisi proses, dan checkpoint domain. Client **tidak** mengirim feature vector F3 internal.

## Konfigurasi deploy

| Environment variable | Fungsi |
|---|---|
| `PARALAB_F3_ARTIFACT_DIR` | Folder artifact F3. Default: `modules/f3_stability_sentinel/outputs/1`. |
| `PARALAB_CORS_ORIGINS` | Origin frontend yang diizinkan, dipisahkan koma. Set eksplisit di environment deploy. |

Artefak hanya boleh dimuat dari build ParaLab yang dipercaya. `model_manifest.json` memverifikasi SHA-256 model, feature schema, threshold, provenance synthetic, dan status CV.

## Deploy sebagai container

`Dockerfile` di root repository membungkus API ini untuk platform seperti Hugging Face Spaces, memakai `requirements/serve.txt` yang versinya dipatok persis ke `model_manifest.json`. Panduan lengkap: [`docs/deploy/huggingface_spaces.md`](../docs/deploy/huggingface_spaces.md).
