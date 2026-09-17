# PRD: Integrasi Web ParaLab dengan Model Gateway F1 sampai F5

> **Status:** draft untuk implementasi
> **Pemilik dokumen:** tim ParaLab
> **Repository terkait:** `paralab-architecture` (dokumen ini) dan `paralab-website` branch `feat/model-integration`
> **Dokumen rujukan:** [docs/architecture/architecture_v5.md](docs/architecture/architecture_v5.md), [docs/deployment/local-qwen-host-handoff.md](docs/deployment/local-qwen-host-handoff.md) pada branch `docs/local-qwen-host-handoff`

---

## 1. Ringkasan

Website ParaLab sudah memanggil lima endpoint model (F1 sampai F5). Dua di antaranya sudah dilayani `api/app.py`, tiga sisanya belum ada di sisi server. Dokumen ini menetapkan kontrak persis tiap endpoint, memetakan tiap kontrak ke fungsi Python yang sudah ada dan teruji di repository ini, lalu menentukan apa yang harus dibangun agar seluruh alur F1 sampai F5 berjalan tanpa mengubah model maupun arsitektur.

Kesimpulan awal dari audit kode kedua repository:

| Modul | Endpoint | Status server | Pekerjaan yang dibutuhkan |
|---|---|---|---|
| F1 Evidence Copilot | `POST /v1/f1/query` | Belum ada | Bungkus `f1_hybrid_retrieval` + `f1_runtime` + Qwen |
| F2 Formulation Guardrail | `POST /v1/f2/health-check` | Belum ada | Bungkus `screen_formula`, tanpa model |
| F3 Stability Sentinel | `POST /v1/f3/forecasts` | **Sudah ada** | Tidak ada |
| F4 Next Validation Step | `POST /v1/f4/next-validation` | **Sudah ada** | Tidak ada |
| F5 Voice Log | `POST /v1/f5/transcribe-draft` | Belum ada | Bungkus `f5_runtime` + Qwen, setelah keputusan D-1 |

Tidak ada satu pun kebutuhan yang menuntut training ulang, perubahan feature schema, atau perubahan kontrak data. Seluruh pekerjaan berada di lapisan adaptor HTTP.

---

## 2. Latar belakang dan masalah

Website memiliki dua versi yang berbeda jauh:

- Branch `master` hanya terhubung ke F3. Seluruh fungsi lain berjalan sebagai heuristik lokal di browser: saran formula memakai tabel klaim ke bahan yang ditulis tangan, pencatatan suara memakai Web Speech API, analisis citra memakai pembacaan piksel canvas.
- Branch `feat/model-integration` sudah memanggil F1, F2, F4, dan F5 ke satu gateway melalui `VITE_MODEL_API_BASE`, sementara F3 tetap melalui `VITE_PARALAB_F3_URL`.

Selama gateway belum menyediakan F1, F2, dan F5, branch `feat/model-integration` tidak dapat digabungkan ke `master` tanpa membuat tiga tombol di UI selalu gagal. Dokumen ini menutup jarak tersebut.

Model inference berjalan pada satu laptop Linux milik anggota tim karena total artefak model sekitar 3,5 GB dan membutuhkan GPU. Konsekuensinya gateway harus dianggap sebagai layanan tunggal berkapasitas terbatas, bukan cluster.

---

## 3. Tujuan dan batasan

### 3.1 Tujuan

1. Website dapat menjalankan seluruh alur F1 sampai F5 terhadap satu gateway.
2. Setiap kontrak HTTP dipetakan ke fungsi Python yang sudah ada, bukan implementasi baru yang menduplikasi logika.
3. Seluruh prinsip keselamatan architecture v5 tetap dipertahankan di jalur HTTP.
4. Kegagalan layanan menghasilkan pesan yang dapat dibaca peneliti, bukan angka pengganti.

### 3.2 Di luar cakupan

1. Authentication, authorization, dan multi-tenant.
2. Database runtime dan persistence audit event.
3. Integrasi CV ke pipeline utama. Pilot CV tetap berstatus `concept_only_synthetic_render_pilot`.
4. Training ulang model apa pun.
5. Perubahan feature schema F3 atau rule F2.
6. Deployment cloud dengan skala lebih dari satu worker.

### 3.3 Prinsip yang tidak boleh dilanggar

