# Laporan Piloting CV: Visual Instability Screening

> **Status:** hasil piloting hackathon, bukan model produksi.
> **Cakupan:** dataset prosedural `cv/data/synthetic_v3/`, notebook `cv/notebooks/train_visual_screening.ipynb`, output run 1-3 di `cv/outputs/`.
> **Terkait:** [../architecture/architecture_v4.md](../architecture/architecture_v4.md) §11 (F_CV: Visual Screening sebagai Asisten Capture untuk F3), [../data/data_pipeline.md](../data/data_pipeline.md), [../../cv/README.md](../../cv/README.md).

---

## 1. Ringkasan eksekutif

Piloting ini menguji apakah classifier CV kecil (`TinyVialCNN`) bisa membedakan 4 kelas visual ketidakstabilan emulsi (`stable_uniform`, `creaming`, `phase_separation`, `heterogeneous`) dari render prosedural sintetis. Tiga run dilakukan:

| Run | Dataset | Isu | Test accuracy |
|---|---|---|---|
| 1 | v2 (5 kelas, nyaris tanpa randomization) | Task trivial — bisa dihafal lewat warna/posisi piksel yang hampir konstan | 1.00 |
| 2 | v3 (4 kelas, domain-randomized) | Bug arsitektur: model stuck di level tebak acak | 0.26 |
| 3 | v3 (sama persis dataset run 2) | Fix arsitektur diterapkan, dataset tidak diubah | 0.896 |

