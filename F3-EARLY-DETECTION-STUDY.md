# Kajian F3: Deteksi Dini Kegagalan Stabilitas dan Rencana Pivot

> Seluruh angka kuantitatif dalam dokumen ini berasal dari **synthetic-demo evaluation**.
> Tidak satu pun merupakan validasi ilmiah, klaim performa produksi, atau pengganti
> formal stability validation.

## 1. Ringkasan eksekutif

Klaim awal kami — "memangkas observasi 12 minggu menjadi 6 minggu" — **tidak bisa
dipertahankan** dan kami ganti.

Dua alasan. Pertama, minggu 0-12 dalam dataset kami sebetulnya sudah merupakan
*accelerated stability test*, bukan shelf life; memangkasnya berbenturan dengan
kewajiban regulasi. Kedua, dan lebih penting: menyatakan "formula ini aman, uji
boleh dihentikan lebih awal" adalah persis kelas kesalahan **false pass**, yang
dalam literatur diidentifikasi sebagai risiko keselamatan dan liabilitas brand.

Klaim penggantinya: **F3 memangkas siklus reformulasi serial, bukan durasi uji.**
Uji stabilitas tetap berjalan penuh; yang dipercepat adalah kapan formulator
mulai ronde perbaikan berikutnya.

Konsekuensi desainnya tegas: **F3 hanya mengeluarkan dua keluaran — "risiko
tinggi, mulai reformulasi" atau "lanjutkan observasi". F3 tidak pernah
mengeluarkan early pass.** Kelas false pass dihapus secara konstruksi, bukan
ditekan lewat tuning threshold.

## 2. Temuan literatur

### 2.1 Durasi uji yang sebenarnya

Postles (2018) menjalankan protokol yang direkomendasikan ISO/TR 18811:2018 dan
Cosmetics Europe terhadap 65 emulsi skala laboratorium, dengan titik waktu:

| Jenis uji | Kondisi | Titik waktu | Total |
|---|---|---|---|
| Accelerated | 4, 25, 40, 45 °C | initial, 1, 2, 4, 8, 12, **16** minggu | ~4 bulan |
| Real-time | 25 °C | initial, 24, 32, 48, 64, 72, **96** minggu | ~2 tahun |

Ekstrapolasi accelerated ke real-time memakai asumsi Q10 = 2 (setiap kenaikan
10 °C menggandakan laju reaksi), bersumber dari Cannell (1985) dan IFSCC
Monograph.

ISO/TR 18811:2018 **tidak menetapkan** kondisi, parameter, maupun kriteria uji —
produsen yang wajib menetapkan dan menjustifikasi protokolnya. EU Cosmetic
Regulation mewajibkan Safety Assessor mempertimbangkan stabilitas jangka panjang
produk sebelum dipasarkan.

Postles juga mencatat praktik industri: sampel uji umumnya mulai diuji **6 bulan
sampai 1 tahun sebelum** formula diproduksi skala industri. Artinya uji
stabilitas duduk di jalur kritis pengembangan produk.

### 2.2 Tidak semua parameter sama andalnya

Temuan utama Postles (2018): dari lima parameter yang diuji, **empat terbukti
tidak akurat sekaligus tidak presisi** untuk memprediksi stabilitas jangka
panjang.

| Parameter | Ambang prediktif | Keterangan |
|---|---|---|
| Viskositas | tidak melewati 16 minggu | Gagal mencapai target 96 minggu |
| Appearance | tidak melewati 16 minggu | Idem |
| Warna | tidak melewati 16 minggu | Idem |
| **pH** | **melewati 96 minggu** | Satu-satunya yang sesuai model Arrhenius |

Ini relevan langsung bagi kami: baseline F3 versi pertama bersandar pada
viskositas sebagai sinyal dominan — yaitu salah satu parameter yang justru
dinyatakan tidak prediktif.

**Batas penafsiran yang harus dijaga.** Temuan Postles adalah tentang
ekstrapolasi *accelerated → real-time*. F3 memprediksi *minggu-4 → minggu-12
dalam kondisi accelerated yang sama*, tanpa ekstrapolasi lintas suhu. Jadi
temuan itu tidak membatalkan viskositas untuk tugas F3. Yang dibatalkan adalah
klaim turunannya: **prediksi berbasis viskositas tidak boleh diklaim mengatakan
apa pun tentang shelf life nyata.**