Disalin dari architecture v5 pasal 3 dan wajib dipertahankan pada setiap endpoint:

1. Tidak ada early pass. F3 hanya mengeluarkan `flag_high_risk`, `continue_observation`, atau abstain.
2. Abstain lebih aman daripada menebak. Data kurang atau domain tidak didukung menghentikan forecast.
3. F2 tetap deterministik. Qwen tidak boleh menjalankan atau menggantikan rule engine.
4. F1 tidak menyuntikkan narasi atau skor relevansi sebagai feature numerik F3.
5. Output F5 dan CV tidak boleh menulis checkpoint tanpa konfirmasi manusia.
6. Seluruh keluaran membawa `data_origin: synthetic_demo` dan tidak boleh dipromosikan sebagai bukti ilmiah.

---

## 4. Arsitektur target

```text
Browser (paralab-website)
  │
  │  VITE_MODEL_API_BASE  ────────────────┐
  │  VITE_PARALAB_F3_URL  ────────────────┤   keduanya harus menunjuk
  │                                        │   ke origin yang sama
  ▼                                        ▼
HTTPS tunnel (Cloudflare Tunnel atau ngrok)
  │
  ▼
127.0.0.1:7860  uvicorn api.app:app  (1 worker)
  │
  ├── GET  /health                    kesiapan tiap artefak
  ├── POST /v1/f1/query               retrieval + Qwen + guardrail teks
  ├── POST /v1/f2/health-check        rule engine deterministik, tanpa model
  ├── POST /v1/f3/forecasts           artefak joblib hash-verified
  ├── POST /v1/f4/next-validation     heuristik deterministik, tanpa model
  └── POST /v1/f5/transcribe-draft    Qwen ekstraksi terstruktur
  │
  ▼
Semaphore tunggal (PARALAB_MODEL_CONCURRENCY=1)
  └── satu generasi Qwen aktif pada satu waktu
```

Keputusan penting: **seluruh endpoint dilayani satu proses pada port 7860**. F3 dan F4 tidak dipindahkan ke proses terpisah, karena artefak F3 berupa joblib kecil yang tidak bersaing memori dengan Qwen, dan memisahkannya akan memaksa dua tunnel HTTPS.

---

## 5. Kontrak endpoint

Seluruh field pada bagian ini diambil dari pembacaan langsung kode website branch `feat/model-integration` dan modul Python pada repository ini. Nama field tidak boleh diubah sepihak di satu sisi.

### 5.1 `GET /health`

Sudah ada, tetapi harus diperluas. Implementasi sekarang hanya melaporkan artefak F3.

**Response yang dibutuhkan:**

```json
{
  "status": "ok",
  "model_version": "stability-sentinel-v1",
  "data_origin": "synthetic_demo",
  "cv_status": "concept_only_synthetic_render_pilot",
  "components": {
    "f3_artifact": "ready",
    "qwen": "ready",
    "f1_embeddings": "ready",
    "f1_corpus": "ready",
    "whisper": "ready"
  }
}
```

Aturan implementasi:

1. Empat field pertama wajib dipertahankan apa adanya. `src/lib/paralab/f3.ts` fungsi `cekKesehatanF3()` membaca `model_version`, `data_origin`, dan `cv_status` untuk menandai status di UI.
2. `components` adalah tambahan baru. Nilai per komponen: `ready`, `unavailable`, atau `disabled`.
3. Komponen yang gagal dimuat tidak boleh dilaporkan `ready`. Handoff doc menyebut ini eksplisit.
4. `status` bernilai `ok` hanya jika seluruh komponen yang tidak `disabled` bernilai `ready`. Selain itu `degraded`.
5. Endpoint ini tidak boleh memuat model saat dipanggil. Seluruh pemuatan terjadi saat startup.

### 5.2 `POST /v1/f1/query` (baru)

**Pemanggil:** `src/components/paralab/DocCopilot.tsx` baris 198, dirender dari `src/routes/doc.$id.tsx` baris 431 sebagai panel "AI Copilot Jurnal".

**Request:**

```json
{ "query": "Kenapa gel cream mengalami penurunan viskositas?" }
```

Website tidak mengirim `top_k`. Server memakai default internal, disarankan 5.

**Response:**

