# Pilot labeling blind retrieval F1

## Status

Queue pertama sudah dibuat di `data/labeling/rag_blind_v1/`:

- 10 blind query manusia `QB-001` sampai `QB-010`;
- 30 kandidat per query;
- total 300 pasangan `query_id × source_id`;
- label `relevance` berskala 0, 1, 2;
- seluruh label berstatus `ai_assisted_provisional` dan `needs_human_review`.

Tidak ada label ini yang boleh disebut human-reviewed atau dipakai sebagai metrik final sebelum review/adjudication.

## Membuat ulang dan validasi

```bash
python3 scripts/build_rag_label_pilot.py build
python3 scripts/build_rag_label_pilot.py validate
```

File utama: `rag_blind_label_candidates.jsonl`.

| Field | Makna |
|---|---|
| `query_id` | Blind query yang dinilai |
| `source_id` | Evidence card kandidat |
| `relevance` | 2 utama, 1 relevan parsial, 0 tidak relevan |
| `rationale` | Dasar provisional dari metadata terstruktur |
| `evidence_snapshot` | Scenario, outcome, failure mode, dan ingredient untuk review cepat |
| `coverage_gap` | Kekosongan coverage yang harus diakui |
| `candidate_rank` | Urutan kandidat review, bukan skor production |
| `review_status` | Harus berubah lewat proses review manusia |

## Aturan reviewer

1. Nilai berdasarkan kecocokan query dengan evidence, bukan berdasarkan kelancaran narasi.
2. Jangan mengubah `source_id`, provenance, atau menganggap synthetic corpus sebagai hasil lab nyata.
3. `QB-009` meminta konteks pria. Corpus tidak memiliki metadata gender, sehingga kandidat hanya boleh maksimal relevance 1 dengan `coverage_gap: gender_not_recorded_in_synthetic_corpus`.
4. `QB-004` sengaja berisi kandidat relevance 0 karena corpus tidak mencatat keluhan lengket aktual. Ini menguji abstention, bukan retrieval paksa.
5. Setiap konflik besar antarreviewer, khususnya 0 versus 2, perlu adjudication.

Setelah dua reviewer dan adjudication selesai, buat export `rag_blind_labels_final.jsonl` terpisah. File blind source asli tidak boleh ditimpa.