### 2.3 Asimetri biaya kesalahan

Literatur menyatakan asimetri ini secara eksplisit:

| Kesalahan | Definisi | Dampak menurut Postles (2018) |
|---|---|---|
| **False fail** | Gagal di accelerated, sebenarnya aman di real-time | "Waste of developmental resource", **tanpa** risiko keselamatan — produk tidak pernah masuk pasar |
| **False pass** | Lolos accelerated, gagal di real-time | Terbaik: masalah kualitas. Terburuk: **risiko keselamatan publik dan liabilitas finansial brand** |

Inilah dasar keputusan desain kami. Kedua kesalahan tidak setara, jadi sistem
tidak boleh memperlakukannya setara.

## 3. Temuan audit dataset internal

Tiga putaran audit terhadap generator sintetis kami sendiri.

### 3.1 v1 — label adalah lookup dari nama skenario

Outcome ditentukan dari `scenario_family`, bukan dari mekanisme fisik. Tiga
skenario selalu `failed`, dua selalu `passed`. Karena tiap skenario punya laju
peluruhan viskositas khas, model cukup melakukan *scenario fingerprinting* lalu
membaca label dari tabel.

Akibatnya hubungan tren→kegagalan menjadi **non-monotonik dan tidak masuk akal
secara ilmiah**:

| Penurunan viskositas mg-4 | Fail rate |
|---|---|
| ~ −10% | 1.00 |
| ~ −7% | **0.00** |
| ~ −3% | 1.00 |
| ~ −0.6% | 0.00 |

PR-AUC test mencapai 0.99 — dan angka itu tidak berarti apa-apa. Ditemukan juga
dua bug: kondisi gagal `early_viscosity_drop` (drop 28%) tidak pernah tercapai
karena trajectory maksimal hanya ~19%, sementara `ph_drift` hampir selalu gagal
(0.98). Logika kondisionalnya efektif mati, tersisa konstanta per skenario.

### 3.2 v2 — hazard kausal, tetapi statis terhadap waktu

Label diganti model hazard: interaksi elektrolit×thickener, ketiadaan
emulsifier, storage 40 °C, deviasi proses, dan jarak pH dari 5,5. Hazard yang
sama menggerakkan trajectory dan probabilitas kegagalan.

Perbaikan nyata — skenario tidak lagi memprediksi label (fail rate 0,42-0,55 di
seluruh skenario), hubungan menjadi monotonik (0,31 → 0,72), PR-AUC turun ke
0,73 yang realistis.

**Tetapi cacat baru muncul saat diuji terhadap pertanyaan produk.** Karena
hazard dihitung sekali di t=0 lalu diekspresikan linear tiap minggu, observasi
lebih lama tidak menambah informasi apa pun:

| Landmark | mg 1 | mg 2 | mg 4 | mg 6 | mg 8 |
|---|---|---|---|---|---|
| ROC-AUC | 0.737 | 0.758 | 0.732 | 0.748 | 0.753 |

Datar. Dalam dunia sintetis itu, keputusan minggu 1 sama bagusnya dengan minggu
8 — sehingga pertanyaan "berapa lama perlu observasi" kehilangan makna.

Ditemukan pula bahwa metrik *lead time* yang sempat kami laporkan menyesatkan:
86% kegagalan tercatat di minggu 12, yang merupakan ujung horizon dan bukan
momen gagal teramati, sehingga lead time hampir selalu 12−4=8 secara konstruksi.

### 3.3 v3 — model survival dengan onset

Perbaikan: kegagalan diberi **waktu onset acak** yang ditarik dari distribusi
eksponensial dengan rata-rata memendek seiring hazard. Sebelum onset sampel
hanya berfluktuasi normal; sesudah onset ia terdegradasi dengan laju sebanding
hazard.

Ini memodelkan kenyataan bahwa sebagian ketidakstabilan baru muncul belakangan —
sehingga trial ber-onset lambat memang **tidak dapat dibedakan** dari trial
stabil pada minggu 4, apa pun modelnya.

Perubahan lain di v3:

