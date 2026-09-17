# Sources

Folder ini menyimpan snapshot sumber publik yang menjadi input pipeline evidence. Berbeda dari `resources/`, file di sini harus memiliki provenance dan diperiksa oleh validator.

## Struktur

```text
public/
└── PMC7407566_tables_2_5.json
```

Snapshot publik tidak otomatis menjadi label supervised F3. Pipeline saat ini hanya menggunakannya sebagai evidence F1 karena tidak memenuhi kontrak trajectory longitudinal landmark hingga outcome.

Gunakan:

```bash
python3 scripts/build_public_evidence.py validate
python3 scripts/ingest_open_sources.py validate
```

Jangan menaruh formula internal, dokumen supplier restricted, data biologis mentah, atau identitas peneliti/partisipan di folder ini.