```json
{
  "query": "Kenapa gel cream mengalami penurunan viskositas?",
  "evidence_status": "sufficient",
  "evidence": [
    {
      "source_id": "J-2024-072-T03",
      "hybrid_score": 0.71,
      "outcome": "failed",
      "failure_mode": "viscosity_loss",
      "journal_title": "Judul jurnal sintetis"
    }
  ],
  "answer": {
    "summary": "Ringkasan grounded dalam Bahasa Indonesia.",
    "limitations": "Evidence ini berasal dari data sintetis dan memerlukan validasi R&D manusia."
  },
  "requires_human_review": true,
  "limitations": ["Evidence demo menggunakan data sintetis berbasis skenario."]
}
```

**Pemetaan ke kode yang sudah ada:**

| Field response | Sumber |
|---|---|
| `evidence_status` | `scripts/f1_hybrid_retrieval.py`, nilai `sufficient` atau `insufficient` |
| `evidence[]` | hasil retrieval yang dikembalikan sebagai `related_cases`, **di-rename menjadi `evidence`** |
| `evidence[].source_id`, `hybrid_score` | langsung dari retrieval |
| `evidence[].outcome`, `failure_mode`, `journal_title` | opsional di sisi website, diambil dari katalog evidence bila tersedia |
| `answer` | hasil `scripts/f1_runtime.py::finalize_summary()` yang mengembalikan `{summary, limitations}` |
| `limitations` | list dari retrieval |

**Aturan implementasi:**

1. Jalankan retrieval lebih dulu. Jangan pernah memanggil Qwen sebelum retrieval selesai.
2. Bila `evidence_status` bernilai `insufficient`, kembalikan response dengan `answer: null` dan **jangan panggil Qwen**. Website sudah menangani `answer` bernilai null.
3. Materi yang dikirim ke Qwen harus berasal dari `f1_runtime.py::prepare_summary_request()`, bukan baris evidence mentah. Fungsi ini menyaring field ke daftar aman dan menjalankan `redact_f1_numbers()`.
4. Seluruh output Qwen harus melewati `f1_runtime.py::finalize_summary()`. Fungsi ini menolak ringkasan yang memuat persentase, pH, cP, RPM, atau derajat Celsius, dan melampirkan kalimat limitasi wajib.
5. Bila `finalize_summary()` melempar `ValueError`, jangan kembalikan teks mentah. Kembalikan `answer: null` disertai `evidence` yang tetap terisi, sehingga peneliti masih melihat sumbernya.
6. Jangan pernah membocorkan formula, konsentrasi bahan, prompt mentah, atau stack trace.

**Catatan penting.** Bentuk response pada `docs/deployment/local-qwen-host-handoff.md` sudah usang. Dokumen tersebut menulis `summary` di level atas, `related_cases`, dan `limitations` berupa string tunggal. Website mengharapkan bentuk bersarang seperti di atas. **Bentuk pada PRD ini yang berlaku**, karena memisahkan hasil retrieval deterministik dari hasil generasi model, dan lebih cocok dengan nilai balik fungsi Python yang sudah ada. Handoff doc harus diperbarui mengikuti dokumen ini.

### 5.3 `POST /v1/f2/health-check` (baru)

**Pemanggil:** `src/routes/journal.$id.tsx` baris 198, fungsi `periksaFormulaDanRisiko()`.

**Request:**

```json
{
  "formula": [{ "bahan": "Niacinamide", "pct": 5.0 }],
  "context": { "target_skin": "oily" },
  "ph": 5.7
}
```

**Response:** kembalikan nilai `screen_formula()` apa adanya.

```json
{
  "screened_at": "2026-09-18T10:00:00",
  "rule_version": "2026.09",
  "overall_status": "warning",
  "disclaimer": "...",
  "results": [
    {
      "input": "Niacinamide",
      "ingredient_id": "niacinamide",
      "inci_name": "Niacinamide",
      "status": "warning",
      "rules_fired": [
        {
          "rule_id": "...",
          "rule_version": "2026.09",
          "severity": "warning",
          "source_id": "...",
          "rationale": "...",
          "requires_human_review": true
        }
      ],
      "requires_human_review": true
    }
  ],
  "derived_features": { "final_ph": 5.7, "electrolyte_load": "high" },
  "model_coverage": { "status": "supported_demo_domain", "reason": "..." },
  "requires_human_signoff": true
}
```