1. **Minggu 16 ditambahkan** agar cocok dengan protokol accelerated nyata
   (sebelumnya berhenti di 12). Horizon label F3 tetap minggu 12.
2. **Label berbasis spesifikasi rilis** yang dibaca di readout, seperti praktik
   nyata: gagal bila viskositas turun >12% atau pH bergeser >0,5 dari baseline.
   Keacakan hidup di onset, bukan di label.
3. **Bobot keandalan sinyal dibalik** sesuai Postles: noise viskositas diperbesar
   (±750 cP), noise pH diperkecil (±0,012), sehingga pH menjadi kanal yang lebih
   bersih.

## 4. Rencana pivot

| Aspek | Sebelum | Sesudah |
|---|---|---|
| Klaim | Observasi 12 minggu → 6 minggu | Siklus reformulasi dipercepat 8 minggu per kegagalan tertangkap |
| Yang dipangkas | Durasi uji stabilitas | Waktu tunggu sebelum ronde reformulasi berikutnya |
| Keluaran F3 | Skor risiko dua arah | **Satu arah**: flag risiko tinggi, atau lanjutkan observasi |
| Early pass | Implisit mungkin | **Tidak pernah, by design** |
| Metrik utama | Akurasi / PR-AUC | Recall kegagalan, presisi alert, dan jumlah early pass (wajib 0) |
| Status uji | Berpotensi dipotong | Berjalan penuh sampai minggu 16, tidak diganggu |

Uji stabilitas tetap berjalan penuh. Yang berubah adalah kapan formulator boleh
mulai bekerja pada perbaikan. Dengan 2-4 ronde reformulasi per proyek, memangkas
8 minggu waktu tunggu per ronde gagal bernilai lebih besar daripada memangkas
satu kali durasi uji — dan tidak melanggar apa pun.

## 5. Bukti empiris

### 5.1 Informasi kini bertambah seiring waktu

Setelah onset diperkenalkan, ROC-AUC naik monoton terhadap lama observasi —
properti yang wajib ada agar pertanyaan "berapa lama observasi" bermakna:

| Landmark | ROC-AUC | Recall | Presisi alert | Kegagalan tertangkap | Early pass | Minggu reformulasi dihemat |
|---|---|---|---|---|---|---|
| Minggu 1 | 0.785 | 94.4% | 69.9% | 51/54 | **0** | 561 |
| Minggu 2 | 0.866 | 96.3% | 74.3% | 52/54 | **0** | 520 |
| **Minggu 4** | **0.894** | **92.6%** | **76.9%** | **50/54** | **0** | **400** |
| Minggu 6 | 0.942 | 88.9% | 84.2% | 48/54 | **0** | 288 |
| Minggu 8 | 0.972 | 94.4% | 94.4% | 51/54 | **0** | 204 |

Tradeoff-nya terbaca jelas: landmark makin awal menghemat lebih banyak minggu,
landmark makin lambat memberi presisi lebih tinggi (lebih sedikit reformulasi
sia-sia). Minggu 4 dipilih sebagai titik operasi default.

### 5.2 Ablation: dari mana sinyalnya datang

| Landmark | Fitur formula F2 + proses saja | Fitur tren saja | Gabungan |
|---|---|---|---|
| Minggu 1 | 0.797 | 0.497 | 0.785 |
| Minggu 2 | 0.797 | 0.714 | 0.866 |
| Minggu 4 | 0.797 | 0.803 | 0.894 |
| Minggu 6 | 0.797 | 0.913 | 0.942 |
| Minggu 8 | 0.797 | 0.958 | 0.972 |

Tiga bacaan penting:

1. **Tren saja tidak berguna di minggu 1** (0,497, setara lempar koin) dan baru
   melampaui fitur formula di minggu 4.
2. Di minggu 1 model gabungan (0,785) justru sedikit **lebih buruk** daripada
   fitur formula saja (0,797) — fitur tren yang belum bermakna hanya menambah
   noise. Jangan berikan fitur tren sebelum ia membawa sinyal.
3. **Angka 0,797 pada kolom pertama tidak boleh dibaca sebagai temuan.**
   Lihat peringatan di bawah.

### 5.2.1 Peringatan: kolom fitur formula bersifat sirkular

