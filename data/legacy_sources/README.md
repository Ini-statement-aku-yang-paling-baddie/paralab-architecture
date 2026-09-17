# Legacy source inputs

File di folder ini adalah input lama yang masih diperlukan oleh `scripts/build_data_pilot.py` untuk menjaga replay dan checksum pilot awal.

- `corpus_paralab.json`: corpus sumber pilot lama.
- `embeddings_paralab.npy`: embedding pasangan pilot lama.

Keduanya tidak digunakan oleh evaluator F1 dense aktif. Evaluator aktif memakai artefak local-only di `sentence-transformer/`.

Jangan mengubah file ini tanpa memperbarui dan memvalidasi seluruh manifest pilot.