**Pemetaan ke kode yang sudah ada:**

Fungsi `modules/f2_guardrail.py::screen_formula(formula, konteks=None, ph=None)` mengembalikan tepat delapan kunci di atas. Tipe `F2Screening` pada `src/lib/paralab/model-adapters.ts` mendeklarasikan delapan kunci yang sama. Tidak ada satu pun field yang meleset.

**Aturan implementasi:**

1. Endpoint ini **tidak boleh memanggil model apa pun**. Ia deterministik dan harus tetap deterministik.
2. Pemetaan nama parameter satu-satunya: `context` pada request dipetakan ke argumen `konteks`.
3. `ph` boleh `null`. Nilainya mengalir ke `derive_features(results, ph=ph)` dan muncul kembali sebagai `derived_features.final_ph`.
4. Endpoint ini tidak perlu semaphore dan tidak boleh ikut antre di belakang generasi Qwen.

### 5.4 `POST /v1/f3/forecasts` (sudah ada)

**Pemanggil:** `src/lib/paralab/f3.ts` fungsi `jalankanF3()`, dirender oleh `src/components/paralab/PanelSentinel.tsx` dari `src/routes/journal.$id.tsx` baris 575.

Kontrak sudah diverifikasi cocok field demi field. Tiga belas field yang dibaca website tersedia seluruhnya pada nilai balik `build_sample_forecast()` di `modules/f3_stability_sentinel/train_stability_sentinel.py` ditambah `result.update()` di `modules/f3_stability_sentinel/inference.py`:

`trial_id`, `decision`, `failure_risk`, `risk_band`, `confidence`, `forecast_week`, `forecast_horizon`, `recommended_action`, `key_signals`, `limitations`, `f2_screening`, `model_version`, `data_origin`.

Jalur abstain mengembalikan `decision: "abstain_human_review_required"` beserta `reason`, dan website membacanya.

**Tidak ada pekerjaan implementasi.** Endpoint ini hanya perlu ikut pindah ke proses gateway pada port 7860.

### 5.5 `POST /v1/f4/next-validation` (sudah ada)

**Pemanggil:** `src/routes/journal.$id.tsx` baris 216, fungsi `muatLangkahValidasi()`, hasilnya dirender `NextValidationCard` pada baris 607.

**Request** dibentuk oleh `src/lib/paralab/f4-adapter.ts::toF4RequestFromF3()`:

```json
{
  "f3_forecast": {
    "decision": "flag_high_risk",
    "risk_band": "high",
    "confidence": "medium",
    "data_origin": "synthetic_demo",
    "f2_screening": { "derived_features": { "electrolyte_thickener_risk": "high" } },
    "limitations": ["..."]
  },
  "checkpoint": null
}
```

Fungsi `modules/f4_next_validation.py::recommend_next_validation()` membaca `decision`, `confidence`, `risk_band`, `f2_screening.derived_features.electrolyte_thickener_risk`, `evidence_ids`, dan `data_origin`. Seluruhnya tersedia. `evidence_ids` tidak dikirim website dan fungsi sudah menangani ketiadaannya dengan default list kosong.

Nilai balik berisi sembilan field dan tipe `F4Recommendation` di website mendeklarasikan sembilan field yang sama.

**Tidak ada pekerjaan implementasi.** Lihat bagian 7.2 untuk perbaikan opsional terkait `checkpoint`.

### 5.6 `POST /v1/f5/transcribe-draft` (baru, menunggu keputusan D-1)

**Pemanggil:** `src/components/paralab/VoiceLog.tsx` baris 104, tombol mikrofon mengambang pada `src/routes/doc.$id.tsx` baris 411.

**Kondisi saat ini terjadi bentrok kontrak:**

| Aspek | Website sekarang | Handoff doc |
|---|---|---|
| Transport | JSON melalui `postJson` | `multipart/form-data` |
| Isi | `{ selected_trial_id, transcript }` | `{ audio, selected_trial_id, language }` |
| Tempat STT | Browser, Web Speech API | Server, faster-whisper |

Output kedua rancangan identik, jadi yang bentrok hanya cara mengirim.

**Response (berlaku untuk kedua opsi):**