Sepuluh fitur pada kolom pertama merekonstruksi `latent_hazard` generator dengan
**R² = 0,991**. Model yang diberi nilai hazard asli secara langsung hanya
mencapai AUC 0,858 — nyaris setara.

Sebabnya terlihat saat disandingkan dengan fungsi `instability_hazard()` di
`scripts/build_full_dataset.py`:

| Suku hazard | Fitur yang mewakilinya |
|---|---|
| `1.30 × electrolyte_thickener_risk` | `f2_electrolyte_thickener_risk` |
| `0.85 × emulsifier_missing` | `f2_emulsifier_balance_watch` |
| `0.30 × electrolyte_load` | `f2_electrolyte_load` |
| `0.55 × (storage == 40 °C)` | `storage_temperature_c` |
| `0.40 × process_penalty` | `heating_temp_c`, `homogenization_rpm`, `mixing_time_min` |
| `0.45 × abs(ph0 − 5.5)` | tidak ada di set ini |

Lima dari enam suku adalah fitur itu sendiri. Model tidak menemukan bahwa
komposisi formula memprediksi stabilitas — ia membalik fungsi yang kami tulis.
AUC 0,797 adalah gema dari bobot yang kami tetapkan sendiri, bukan bukti
empiris. Plafon 0,858 pun bukan batas kemampuan model melainkan batas dari
keacakan onset yang sengaja dimasukkan.

Perlu dibedakan derajat kesirkularan dua kelompok fitur:

- **Fitur tren** (pH, viskositas): kesirkularan ringan. Di lab nyata pun
  spesifikasi pass/fail dibaca dari pengukuran yang sama, sehingga hubungan
  "sampel terdegradasi → gagal spec" mendekati tautologi di dunia nyata juga.
- **Fitur formula F2**: kesirkularan penuh. Di dunia nyata tidak ada yang tahu
  bahwa Carbomer bersama elektrolit bernilai 1,30 satuan hazard. Angka itu kami
  karang.

Yang tetap sah adalah **arsitekturnya** — bahwa F2 memasok faktor risiko
deterministik ke F3 (`ARCHITECTURE-V4.md` §9.6) masuk akal secara domain, karena
inkompatibilitas elektrolit-thickener memang risiko formulasi terdokumentasi dan
karena itulah ia ada di rule base F2 sejak awal. Yang **tidak** sah adalah
besarannya. Seberapa kuat faktor-faktor itu benar-benar memprediksi stabilitas
hanya dapat dijawab oleh data lab asli.

Konsekuensi praktis: Mode A (`ARCHITECTURE-V4.md` §9.2) **konsisten** dengan
hasil ini, tetapi tidak dibuktikan olehnya. Kalibrasi Mode A terhadap data nyata
tetap menjadi prasyarat sebelum klaim apa pun dibuat.

### 5.3 Model baseline pada titik operasi minggu 4

Model terpilih `stability-sentinel-random_forest-v1`, threshold 0,321 dituning di
validation, dievaluasi sekali di test (n = 86):

| Metrik | Nilai |
|---|---|
| Recall kegagalan | 0.944 |
| Presisi alert | 0.750 |
| ROC-AUC | 0.858 |
| Early pass dikeluarkan | 0 |
| Lead time rata-rata | 3.8 minggu (n = 51) |

Lead time di sini adalah jarak nyata antara alert minggu-4 dan minggu saat
spesifikasi benar-benar terlanggar. Pada versi dataset sebelumnya angka ini
tidak bermakna karena 86% kegagalan tercatat di minggu 12; kini `failure_week`
tersebar sehingga angkanya dapat dibaca apa adanya.

Peringkat kepentingan fiturnya berubah sesuai desain:

| Fitur | Permutation importance |
|---|---|
| `ph_change` | **+0.177** |
| `f2_electrolyte_thickener_risk` | +0.019 |
| `storage_temperature_c` | +0.008 |
| `ph_current` | +0.008 |
| `f2_emulsifier_balance_watch` | +0.007 |
| `viscosity_change_pct` | −0.005 |

pH kini menjadi sinyal dominan dan viskositas praktis tidak menyumbang —
konsisten dengan temuan Postles (2018) di §2.2, dan merupakan hasil langsung
dari pembalikan bobot noise di generator.

