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

Client mengirim formula, kondisi proses, dan checkpoint domain. Client **tidak** mengirim feature vector F3 internal.

## Konfigurasi deploy

| Environment variable | Fungsi |
|---|---|
| `PARALAB_F3_ARTIFACT_DIR` | Folder artifact F3. Default: `modules/f3_stability_sentinel/outputs/1`. |
| `PARALAB_CORS_ORIGINS` | Origin frontend yang diizinkan, dipisahkan koma. Set eksplisit di environment deploy. |

Artefak hanya boleh dimuat dari build ParaLab yang dipercaya. `model_manifest.json` memverifikasi SHA-256 model, feature schema, threshold, provenance synthetic, dan status CV.