**Kesimpulan utama:**
1. Dataset v2 harus ditinggalkan — hasil 100%-nya adalah artefak task yang terlalu mudah, bukan bukti model bagus.
2. Dataset v3 (domain-randomized, warna independen dari label) adalah desain yang benar secara konsep.
3. Bug run 2 ada di model (`AdaptiveAvgPool2d((1,1))` membuang informasi posisi spasial), bukan di data. Fix sudah diverifikasi dua kali: smoke test CPU lokal (96.9% val acc) dan run resmi di Kaggle GPU (89.6% test acc) — konsisten.
4. Hasil ini **tidak membuktikan model siap dipakai pada foto kosmetik asli**. Ini murni bukti bahwa pipeline train/eval-nya berfungsi dengan benar pada domain sintetis yang terkontrol.
5. Taksonomi CV ternyata nyaris identik dengan enum `appearance` di dataset F3 yang sedang dikerjakan (`data/full_synthetic/`) — mapping langsung tanpa kehilangan informasi. Contoh gate confidence/abstention dan jalur human-confirmation sudah diformalkan sebagai modul **F_CV** di [../architecture/architecture_v4.md §11](../architecture/architecture_v4.md#11-f_cv-visual-screening-sebagai-asisten-capture-untuk-f3). Yang tersisa murni eksekusi, bukan desain: validasi domain di foto asli (belum lolos) — lihat §4.

---

## 2. Kronologi piloting

### 2.1 Run 1 — v2, task trivial (bukan hasil yang valid untuk diklaim)

`cv/generate_dataset.py` (v2) menggambar vessel dengan bentuk/rotasi/background yang nyaris konstan (jitter ±4-5) dan warna per kelas yang hampir fixed (mis. `creaming` selalu band krem di 13-20% tinggi vessel dengan warna sama persis tiap gambar). Model bisa menang hanya dengan menghafal warna/posisi piksel, bukan belajar morfologi instabilitas. **100% test accuracy run ini tidak dianggap sebagai baseline yang valid** dan menjadi alasan v3 dibuat.

### 2.2 Run 2 — v3, bug arsitektur ditemukan

`generate_dataset_v3.py` memperbaiki masalah di atas: 8 palet warna dipilih independen dari label, 4 profil background/pencahayaan, 3 bentuk vessel, blur/contrast/brightness jitter. Desain ini benar — mencegah shortcut warna.

Tapi model gagal total belajar:

```
epoch  train_loss  train_acc  val_loss  val_acc
1      1.44        0.24       1.39      0.24
7      1.36        0.30       1.41      0.31   (early-stop, patience=6)
```
Train loss nyaris tidak turun (mendekati ln(4)=1.386, level tebak acak untuk 4 kelas) bahkan di data training sendiri. Confusion matrix menunjukkan model tidak pernah memprediksi `phase_separation` sama sekali.

**Root cause**: `TinyVialCNN.features` diakhiri `nn.AdaptiveAvgPool2d((1, 1))` sebelum `nn.Linear(192, num_classes)`. Operasi ini merata-ratakan seluruh feature map jadi satu vektor 192-dim, membuang **semua informasi posisi spasial**. Padahal pembeda utama ke-4 kelas adalah soal *di mana* sesuatu terjadi: boundary horizontal di tengah (`phase_separation`), lapisan tipis di atas (`creaming`), blob tersebar (`heterogeneous`), rata (`stable_uniform`). Di v2 arsitektur ini "kebetulan" cukup karena warna/posisi hampir konstan; begitu warna dilepas dari label di v3, sinyal itu hilang total.

### 2.3 Fix yang diterapkan

Tiga perubahan di `cv/notebooks/train_visual_screening.ipynb` (diff bersih, dataset tidak disentuh):

```diff
- nn.AdaptiveAvgPool2d((1, 1))                                    # buang info spasial
+ nn.AdaptiveAvgPool2d((4, 4))                                    # simpan layout 4x4

- nn.Linear(192, num_classes)
+ nn.Linear(192 * 4 * 4, num_classes)

- NUM_EPOCHS = 25          → 70     # task v3 lebih sulit, butuh lebih lama "pecah" dari initialization
- patience = 6             → 15
```

Learning rate (1e-3, AdamW) dan augmentasi tidak diubah.

### 2.4 Validasi fix — smoke test lokal (CPU, sebelum Kaggle)

Untuk menghindari buang kuota GPU Kaggle, fix diuji dulu secara lokal (CPU, dataset v3 yang sama, tidak diubah):

```
epoch  train_loss  train_acc  val_loss  val_acc
1      1.58        0.22       1.44      0.25
30     0.31        0.89       0.33      0.85
51     0.10        0.97       0.10      0.97   (best_epoch)
60     0.13        0.95       0.48      0.85
```

Val accuracy naik dari level tebak acak ke 96.9% — mengonfirmasi diagnosis sebelum dijalankan resmi di Kaggle.

### 2.5 Run 3 — v3, arsitektur fixed, dijalankan resmi di Kaggle (GPU)

```
best_epoch = 61 / 70
best validation_loss = 0.148, validation_accuracy = 0.958
test_accuracy = 0.896  (86/96 benar)
```

Confusion matrix test set:

```
                stable_uni  creaming  phase_sep  heterogen
stable_uniform      19         5          0          0
creaming              3        20          1          0
phase_separation      0         0         24          0
heterogeneous          1        0          0         23
```

`phase_separation` (100%) dan `heterogeneous` (96%) diklasifikasi nyaris sempurna. **Seluruh 10 error terjadi antara `stable_uniform` ↔ `creaming`** — bukan kegagalan model, tapi overlap yang memang inherent di generator: `creaming` dibedakan dari `stable_uniform` lewat lapisan tipis (`layer_height` 6-20% tinggi, blend `strength` 0.10-0.33), dan di ujung bawah range itu gambarnya secara visual ambigu bahkan buat manusia.

### 2.6 Cek overfitting

Train loss turun mulus terus sampai akhir (1.60→0.09) sementara val loss mulai naik-turun tidak stabil setelah epoch ~50, dan gap train-val accuracy melebar lagi di epoch 65-70 (+0.05 sampai +0.06) — tanda overfitting ringan mulai muncul di ekor training. **Ini sudah tertangani otomatis**: checkpoint yang disimpan dan dipakai untuk evaluasi test adalah checkpoint *best validation loss* (epoch 61, gap train-val accuracy -0.001), bukan model di epoch terakhir (epoch 70, gap sudah melebar lagi). Early-stopping bekerja sesuai desain.

---

## 3. Viabilitas ke data asli — TIDAK, dengan justifikasi eksplisit

Hasil 89.6% ini **tidak memprediksi performa pada foto kosmetik asli**. Alasan:

1. **Domain gap render vs foto**: gambar digambar `PIL.ImageDraw` (persegi/ellipse warna solid, gradient linear matematis). Foto asli punya refleksi kaca, physically-based lighting, tekstur cairan nyata, noise sensor, kompresi, meniskus, foam soft-edge — kompleksitas visual yang jauh melampaui 4 preset gradient di generator.
2. **Label bukan ground truth ilmiah**: `annotation_basis` di manifest adalah `"procedural_generator_parameters"`. Model belajar menebak parameter generator dari piksel, bukan mengenali fenomena instabilitas dari assessment manusia.
3. **Bukti dari confusion pattern sendiri**: error 100% terjadi tepat di ujung bawah range parameter (`layer_height`, `strength`) — model belajar threshold numerik generator, bukan konsep visual general yang robust ke variasi rendering nyata.
4. **Model kecil, from-scratch, data sangat sedikit**: `TinyVialCNN` (~330K parameter) dilatih dari nol pakai 448 gambar, tanpa exposure ke tekstur/noise foto asli sama sekali.

Ini konsisten dengan keputusan produk yang sudah ada: [../architecture/architecture_v4.md](../architecture/architecture_v4.md) menaruh classifier CV visual di **P2, "Ditunda sampai memperoleh dataset gambar berlabel yang sesuai domain"** — bukan P0/P1 seperti F1/F2/F3.

**Yang transferable ke data asli** (bagian yang tetap berharga dari piloting ini):
- Taksonomi kelas (`creaming`, `phase_separation`, `heterogeneous`) adalah fenomena instabilitas emulsi kosmetik yang nyata dan dikenal di literatur formulasi — bukan label arbitrer seperti trajectory pH/viskositas sintetis di F3.
- Pipeline engineering (manifest-driven dataset, split by `sample_sequence_id` anti-leakage, early-stopping berbasis val-loss, confusion matrix + provenance di `training_report.json`) reusable langsung.
- Prinsip fix arsitektur (spatial-preserving pooling untuk task yang dibedakan oleh *posisi*) berlaku umum, bukan tambalan khusus data sintetis.

**Yang harus diganti saat pindah ke data asli** (bukan plug-and-play):
- Ganti `TinyVialCNN` from-scratch → transfer learning (backbone pretrained ImageNet, mis. MobileNetV3/ResNet18 kecil, freeze sebagian layer) karena data asli hampir pasti terbatas volumenya.
- Augmentasi perlu dituning ulang untuk variasi kamera/pencahayaan nyata, bukan augmentasi ringan yang dikalibrasi untuk render vector bersih.
- Hyperparameter (LR, epoch budget, patience) perlu di-retune dari nol, bukan diwariskan dari angka yang cocok untuk dataset sintetis ini.
- Butuh label dari formulator (manusia) yang diverifikasi, bukan parameter generator, idealnya puluhan-ratusan gambar per kelas minimal untuk test set yang bisa dipercaya.

---

## 4. Kompatibilitas dengan pipeline F3 — BELUM, dengan bukti konkret

Rencana produk: CV berperan sebagai **otomasi capture** — peneliti foto sampel alih-alih input observasi manual, hasil CV langsung masuk sebagai data checkpoint yang dikonsumsi F3. Ini dicek terhadap data F3 pilot yang **sudah dieksekusi** (`data/canonical/checkpoints.jsonl`, `data/derived/forecast_features.jsonl`, `data/schema_contract.json`), bukan cuma terhadap desain konseptual di ../architecture/architecture_v4.md.

### 4.1 Taksonomi — SOLVED, dua dataset F3 punya vocab appearance berbeda

Repo ini punya **dua** dataset F3:

| Dataset | Contract | `appearance` enum | Skala |
|---|---|---|---|
| `data/canonical/` (pilot lama) | `pilot-v1` / `landmark4-v1` | `uniform`, `uncertain`, `separated` (3 nilai) | 12 proyek |
| `data/full_synthetic/` (sedang dikerjakan, target arsitektur) | `full-synthetic-v2` / `landmark4-full-v1` | `uniform`, `creaming`, `heterogeneous`, `separated` (4 nilai, severity-graded di `scripts/build_full_dataset.py`) | 200 proyek target |

Cek distribusi aktual di `data/full_synthetic/canonical/checkpoints.jsonl`:

```
uniform:        4037
separated:       325
heterogeneous:   230
creaming:        208
```

**Ini nyaris sama persis dengan taksonomi CV** — 2 nama identik (`creaming`, `heterogeneous`), 2 lagi cuma beda penamaan (`stable_uniform`↔`uniform`, `phase_separation`↔`separated`). Kemungkinan besar bukan kebetulan: keduanya independen mengarah ke terminologi standar fenomena instabilitas emulsi kosmetik.

**Pemetaan yang diadopsi:**

| CV output | → | Appearance kanonis F3 (`full_synthetic`) |
|---|---|---|
| `stable_uniform` | → | `uniform` |
| `creaming` | → | `creaming` |
| `heterogeneous` | → | `heterogeneous` |
| `phase_separation` | → | `separated` |

Zero information loss, zero perlu nilai enum baru. Mapping ini didefinisikan sebagai **kontrak terpisah di sisi bridge CV** (`visual_screening_contract_version: "cv-appearance-map-v1"`), bukan mengubah `feature_schema_version` F3 — karena enum `appearance` di `full_synthetic` sudah mendukung ini apa adanya.

**Catatan penting**: dataset pilot lama (`data/canonical/`) **tidak diretrofit** untuk mapping ini. Ia sudah dibangun, divalidasi, dan dikunci lewat SHA-256 manifest sesuai disiplin di [../data/data_pipeline.md](../data/data_pipeline.md) ("snapshot yang berbeda dari build sebelumnya ditolak, bukan ditimpa diam-diam"). Integrasi CV diarahkan ke `full_synthetic` saja, yang memang jadi target skala produksi sesuai arsitektur.

### 4.2 CV cuma mengotomasi sebagian dari satu observasi checkpoint — BY DESIGN, bukan gap

Satu entri `observations[]` di `forecast_features.jsonl` berisi **tiga hal sekaligus**: `appearance` (kategorikal), `measurements.ph`, `measurements.viscosity_cp` (numerik dari instrumen). CV hanya mengisi `appearance`; `ph`/`viscosity_cp` tetap dari pH meter dan viskometer. **Ini memang scope yang dimaksud** — CV berperan sebagai otomasi capture visual, bukan pengganti seluruh proses pencatatan checkpoint. Dikonfirmasi: bukan limitasi yang perlu ditutup, cukup dinyatakan eksplisit di setiap klaim produk supaya tidak overselling ("CV mengotomasi field appearance", bukan "CV mengotomasi observasi checkpoint").

### 4.3 Confidence/abstention — SOLVED, diimplementasikan di ../architecture/architecture_v4.md §11.4

Enum `appearance` di `full_synthetic` (§4.1) **tidak punya nilai `uncertain` di level checkpoint** (beda dari pilot lama). Daripada menambah nilai enum baru khusus buat CV (yang berarti ubah kontrak F3 lagi), solusinya diformalkan sebagai *confidence gate* di [../architecture/architecture_v4.md §11.4](../architecture/architecture_v4.md#114-confidence-gate-dan-abstention): confidence kelas teratas memenuhi threshold → `proposed_appearance_patch` diisi sebagai draft yang tinggal dikonfirmasi; di bawah threshold → tidak ada draft sama sekali, field `appearance` checkpoint tetap kosong dan diisi manual peneliti seperti alur tanpa CV. Satu keputusan desain, menyatu dengan mekanisme konfirmasi di §4.4 — bukan mekanisme terpisah.

Titik awal threshold: dari confusion matrix run 3, kesalahan klasifikasi punya confidence mulai dari 0.48 sampai 0.98 — jadi confidence mentah bukan sinyal sempurna, tapi tetap berguna sebagai filter kasar. Threshold pasti (mis. 0.6) baru bisa dikalibrasi setelah ada data foto asli (Fase 2, §6), bukan diklaim final sekarang — ../architecture/architecture_v4.md §11.4 mencatat ini eksplisit sebagai starting point, bukan angka final.

### 4.4 Jalur human sign-off untuk CV — SOLVED, diimplementasikan di ../architecture/architecture_v4.md §11

Bayangkan skenario konkret: sampel sebenarnya cuma ada beberapa gelembung kecil (harusnya `uniform`), tapi CV membacanya sebagai `heterogeneous` dengan confidence 80%. Kalau ini ditulis langsung ke checkpoint tanpa dicek manusia:

1. Checkpoint di arsitektur ini didesain append-only/immutable (../architecture/architecture_v4.md §4) — begitu tersimpan, salah baca CV itu jadi bagian permanen dari record trial.
2. F3 membaca checkpoint itu apa adanya dan menghasilkan forecast risiko berdasarkan appearance yang **salah**.
3. Peneliti melihat forecast "risiko tinggi" dan bisa saja mengambil keputusan reformulasi/hentikan trial padahal sampelnya baik-baik saja — keputusan formulasi yang salah, dipicu satu foto yang salah dibaca, dan tidak ada yang pernah mengecek ulang karena sistem "mempercayai" CV begitu saja.
4. Ke depannya, kalau mau mengevaluasi "seberapa akurat CV di lapangan", datanya tidak ada — karena tidak pernah direkam mana prediksi yang dikoreksi manusia vs dipakai apa adanya.

Prinsip #10 ../architecture/architecture_v4.md (*"Human sign-off wajib. Tidak ada output AI yang otomatis memfinalkan formula, observasi, atau keputusan compliance."*) dan pola yang sudah ada di F5 (voice logging) itu justru satu-satunya titik yang mencegah skenario di atas. Ini sekarang diformalkan sebagai bagian arsitektur resmi: [../architecture/architecture_v4.md §11](../architecture/architecture_v4.md#11-f_cv-visual-screening-sebagai-asisten-capture-untuk-f3) mendefinisikan modul **F_CV** dengan kontrak `proposed_appearance_patch` + `per_class_probabilities` + `requires_confirmation: true` → user konfirmasi/koreksi → baru ditulis ke checkpoint kanonis → F3 baru jalan setelah checkpoint valid tersimpan — pola identik F5 (§10), modalitas beda (foto, bukan suara). Titik konfirmasi yang sama itu jadi sumber data untuk mengukur akurasi CV di real-world usage nanti (persentase prediksi yang dikoreksi manusia) — dicatat eksplisit di §11.6 sebagai dasar kalibrasi ulang threshold dan penentuan kapan gate validasi domain bisa dianggap terlewati.

### 4.5 Gate validasi domain — masih berlaku, sengaja belum terlewati

Sesuai §3: model belum tervalidasi di foto asli. [../architecture/architecture_v4.md §11.6](../architecture/architecture_v4.md#116-batas-tanggung-jawab-dan-status-validasi-domain) eksplisit melarang klaim phase-separation classification sebagai kebenaran final tanpa model visual tervalidasi domain. Bedanya dengan sebelumnya: sekarang eksplisit dicatat bahwa konfirmasi manusia (§4.4) berperan ganda sebagai mitigasi interim untuk status ini — bukan alasan untuk menganggap gate ini sudah terlewati. Menyambungkan output CV sebagai fitur F3 **tanpa** jalur konfirmasi tetap pelanggaran terhadap prinsip #2.

### 4.6 Kesimpulan kompatibilitas

**Keempat concern sudah punya jawaban desain yang eksplisit dan tercatat di arsitektur:** taksonomi solved via mapping langsung ke `full_synthetic` tanpa kehilangan informasi (§4.1); cakupan appearance-only dikonfirmasi by design, bukan gap (§4.2); confidence/abstention dan human-confirmation kini diformalkan sebagai modul **F_CV** di [../architecture/architecture_v4.md §11](../architecture/architecture_v4.md#11-f_cv-visual-screening-sebagai-asisten-capture-untuk-f3) (§4.3, §4.4). Yang tersisa murni soal eksekusi, bukan desain: gate validasi domain (§4.5) baru terlewati setelah ada data foto asli dan model divalidasi ulang (§6 Fase 1-2) — desain kontraknya sudah siap dipakai begitu itu terjadi.

---

## 5. Standardisasi kamera lab (usulan baru)

Bagian dari gap sim2real (§3) didominasi oleh variasi background/pencahayaan/vessel yang di dunia nyata jauh lebih liar daripada 4 preset di generator. Standardisasi capture mengurangi domain gap ini secara langsung — bukan cuma "nice to have", tapi prasyarat teknis supaya model (setelah dilatih ulang dengan foto asli) punya kesempatan realistis untuk generalisasi.

Usulan spesifikasi rig capture minimal:

| Parameter | Standar yang diusulkan | Alasan |
|---|---|---|
| Vessel | 1 jenis vial/wadah standar lab (bentuk, ukuran, material tetap) | Bentuk vessel jadi faktor nuisance yang dihilangkan, bukan sumber variasi |
| Background | Backdrop polos warna tunggal (mis. abu-abu netral), fixed | Menghilangkan variasi scene yang paling merusak generalisasi model kecil |
| Pencahayaan | Softbox/ring light tetap, posisi & intensitas dikalibrasi | Menghindari bayangan/refleksi tak terduga; mendekatkan ke asumsi "flat lighting" generator |
| Jarak & sudut kamera | Jarak tetap, sudut frontal tegak lurus vessel, tripod/rig fixed-mount | Framing konsisten antar sesi & antar peneliti |
| White balance & exposure | Preset manual tetap (bukan auto), exposure terkunci | Warna liquid harus konsisten dipakai sebagai sinyal, bukan bias kamera |
| Resolusi & format | Resolusi tetap, format tidak lossy berulang (hindari re-compress JPEG bertingkat) | Konsistensi kualitas input model |

Standardisasi ini **tidak menghilangkan kebutuhan validasi domain nyata** (§3) — ia mengurangi variance yang tidak relevan, sehingga budget data collection real bisa fokus melabeli variasi yang benar-benar relevan (jenis/tingkat ketidakstabilan), bukan menghabiskan sampel untuk menutupi variasi kamera yang seharusnya sudah dikontrol dari awal.

---

## 6. Rencana jika lolos ke inkubasi

### Fase 0 — Selaras skema (SELESAI, sudah diformalkan di [../architecture/architecture_v4.md §11](../architecture/architecture_v4.md#11-f_cv-visual-screening-sebagai-asisten-capture-untuk-f3))
- ✅ Pemetaan taksonomi (§4.1, §11.3): `stable_uniform→uniform`, `creaming→creaming`, `heterogeneous→heterogeneous`, `phase_separation→separated`, langsung ke enum `appearance` di `data/full_synthetic/`. Tidak perlu naikkan `feature_schema_version` F3 (enum sudah mendukung), cukup versionkan mapping-nya sendiri (`visual_screening_contract_version: "cv-appearance-map-v1"`).
- ✅ Kontrak output F_CV (§11.5): `predicted_label`, `confidence`, `per_class_probabilities`, `model_version`, `image_ref`, `proposed_appearance_patch`, `requires_confirmation: true` — mengikuti pola `f5_examples` yang sudah ada.
- ✅ Confidence gate (§4.3, §11.4): di bawah threshold, field `appearance` checkpoint dibiarkan kosong/pending untuk diisi manual, bukan dipaksa jadi nilai enum baru. Angka threshold pasti masih starting point, dikalibrasi ulang di Fase 2 dengan data foto asli.
- Sisa kerja Fase 0: implementasi kode nyata dari kontrak yang sudah didesain ini (belum ada baris kode produk, baru spesifikasi arsitektur).

### Fase 1 — Standardisasi capture & pengumpulan data asli
- Bangun rig capture sesuai §5.
- Kumpulkan foto asli berlabel formulator (real ground truth), minimal puluhan-ratusan sampel per kelas, dengan split by sequence/sesi (bukan random) mengikuti disiplin yang sama dengan pilot sintetis ini.
- Sisihkan held-out test set foto asli yang tidak pernah disentuh training — ini yang akan jadi angka akurasi pertama yang benar-benar bisa diklaim untuk dunia nyata.

### Fase 2 — Retraining dengan transfer learning
- Ganti `TinyVialCNN` ke backbone pretrained, fine-tune di atas data asli + (opsional) data sintetis sebagai pretraining tambahan.
- Re-tuning augmentasi, LR, epoch budget dari nol terhadap karakteristik foto asli.
- Evaluasi calibration (bukan cuma accuracy) karena confidence akan dipakai untuk keputusan abstain/confirm.

### Fase 3 — Integrasi F3 dengan human-in-the-loop
- Implementasikan flow: foto → CV propose → peneliti konfirmasi/koreksi → tulis ke checkpoint kanonis → F3 jalan hanya setelah checkpoint valid — identik dengan pola F5, modalitas berbeda.
- Audit event mencatat: `model_version` CV, confidence, apakah dikonfirmasi/dikoreksi manusia (mengikuti §14.2 ../architecture/architecture_v4.md).
- CV tetap **tidak pernah** mengisi `measurements.ph`/`viscosity_cp` — field itu tetap butuh instrumen atau input manual/voice (F5).

### Fase 4 — Perluasan setelah domain coverage test
- Baru pertimbangkan menambah kelas/produk family lain setelah Fase 2-3 terbukti generalize di domain O/W gel-cream, sesuai roadmap tertunda §17 ../architecture/architecture_v4.md.

---

## 7. Limitasi

- Dataset training seluruhnya render prosedural sintetis (`data_origin: synthetic_demo`), nol foto asli dilibatkan di piloting ini.
- Label berasal dari parameter generator (`annotation_basis: procedural_generator_parameters`), bukan assessment manusia terhadap sampel fisik.
- Akurasi 89.6% (run 3) hanya berlaku di dalam distribusi render sintetis yang sama; tidak ada dasar untuk mengekstrapolasi angka ini ke performa di foto asli.
- Model belum dikalibrasi (confidence mentah dari softmax, belum divalidasi terhadap frekuensi benar aktual) — beberapa kesalahan klasifikasi di run 3 punya confidence tinggi (0.91-0.98) padahal salah.
- Confusion `stable_uniform` ↔ `creaming` mengindikasikan model sensitif terhadap threshold parameter generator di ujung range, bukan konsep visual yang robust.
- Mekanisme human-confirmation dan confidence-gate/abstention sudah didesain formal ([../architecture/architecture_v4.md §11](../architecture/architecture_v4.md#11-f_cv-visual-screening-sebagai-asisten-capture-untuk-f3)), tapi **belum ada implementasi kode** — masih spesifikasi arsitektur, belum tersambung ke pipeline F3 nyata.
- Threshold confidence di §11.4 adalah starting point, belum dikalibrasi dari data nyata apa pun (sintetis maupun foto asli).
- Standardisasi kamera (§5) masih usulan desain, belum diimplementasikan atau diuji.

## 8. Klarifikasi untuk juri/reviewer inkubasi

- CV pipeline ini adalah **bukti workflow** (dataset generation → training → evaluation → artifact dengan provenance lengkap berjalan benar), bukan model visual screening yang siap pakai.
- Taksonomi kelas (`creaming`, `phase_separation`, `heterogeneous`) dipilih karena merepresentasikan fenomena instabilitas emulsi kosmetik nyata secara konsep — tapi belum divalidasi bahwa model bisa mengenalinya di foto sungguhan.
- "CV sebagai otomasi observasi" dalam roadmap produk **hanya mencakup field appearance/visual**, tidak menggantikan pengukuran pH/viskositas instrumen — klaim ke juri harus eksplisit membatasi scope ini agar tidak overselling.
- Peningkatan dari 26% → 89.6% test accuracy antara run 2 dan run 3 murni dari perbaikan arsitektur (satu baris pooling + tuning epoch/patience), dataset tidak diubah sama sekali — ini fakta yang bisa didemokan ulang secara langsung dari kedua notebook run yang tersimpan.