```json
{
  "trial_id": "prj-gelcream-oily-b2",
  "transcript": "pH lima koma lima, viskositas turun sedikit",
  "proposed_checkpoint_patch": {
    "measurements": { "ph": 5.5, "viscosity_cp": null },
    "observations": { "appearance": "sedikit memisah" }
  },
  "field_confidence": { "ph": 0.82 },
  "requires_confirmation": true
}
```

**Pemetaan ke kode yang sudah ada:**

Seluruh output model wajib melewati `scripts/f5_runtime.py::finalize_extraction(selected_trial_id, model_output)`. Fungsi ini menolak patch yang tidak memuat `measurements` dan `observations`, menimpa `trial_id` apa pun yang dikarang model dengan nilai dari request, dan memaksa `requires_confirmation` bernilai `true`. Website memvalidasi ulang lewat `assertConfirmable()` dan menolak draft yang tidak meminta konfirmasi.

**Aturan implementasi:**

1. `selected_trial_id` selalu berasal dari request, tidak pernah dari model. Ini sudah dipaksa `finalize_extraction()` dan tidak boleh dilewati.
2. Endpoint ini **tidak boleh menulis checkpoint atau jurnal**. Ia hanya mengusulkan. Penulisan terjadi setelah peneliti menekan konfirmasi di UI.
3. Transkrip kosong atau hanya berisi spasi ditolak dengan 422.
4. Ekstraksi Qwen dibatasi ke skema JSON. Field yang tidak disebut penutur dibiarkan `null`, jangan diisi tebakan.
5. Jangan menyimpan log permanen berisi transkrip, prompt, atau output model.

---

## 6. Keputusan yang harus diambil

### D-1: transport F5

**Opsi A, terima JSON transcript (rekomendasi).** Gateway menerima `{selected_trial_id, transcript}`, menjalankan Qwen untuk ekstraksi, lalu `finalize_extraction()`.

Keuntungan: Whisper tidak perlu dimuat sama sekali sehingga VRAM 6 GB sepenuhnya untuk Qwen, tidak ada berkas audio berpindah sehingga aturan privasi audio pada handoff doc otomatis terpenuhi, latensi berkurang, `python-multipart` dan `faster-whisper` dapat dikeluarkan dari dependency, dan website tidak perlu diubah sama sekali.

Kerugian: Web Speech API hanya tersedia di Chrome dan Edge, dan akurasi Bahasa Indonesia di bawah Whisper. Kualitas transkrip menjadi tanggung jawab browser.

**Opsi B, terima audio multipart.** Sesuai handoff doc. Akurasi lebih baik dan bekerja di semua browser, tetapi `VoiceLog.tsx` harus ditulis ulang untuk merekam audio, Whisper harus berbagi GPU dengan Qwen, dan seluruh aturan batas ukuran audio serta penghapusan berkas sementara harus dibangun.

**Rekomendasi:** ambil opsi A untuk demo, sisakan opsi B sebagai peningkatan setelah demo. Bila akurasi transkrip Bahasa Indonesia ternyata tidak memadai saat uji coba, opsi B dapat ditambahkan sebagai endpoint kedua tanpa membatalkan opsi A.

**Keputusan ini perlu persetujuan sebelum implementasi F5 dimulai.**

### D-2: satu atau dua base URL di website

Website memakai dua variabel: `VITE_MODEL_API_BASE` dengan default `http://localhost:7860` untuk F1, F2, F4, dan F5, serta `VITE_PARALAB_F3_URL` dengan default `http://127.0.0.1:8000` untuk F3.

Karena seluruh endpoint dilayani satu proses, kedua variabel harus diisi URL tunnel yang sama. Bila hanya satu yang diisi, panel F3 akan selalu menampilkan abstain dengan alasan layanan tidak dapat dihubungi, sementara panel lain berfungsi normal. Gejala ini membingungkan saat demo.

**Rekomendasi:** jangka pendek isi kedua variabel dengan nilai sama dan dokumentasikan di `.env.example` website. Jangka menengah satukan menjadi satu variabel di sisi website.

---

## 7. Temuan yang perlu diperbaiki

### 7.1 Urutan `overall_status` menutupi bahan tak dikenal

Pada `modules/f2_guardrail.py` baris 145 sampai 147, `overall_status` dihitung dengan urutan `blocked`, lalu `warning`, lalu `unknown`. Akibatnya satu bahan berstatus `unknown` dapat tertutup oleh bahan lain berstatus `warning`, sehingga `overall_status` menjadi `warning` dan `inference.py` meneruskan forecast, padahal architecture v5 menyatakan bahan tak dikenal wajib menghentikan forecast.

