# Baseline F1 dense retrieval

Baseline retrieval menggunakan `paraphrase-multilingual-MiniLM-L12-v2` melalui SentenceTransformer lokal, tanpa fallback lexical.

## Artefak lokal yang tidak dipush

Folder `sentence-transformer/` sengaja diabaikan Git karena berukuran sekitar 417 MB. Sebelum menjalankan evaluasi pada workspace baru, salin folder tersebut secara lokal dengan struktur berikut:

```text
sentence-transformer/
├── embedding_model.zip
└── embeddings_paralab.npy
```

Keduanya diperlukan. ZIP menyimpan model lokal, sedangkan `.npy` adalah 600 embedding dokumen yang urutannya cocok dengan `data/evidence_rag_text.jsonl`.

## Environment yang dapat direproduksi

Versi diselaraskan dengan metadata model:

- PyTorch `2.10.0+cpu`
- SentenceTransformers `5.4.1`
- Transformers `5.0.0`

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements-f1-dense.txt
.venv/bin/python scripts/evaluate_f1_dense.py
```

Gunakan build CPU. Jangan menginstal build CUDA secara tidak sengaja karena baseline ini tidak memerlukan GPU dan paket CUDA memperbesar environment beberapa gigabyte.

## Output dan batas metrik

Perintah menulis `data/evaluation/f1_dense_pool_v1.json`.

Metrik hanya mengukur reranking dense pada 30 kandidat yang telah diberi label mesin untuk setiap blind query. Jadi metrik ini **bukan** klaim open-corpus retrieval, validasi ilmiah kosmetik, atau evaluasi domain-expert. Blind query tetap tidak boleh masuk data training atau teacher generation.