> Catatan: angka di §5.1-5.2 berasal dari `landmark_sweep.py` yang memakai
> Logistic Regression seragam agar perbandingan antar landmark adil. Angka di
> §5.3 berasal dari `train_stability_sentinel.py` yang memilih model terbaik
> lewat validation. Keduanya konsisten di minggu 4 (recall 0,93 vs 0,94).

### 5.4 Analisis sensitivitas bobot — klaim yang tidak bergantung pada angka

§5.2.1 menunjukkan bobot hazard kami adalah asumsi, bukan pengukuran. Maka
pertanyaan yang layak dijawab bukan "seberapa akurat modelnya" melainkan:
**seandainya bobot itu salah, apakah kebijakan keputusannya tetap berdiri?**

Metode (`feature_3/weight_sensitivity.py`): 30 replikat, masing-masing menarik
vektor bobot baru, **meregenerasi seluruh dataset** dari bobot itu, melatih
ulang, menyetel threshold di validation, lalu mengevaluasi sekali di test.
Rentang tiap faktor sebagai kelipatan nilai yang diasumsikan:

| Faktor | Rentang diuji |
|---|---|
| `electrolyte_thickener_risk` | 0,1× – 2,0× |
| `emulsifier_missing` | 0,1× – 2,0× |
| `electrolyte_load` | 0,1× – 2,0× |
| `storage_40c` | 0,3× – 2,0× |
| `process_penalty` | 0,3× – 2,0× |
| `ph_deviation` | 0,3× – 2,0× |

Faktor formula sengaja diberi lantai 0,1× agar skenario paling merugikan bagi
desain F2→F3 — "komposisi formula hampir tidak berpengaruh, hanya tren terukur
yang penting" — masuk ke dalam rentang uji.

Hasil atas 30 replikat (tidak ada yang degenerate):

| Metrik | min | median | max |
|---|---|---|---|
| ROC-AUC | 0.819 | 0.888 | 0.935 |
| Recall kegagalan | 0.830 | 0.915 | 0.962 |
| Presisi alert | 0.738 | 0.786 | 0.875 |
| Fail rate dataset | 0.463 | 0.616 | 0.737 |

- **30/30 replikat memenuhi target recall ≥ 0,80.**
- **Total early pass dikeluarkan: 0.**
- Fail rate bergerak 0,46–0,74, membuktikan perturbasi bobot benar-benar
  mengubah datanya dan bukan sekadar mengocok noise.

**Batas klaim ini — penting.** Analisis ini menguji ketahanan terhadap *bobot
relatif* antar faktor, **bukan** terhadap *bentuk fungsionalnya*. Yang tetap
diasumsikan dan tidak diuji di sini:

- hazard berupa penjumlahan linear dari faktor-faktor tersebut;
- onset berdistribusi eksponensial dengan rata-rata `14/(1+hazard)`;
- degradasi linear terhadap waktu sejak onset;
- spesifikasi rilis di viskositas 12% dan pH 0,5;
- pH merupakan kanal yang lebih bersih daripada viskositas.

Bila salah satu asumsi struktural itu keliru, analisis ini tidak berkata apa
pun. Rentang 0,1×–2,0× pun kami yang menetapkan. Jadi klaim yang sah dari §5.4
berbunyi persis: *dalam bentuk model yang kami asumsikan, kebijakan alert satu
arah memenuhi targetnya di seluruh rentang bobot yang diuji* — bukan bahwa
sistemnya tervalidasi.

## 6. Target terukur

| Metrik | Target | Capaian mg-4 | Alasan |
|---|---|---|---|
| Recall kegagalan | ≥ 0.80 | 0.944 | Mayoritas ronde gagal tertangkap lebih awal |
| **Early pass dikeluarkan** | **0** | **0** | Kelas false pass dihapus secara konstruksi |
| Presisi alert | ≥ 0.60 | 0.750 | Batas "waste of developmental resource" yang ditolerir |
| Penghematan per kegagalan | 8 minggu | 8 minggu | Minggu 4 vs readout minggu 12 |

Properti `early_pass_issued = 0` ditegakkan oleh kontrak output di
`feature_3/train_stability_sentinel.py` dan diuji di
`tests/test_f3_stability_sentinel.py::test_low_risk_never_clears_a_trial_early`,
sehingga ia tidak bergantung pada pemilihan threshold.