Website sudah memasang penjaga sisi klien untuk kasus ini di `src/lib/paralab/f3.ts` baris 326, dan menahan forecast yang menurut aturannya sendiri tidak boleh terbit. Penjaga itu benar, tetapi masalahnya ada di server.

**Tindakan:** naikkan `unknown` di atas `warning` pada perhitungan `overall_status`, atau tambahkan pemeriksaan terpisah di `inference.py` yang memicu abstain bila ada satu saja hasil berstatus `unknown`. Sertakan test regresi.

**Dampak:** memperbaiki ini mengubah perilaku F2 yang sudah dipakai `inference.py`, jadi jalankan ulang `tests/test_f2_guardrail.py` dan `tests/test_f3_inference_contract.py`.

### 7.2 Website tidak pernah mengirim `checkpoint` ke F4

`toF4RequestFromF3()` memiliki parameter `checkpoint` dengan default `null`, dan `journal.$id.tsx` memanggilnya tanpa argumen kedua. Akibatnya cabang `_missing_checkpoint_fields()` pada F4 tidak pernah aktif kecuali F3 sudah abstain lebih dulu.

Ini bukan kerusakan, melainkan kapabilitas yang tidak terpakai. F4 sebenarnya dapat menunjuk `ph`, `viscosity_cp`, atau `appearance` yang belum terisi.

**Tindakan:** di sisi website, kirim checkpoint terkonfirmasi terakhir sebagai argumen kedua. Tidak ada perubahan di sisi server.

### 7.3 Website mengirim `context` kosong ke F2

`toF2Request()` selalu mengirim `context: {}`, sedangkan `f3.ts` mengirim `{ target_skin: "oily" }`. Akibatnya rule yang bergantung konteks kulit berminyak tidak menyala pada panel F2, tetapi menyala pada jalur F3. Formula yang sama dapat menghasilkan status berbeda di dua panel pada halaman yang sama.

**Tindakan:** di sisi website, isi `context` dengan konteks proyek yang sama seperti yang dikirim `f3.ts`.

### 7.4 Handoff doc F1 sudah usang

Bentuk response F1 pada `docs/deployment/local-qwen-host-handoff.md` tidak cocok dengan yang dibaca website. Lihat catatan pada bagian 5.2.

**Tindakan:** perbarui handoff doc agar merujuk bentuk pada PRD ini.

---

## 8. Konfigurasi

Seluruh variabel di bawah sudah didefinisikan pada `deploy/model-gateway.env.example` di branch `docs/local-qwen-host-handoff` dan tetap berlaku.

| Variabel | Fungsi | Catatan |
|---|---|---|
| `PARALAB_QWEN_BASE_DIR` | Direktori Qwen2.5-1.5B-Instruct lokal | Muat dengan `local_files_only=True` |
| `PARALAB_QWEN_LORA_DIR` | Direktori LoRA ParaLab | rank 16, alpha 32, base wajib persis |
| `PARALAB_F1_EMBEDDING_MODEL_DIR` | Direktori SentenceTransformer | Dibutuhkan F1 |
| `PARALAB_F3_ARTIFACT_DIR` | Folder artefak F3 | Default `modules/f3_stability_sentinel/outputs/1` |
| `PARALAB_MODEL_CONCURRENCY` | Ukuran semaphore generasi | Mulai dari 1 |
| `PARALAB_MAX_INPUT_TOKENS` | Batas input Qwen | 2048, turunkan ke 1536 bila OOM |
| `PARALAB_MAX_NEW_TOKENS` | Batas output Qwen | 256, turunkan ke 160 bila OOM |
| `PARALAB_REQUEST_TIMEOUT_SECONDS` | Timeout permintaan | 90 |
| `PARALAB_CORS_ORIGINS` | Origin website yang diizinkan | Wajib eksplisit, tidak boleh `*` |

Sisi website:

```dotenv
VITE_MODEL_API_BASE=https://<public-gateway-url>
VITE_PARALAB_F3_URL=https://<public-gateway-url>
```

Variabel berawalan `VITE_` terbaca publik di browser. Tidak boleh memuat kredensial, token tunnel, atau path model.

