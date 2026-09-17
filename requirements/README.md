# Dependency per workflow

Dependency dipisahkan agar user tidak perlu menginstal seluruh stack untuk satu tugas.

| File | Digunakan untuk |
|---|---|
| `f1_dense.txt` | evaluator SentenceTransformer F1, CPU-only |
| `f1_summarizer.txt` | dependency inti F1 evidence summarizer (Qwen2.5-1.5B + LoRA) |
| `model_gateway.txt` | server lokal F1+F2+F4+F5 (`api/model_gateway.py`), meng-include `f1_summarizer.txt` + FastAPI/uvicorn — lihat `docs/deploy/local_llm_hosting.md` |
| `f3_stability_sentinel.txt` | training dan evaluasi model tabular F3 |
| `cv.txt` | generator gambar sintetis CV |
| `api.txt` | adaptor FastAPI untuk deployment bundle F3 (dev lokal, versi fleksibel) |
| `serve.txt` | image Docker deploy (Hugging Face Spaces, dst); versi dipatok persis ke `model_manifest.json` |

Contoh:

```bash
uv venv .venv-f3 --python 3.11
uv pip install --python .venv-f3/bin/python -r requirements/f3_stability_sentinel.txt
```

Model SentenceTransformer dan embedding F1 tidak disimpan di Git. Lihat [`docs/data/f1_dense_evaluation.md`](../docs/data/f1_dense_evaluation.md).
