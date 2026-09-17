# Notebook

Notebook dipakai untuk eksperimen yang memerlukan alur interaktif. Implementasi yang menjadi kontrak produksi prototipe tetap ditempatkan di `modules/` atau `scripts/`.

## Corpus generator

`corpus_generator/` berisi:

- `paralab_v4_corpus_generator.ipynb`: notebook generator corpus;
- `generate_corpus_v4.py`: source Python yang lebih mudah ditinjau dan dibandingkan di Git.

Corpus yang dihasilkan berstatus synthetic-demo. Nama `v4` dipertahankan karena merupakan versi artefak generator, bukan versi arsitektur aktif.

Jangan menyimpan credential, token API, atau output model besar di notebook/repository.
