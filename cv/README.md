# ParaLab CV

Folder ini memuat seluruh artefak computer vision ParaLab.

## Dataset sintetis prosedural

`generate_dataset.py` mempertahankan baseline V2 lima kelas. Dataset yang direkomendasikan untuk training berikutnya adalah V3, dibuat oleh `generate_dataset_v3.py`. V3 memakai domain randomization pada bentuk wadah, background, pencahayaan, crop, fill level, warna cairan, fokus, dan manifestasi instability agar tugas tidak hanya menghafal satu template per kelas.

Instal dependensi CV pada environment Python yang akan menjalankan generator:

```bash
python3 -m pip install -r cv/requirements.txt
```

Lalu build dan validasi V3:

```bash
python3 cv/generate_dataset_v3.py build
python3 cv/generate_dataset_v3.py validate
```

Output default: `cv/data/synthetic_v3/`

Kelas classifier V3:

- `stable_uniform`
- `creaming`
- `phase_separation`
- `heterogeneous`

`uncertain` tidak lagi menjadi kelas classifier. Ia harus diperlakukan sebagai abstention atau human-review state setelah image-quality gate, bukan sebagai pola visual sintetis yang dapat dihafal model.

Setiap manifest record menyimpan sequence ID, split, label, hash gambar, provenance, dan parameter capture. Seluruh view dari satu `sample_sequence_id` berada pada split yang sama untuk mencegah leakage. Split juga distratifikasi per kelas visual, sehingga train, validation, dan test masing-masing mencakup seluruh label saat jumlah sequence per kelas minimal tiga.

## Pipeline training Kaggle

Notebook `cv/notebooks/train_visual_screening.ipynb` adalah pipeline training baseline untuk Kaggle. Upload `cv/data/synthetic_v3/` sebagai Kaggle Dataset, attach ke notebook, lalu ubah `DATASET_ROOT` di cell konfigurasi sesuai slug input Kaggle. Pipeline akan memvalidasi manifest dan hash, melatih `TinyVialCNN`, memilih checkpoint berdasarkan validation loss, lalu melaporkan satu evaluasi final pada test set.


Dataset ini hanya untuk memvalidasi integrasi workflow dan baseline model demo. Output model yang dilatih dengannya wajib ditandai sebagai **synthetic-demo visual screening**, bukan penilaian stabilitas kosmetik atau pengganti stability test.
