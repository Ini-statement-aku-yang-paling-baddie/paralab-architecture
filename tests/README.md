# Test suite

Test menggunakan `unittest` dan mencakup determinisme, kontrak schema, provenance, anti-leakage, serta perilaku keselamatan F2/F3.

## Menjalankan seluruh test

```bash
.venv-f3/bin/python -m unittest discover -s tests -v
```

Gunakan environment F3 agar test model tidak di-skip karena dependency tidak tersedia.

## Cakupan utama

| Kelompok test | Yang diverifikasi |
|---|---|
| `test_data_pilot.py` | determinisme pilot, manifest, missingness, dan future leakage |
| `test_full_dataset.py` | generator full synthetic, family-safe split, dan replay manifest |
| `test_f1_dense_eval.py` | judged-pool metrics dan larangan BM25 fallback |
| `test_f2_guardrail.py` | acceptance behavior rule engine F2 |
| `test_f3_stability_sentinel.py` | feature boundary, abstention, dan larangan early pass |
| `test_public_evidence.py` | provenance evidence publik dan exclusion dari supervised F3 |
| `test_rag_label_pilot.py` | label provisional/machine tidak diklaim sebagai human review |
| `test_cv_generator*.py` | generator visual, split sequence-safe, dan manifest |
| `test_cv_training_notebook.py` | pipeline notebook yang reproducible |

Test lulus membuktikan kontrak software pada artefak repository, bukan validitas ilmiah terhadap formulasi kosmetik nyata.