---

## 9. Kebutuhan non-fungsional

1. **Konkurensi.** Satu worker uvicorn. Satu generasi Qwen aktif pada satu waktu, dikawal semaphore bersama antara F1 dan F5. F2, F3, dan F4 deterministik dan tidak boleh ikut antre di belakang generasi Qwen.
2. **Ketika penuh.** Kembalikan 429 atau timeout terstruktur, jangan biarkan OOM.
3. **Pemuatan artefak.** Seluruhnya saat startup, tidak ada unduhan saat permintaan berjalan.
4. **Validasi startup F1.** Jumlah dokumen, jumlah baris embedding, dimensi embedding, dan urutan source ID pada manifest harus cocok. Matriks embedding yang bentuknya cocok tetapi isinya usang adalah deployment tidak sah.
5. **CORS.** Header yang diizinkan tetap `Content-Type` dan `ngrok-skip-browser-warning`, sesuai implementasi sekarang di `api/app.py`.
6. **HTTPS.** Website yang dilayani HTTPS tidak dapat memanggil `http://` pada laptop. Tunnel HTTPS wajib.
7. **Error.** Kembalikan pesan terstruktur yang aman dibaca klien. Jangan kembalikan traceback.
8. **Log.** Jangan menyimpan audio, transkrip, prompt, evidence mentah, atau output model secara permanen.

---

## 10. Kriteria penerimaan

### Per endpoint

```text
[ ] GET  /health melaporkan kesiapan tiap komponen secara jujur
[ ] GET  /health tetap memuat model_version, data_origin, dan cv_status
[ ] POST /v1/f1/query mengembalikan evidence[] hasil retrieval, bukan related_cases
[ ] POST /v1/f1/query dengan evidence_status insufficient tidak memanggil Qwen dan answer bernilai null
[ ] POST /v1/f1/query menolak ringkasan yang memuat angka pengukuran lewat finalize_summary()
[ ] POST /v1/f2/health-check mengembalikan delapan kunci screen_formula apa adanya
[ ] POST /v1/f2/health-check tidak memanggil model apa pun
[ ] POST /v1/f2/health-check meneruskan ph ke derived_features.final_ph
[ ] POST /v1/f3/forecasts berjalan pada port gateway dan lulus tests/test_api_contract.py
[ ] POST /v1/f4/next-validation menerima payload dari toF4RequestFromF3 tanpa error
[ ] POST /v1/f5/transcribe-draft memakai selected_trial_id dari request, bukan dari model
[ ] POST /v1/f5/transcribe-draft selalu mengembalikan requires_confirmation true
[ ] POST /v1/f5/transcribe-draft tidak menulis jurnal atau checkpoint
```

### Tingkat sistem

```text
[ ] nvidia-smi bekerja dan torch.cuda.is_available() bernilai true
[ ] Qwen base dan LoRA dimuat dari path lokal tanpa unduhan
[ ] Embedding model, korpus F1, dan manifest lolos validasi saat startup
[ ] Layanan berjalan dengan tepat satu worker dan satu generasi aktif
[ ] URL HTTPS publik dapat dipanggil dari origin website tanpa galat CORS atau mixed content
[ ] Kedua variabel base URL website menunjuk origin yang sama
```

### Alur ujung ke ujung

```text
[ ] Peneliti membuka jurnal, menekan periksa formula, dan melihat rule F2 beserta rule_id dan versinya
[ ] Panel Sentinel menjalankan F3 dan menampilkan alert atau lanjutkan observasi, tidak pernah lolos lebih awal
[ ] Bila F3 abstain, alasannya terbaca dan menyebut data apa yang kurang
[ ] Kartu langkah validasi berikutnya terisi dari F4 dan menandai wajib review manusia
[ ] Copilot jurnal menjawab dengan ringkasan berbahasa Indonesia beserta daftar sumber dan limitasi
[ ] Pencatatan suara menghasilkan draft yang harus dikonfirmasi sebelum masuk jurnal
[ ] Mematikan gateway membuat seluruh panel menampilkan alasan kegagalan, bukan angka pengganti
```

---

## 11. Rencana pengujian

