# Image deploy untuk API F3 Stability Sentinel ParaLab.
#
# Dipakai untuk Hugging Face Spaces (SDK: Docker) atau host container lain
# yang serupa (Cloud Run, Render). Image ini HANYA membungkus adaptor FastAPI
# di api/app.py: tidak ada training, tidak ada notebook, tidak ada corpus F1.
#
# Versi pandas/scikit-learn/joblib DIPATOK PERSIS ke runtime fingerprint di
# modules/f3_stability_sentinel/outputs/1/model_manifest.json. Modul
# modules/f3_stability_sentinel/deployment.py menolak memuat model bila
# fingerprint tidak cocok persis (lihat validate_runtime), jadi jangan naikkan
# versi paket ini tanpa melatih ulang model dan memperbarui manifest.
FROM python:3.11.16-slim

WORKDIR /app

# Dependency dulu, supaya layer cache pip tidak batal setiap kali kode berubah.
COPY requirements/serve.txt requirements/serve.txt
RUN pip install --no-cache-dir -r requirements/serve.txt

# Salin hanya yang benar-benar dibaca adaptor saat runtime:
#   api/                                       -> adaptor FastAPI
#   modules/                                    -> F2 guardrail + inference F3
#   data/ingredient_master.json, formulation_rules.json -> dibaca f2_guardrail.py
COPY api/ api/
COPY modules/ modules/
COPY data/ingredient_master.json data/formulation_rules.json data/

# Hugging Face Spaces (Docker SDK) mengarahkan trafik publik ke port 7860.
# PARALAB_F3_ARTIFACT_DIR tidak perlu di-set: default di api/app.py sudah
# menunjuk ke modules/f3_stability_sentinel/outputs/1 relatif terhadap file
# ini, dan struktur folder itu dipertahankan persis di image ini.
#
# PARALAB_CORS_ORIGINS SENGAJA tidak di-hardcode di sini. Set sebagai
# environment variable pada platform deploy (mis. "Variables" di Hugging Face
# Spaces) agar berisi origin situs yang sebenarnya, bukan localhost.
EXPOSE 7860

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "7860"]
