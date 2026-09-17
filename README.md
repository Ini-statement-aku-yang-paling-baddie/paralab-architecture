# ParaLab

Prototipe local-first untuk R&D formulasi kosmetik O/W gel-cream kulit berminyak. ParaLab menggabungkan retrieval evidence F1, guardrail deterministik F2, structured logging F5, serta Stability Sentinel F3. Seluruh artefak sintetis berstatus demo dan bukan validasi laboratorium atau keputusan produksi.

## Mulai dari sini

| Jika ingin memahami | Buka |
|---|---|
| Arsitektur dan batas klaim | [`docs/architecture/architecture_v5.md`](docs/architecture/architecture_v5.md) |
| Kontrak serta provenance data | [`data/README.md`](data/README.md) |
| Dataset penuh dan F3 | [`docs/data/full_dataset.md`](docs/data/full_dataset.md) |
| Hasil serta batas CV pilot | [`docs/reports/cv_pilot_report.md`](docs/reports/cv_pilot_report.md) |
| Kajian F3 dan keputusan one-sided alert | [`docs/reports/f3_early_detection_study.md`](docs/reports/f3_early_detection_study.md) |

## Struktur repository

- `modules/`: capability inti yang dapat diimpor, saat ini F2 Guardrail dan F3 Stability Sentinel.
- `scripts/`: builder, ingestion, dan evaluator data yang dijalankan dari CLI.
- `data/`: dataset kanonis, view turunan, evidence publik, dan manifest provenance.
- `cv/`: generator dataset visual sintetis, notebook training, dan artefak evaluasi CV.
- `notebooks/`: notebook eksplorasi dan generator corpus.
- `tests/`: kontrak determinisme, anti-leakage, dan perilaku safety.
- `docs/`: dokumentasi yang dikelompokkan berdasarkan arsitektur, data, produk, dan laporan.
- `resources/` dan `sources/`: materi referensi proyek yang tidak dieksekusi sebagai kode.

## Perintah verifikasi

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_data_pilot.py validate
python3 scripts/build_full_dataset.py validate
python3 scripts/build_public_evidence.py validate
python3 scripts/build_training_views.py validate
```

F3 memerlukan dependency terpisah di `modules/f3_stability_sentinel/requirements.txt`.

## Batasan penting

- F2 adalah rule engine deterministik, bukan approval otomatis regulasi atau halal.
- F3 hanya mengeluarkan alert risiko atau instruksi melanjutkan observasi, tidak pernah early pass.
- CV adalah pilot pada render sintetis dan tidak menggantikan pengukuran instrumen atau stability test formal.
- Output AI dan data sintetis selalu memerlukan konfirmasi manusia serta tidak boleh diklaim sebagai ground truth ilmiah.