Target ini bertahan di seluruh 30 replikat perturbasi bobot (§5.4), sehingga
pemenuhannya tidak bergantung pada nilai bobot tertentu yang kami tebak.

### 6.1 Klaim mana yang boleh dipakai di depan penilai

Membedakan ini penting supaya tidak mengulang kesalahan mengutip angka sirkular.

| Klaim | Status | Dasar |
|---|---|---|
| F3 tidak pernah mengeluarkan early pass | **Sah** | Konstruksi kontrak output + test; tidak bergantung data |
| F2 memasok feature berversi ke F3 tanpa prosa mentah | **Sah** | Implementasi + test, sesuai §9.6 |
| Abstain saat checkpoint baseline/landmark hilang | **Sah** | Implementasi + test |
| Split per family tanpa kebocoran, test dievaluasi sekali | **Sah** | Verifikasi split + disiplin evaluasi |
| Kebijakan alert bertahan walau bobot hazard salah 0,1×–2,0× | **Sah, bersyarat** | §5.4, terbatas pada bentuk model yang diasumsikan |
| Observasi lebih lama menaikkan akurasi | **Sah untuk dataset ini** | §5.1; properti generator v3, bukan temuan dunia nyata |
| Asimetri false pass vs false fail | **Sah** | Fakta eksternal, Postles (2018) |
| pH lebih andal daripada viskositas | **Sah** | Fakta eksternal, Postles (2018) |
| "Model F3 akurat X%" sebagai kemampuan dunia nyata | **Tidak sah** | Sirkular terhadap generator (§5.2.1) |
| Komposisi formula memprediksi stabilitas sekuat ini | **Tidak sah** | Bobotnya kami karang (§5.2.1) |

Bila ditanya "seberapa akurat?", jawaban yang benar: *"pada data sintetis kami
ROC-AUC 0,86 dan bertahan 0,82–0,94 saat asumsinya diguncang; angka itu tidak
dapat ditransfer ke dunia nyata, dan §10 adalah rencana kalibrasinya."*

## 7. Batasan

1. Seluruh angka berasal dari data sintetis berbasis seeded onset model. Bukan
   validasi ilmiah dan bukan klaim performa produksi.
2. Generator dan model disusun oleh tim yang sama, sehingga struktur datanya
   diketahui saat memodelkan. Angka di atas membuktikan benchmark tidak lagi
   dapat diakali murah — **bukan** membuktikan modelnya tervalidasi.
3. Secara khusus, fitur formula F2 bersifat sirkular terhadap fungsi hazard
   generator (R² = 0,991; lihat §5.2.1). Kontribusinya terhadap AUC tidak boleh
   dikutip sebagai bukti bahwa komposisi formula memprediksi stabilitas nyata.
   Analisis sensitivitas (§5.4) meredam dampaknya tetapi tidak menghapusnya:
   ia menguji bobot, bukan bentuk fungsional.
4. Test set berukuran 86 baris, sehingga interval kepercayaan tiap metrik lebar.
5. Prediksi berbasis viskositas tidak boleh diklaim mengatakan apa pun tentang
   shelf life nyata (lihat §2.2).
6. `likely_failure_mode` belum tersedia karena label masih biner.
7. F3 tidak menggantikan formal stability validation, sesuai
   `ARCHITECTURE-V4.md` §9.1.

## 8. Roadmap

Diurutkan dari yang sudah dikerjakan ke yang sengaja diparkir.

### Selesai

| Item | Artefak |
|---|---|
| Audit kesirkularan dan pembuktiannya (R² = 0,991) | §5.2.1 |
| Generator ber-onset agar observasi berbayar | `scripts/build_full_dataset.py` |
| Titik waktu selaras protokol accelerated (sampai minggu 16) | `WEEKS` |
| Label dari spesifikasi rilis, bukan lookup skenario | `spec_violation()` |
| Kebijakan alert satu arah, tanpa early pass | `build_sample_forecast()` + test |
| Kurva akurasi vs lama observasi | `feature_3/landmark_sweep.py` |
| Analisis sensitivitas bobot | `feature_3/weight_sensitivity.py` |