1. **Kontrak.** Perluas `tests/test_api_contract.py` untuk mencakup `/v1/f1/query`, `/v1/f2/health-check`, dan `/v1/f5/transcribe-draft` dengan loader artefak yang diinjeksi, sehingga test tidak membutuhkan GPU.
2. **Guardrail teks F1.** Uji bahwa `finalize_summary()` menolak keluaran yang memuat persentase, pH, cP, RPM, dan derajat Celsius. Fungsi ini sudah ada, testnya yang perlu diperluas ke jalur HTTP.
3. **Identitas F5.** Uji bahwa `trial_id` pada response sama dengan `selected_trial_id` pada request meskipun model mengembalikan ID lain.
4. **Regresi F2.** Setelah perbaikan 7.1, pastikan formula yang memuat satu bahan tak dikenal dan satu bahan berstatus warning menghasilkan `overall_status` bernilai `unknown` dan memicu abstain di F3.
5. **Determinisme.** F2, F3, dan F4 harus menghasilkan keluaran identik untuk input identik. Tidak boleh ada jalur yang memanggil model.
6. **Beban.** Dua permintaan F1 bersamaan harus terserialisasi, bukan menyebabkan OOM.

---

## 12. Urutan pengerjaan

| Tahap | Isi | Ketergantungan |
|---|---|---|
| 1 | Perbaikan 7.1 pada `f2_guardrail.py` beserta test regresi | Tidak ada |
| 2 | `POST /v1/f2/health-check`, deterministik dan tanpa GPU | Tahap 1 |
| 3 | Perluas `GET /health` dengan blok `components` | Tidak ada |
| 4 | Pemuatan Qwen dan embedding saat startup beserta semaphore | Host Linux siap |
| 5 | `POST /v1/f1/query` | Tahap 4 |
| 6 | Keputusan D-1, lalu `POST /v1/f5/transcribe-draft` | Tahap 4 dan persetujuan D-1 |
| 7 | Tunnel HTTPS dan penyetelan kedua base URL website | Tahap 2 sampai 6 |
| 8 | Perbaikan 7.2 dan 7.3 di sisi website | Tahap 2 |
| 9 | Perbarui handoff doc sesuai temuan 7.4 | Tahap 5 |

Tahap 1 sampai 3 tidak membutuhkan GPU dan dapat dikerjakan paralel dengan penyiapan host.

---

## 13. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| VRAM 6 GB tidak cukup saat Qwen dan Whisper hidup bersamaan | F5 atau F1 gagal saat demo | Ambil opsi A pada D-1 sehingga Whisper tidak dimuat |
| Laptop host mati atau tunnel putus | Seluruh panel model gagal | Website sudah menampilkan abstain yang menjelaskan diri, bukan angka pengganti |
| Embedding F1 usang terhadap korpus | Evidence salah tanpa gejala yang terlihat | Validasi jumlah baris, dimensi, dan urutan source ID saat startup |
| Qwen mengarang angka pengukuran di ringkasan | Klaim melampaui bukti | `finalize_summary()` menolak keluaran bernomor |
| Model mengarang `trial_id` pada F5 | Draft masuk ke jurnal yang salah | `finalize_extraction()` menimpa dengan ID dari request |
| Hanya satu base URL diisi saat demo | Panel F3 abstain terus | Tercakup pada D-2 dan kriteria penerimaan |

---

## 14. Lampiran: peta panggilan website

| Endpoint | Berkas pemanggil | Baris | Permukaan UI |
|---|---|---|---|
| `/v1/f1/query` | `src/components/paralab/DocCopilot.tsx` | 198 | Panel AI Copilot Jurnal pada halaman dokumen |
| `/v1/f2/health-check` | `src/routes/journal.$id.tsx` | 198 | Tombol periksa formula pada halaman jurnal |
| `/v1/f3/forecasts` | `src/lib/paralab/f3.ts` | 280 | Panel Sentinel pada halaman jurnal |
| `/health` | `src/lib/paralab/f3.ts` | 374 | Penanda status layanan pada Panel Sentinel |
| `/v1/f4/next-validation` | `src/routes/journal.$id.tsx` | 216 | Kartu langkah validasi berikutnya |
| `/v1/f5/transcribe-draft` | `src/components/paralab/VoiceLog.tsx` | 104 | Tombol mikrofon mengambang pada halaman dokumen |

Seluruh nomor baris merujuk branch `feat/model-integration` pada repository `paralab-website`.
