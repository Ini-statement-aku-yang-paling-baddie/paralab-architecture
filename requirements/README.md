# Dependency per workflow

Dependency dipisahkan agar user tidak perlu menginstal seluruh stack untuk satu tugas.

| File | Digunakan untuk |
|---|---|
| `f1_dense.txt` | evaluator SentenceTransformer F1, CPU-only |
| `f3_stability_sentinel.txt` | training dan evaluasi model tabular F3 |
| `cv.txt` | generator gambar sintetis CV |
| `api.txt` | adaptor FastAPI untuk deployment bundle F3 |

Contoh:

```bash
uv venv .venv-f3 --python 3.11
uv pip install --python .venv-f3/bin/python -r requirements/f3_stability_sentinel.txt
```

Model SentenceTransformer dan embedding F1 tidak disimpan di Git. Lihat [`docs/data/f1_dense_evaluation.md`](../docs/data/f1_dense_evaluation.md).