### Diparkir — menunggu data nyata

Ini **bukan** pekerjaan yang dilewatkan, melainkan pekerjaan yang tidak dapat
diselesaikan tanpa data lab. Dicatat agar batasnya jelas, bukan tersembunyi.

**P1. Kalibrasi bobot hazard terhadap data terbitan.**
Tidak ada dataset agregat terbuka; datanya tersebar di tabel paper
masing-masing, umumnya 3-10 formulasi dengan titik hari 0/7/14/30. Menambang
10-20 paper menghasilkan sekitar 50-150 trajectory nyata — **tidak cukup untuk
melatih model**, tetapi cukup untuk menguji **arah** asumsi kami: apakah formula
carbomer+elektrolit betul kehilangan viskositas lebih banyak. Itu mengubah bobot
karangan menjadi bobot yang pernah dikonfrontasi kenyataan.

Mesin ingest-nya sudah ada (`scripts/ingest_open_sources.py`,
`scripts/build_public_evidence.py`) dengan satu sumber berjalan
(PMC7407566, CC-BY-4.0), sehingga yang dibutuhkan adalah ekstraksi tabel
tambahan, bukan infrastruktur baru.

**P2. Uji ketahanan terhadap bentuk fungsional, bukan hanya bobot.**
§5.4 mengasumsikan hazard linear, onset eksponensial, dan degradasi linear.
Menguji bentuk alternatif (misal onset Weibull, degradasi non-linear)
memperluas klaim ketahanan. Dapat dikerjakan tanpa data nyata, tetapi nilainya
rendah sebelum P1 memberi tahu bentuk mana yang layak diuji.

**P3. `likely_failure_mode` multi-kelas.**
Kontrak §9.5 menyediakan field ini, tetapi label kami masih biner. Perlu
definisi mode kegagalan yang disepakati formulator sebelum dimodelkan.

**P4. Integrasi F1 untuk mengisi `evidence_ids`.**
Saat ini selalu kosong. Membutuhkan penyambungan retrieval F1 ke output F3.

**P5. Kalibrasi probabilitas terhadap data nyata.**
Brier score dan reliability curve saat ini diukur terhadap dunia sintetis kami
sendiri, sehingga "probabilitas 0,8 berarti 80% gagal" belum bermakna di luar.

## 9. Referensi

1. **Postles, A. (2018).** *Factors affecting the measurement of stability and
   safety of cosmetic products.* PhD thesis, Bournemouth University, in
   collaboration with Solab Group Ltd.
   <https://eprints.bournemouth.ac.uk/32141/1/POSTLES,%20Andrew_Ph.D._2018.pdf>
   — sumber utama: protokol titik waktu accelerated/real-time, studi 65 emulsi,
   reliabilitas per parameter, dan asimetri false pass/false fail.
2. **ISO/TR 18811:2018.** *Cosmetics — Guidelines on the stability testing of
   cosmetic products.* <https://www.iso.org/standard/63465.html>
3. **Cannell, J. S. (1985).** Fundamentals of stability testing.
   *International Journal of Cosmetic Science*, 7(6), 291. — sumber asumsi
   Q10 = 2; dikutip dalam Postles (2018).
4. **Cosmetics Europe / Colipa (2004).** *Guidelines on Stability Testing of
   Cosmetic Products.* — dikutip dalam Postles (2018).
5. **Personal Care Products Council (2011).** *Guidelines for Industry — The
   Stability Testing of Cosmetics.* — dikutip dalam Postles (2018).

## 10. Artefak terkait

- Generator dataset: `scripts/build_full_dataset.py` (`full-synthetic-v2`)
- Kontrak dataset: `FULL-DATASET.md`
- Model baseline F3: `feature_3/train_stability_sentinel.py`
- Analisis landmark: `feature_3/landmark_sweep.py` → `feature_3/outputs/1/landmark_sweep.json`
- Sensitivitas bobot: `feature_3/weight_sensitivity.py` → `feature_3/outputs/1/weight_sensitivity.json`
- Test kontrak F3: `tests/test_f3_stability_sentinel.py`
- Arsitektur: `ARCHITECTURE-V4.md` §9 (F3), §13.3 (evaluasi)
