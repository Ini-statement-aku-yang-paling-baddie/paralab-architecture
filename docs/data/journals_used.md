# Jurnal dan sumber ilmiah yang dipakai ParaLab

Dokumen ini adalah indeks tunggal untuk sumber eksternal yang **benar-benar dipakai oleh implementasi atau dokumentasi aktif ParaLab**. Ia tidak memasukkan tautan eksplorasi mentah di `docs/archive/research_notes.md`, synthetic corpus, atau referensi yang belum di-ingest/diverifikasi.

> [!IMPORTANT]
> Sumber di bawah tidak memvalidasi ParaLab sebagai sistem produksi. Dataset F3 dan CV tetap `synthetic_demo`. Sumber publik dipakai hanya dalam peran yang ditulis pada setiap entri.

## Jurnal ilmiah

| ID | Sitasi | Peran di ParaLab | Status penggunaan |
|---|---|---|---|
| J-01 | Simões, A., Veiga, F., & Vitorino, C. (2020). *Progressing Towards the Sustainable Development of Cream Formulations*. **Pharmaceutics, 12**(7), 647. https://doi.org/10.3390/pharmaceutics12070647 | Satu-satunya paper yang sudah di-ingest sebagai `observed_public`. Table 2 dan Table 5 membentuk 15 evidence document F1 serta konteks F2. | CC BY 4.0. Bukan formula kosmetik lengkap atau label F3: domainnya cream hidrokortison farmasi, data tabel bersifat snapshot/proxy. |
| J-02 | Cannell, J. S. (1985). *Fundamentals of stability testing*. **International Journal of Cosmetic Science, 7**(6), 291-303. https://doi.org/10.1111/j.1467-2494.1985.tb00423.x | Landasan historis asumsi Q10 dan stability testing yang dibahas pada kajian F3. | Dipakai sebagai rujukan sekunder melalui Postles (2018); bukan sumber data training atau evaluasi F3. |
| J-03 | Chitre, A., Querimit, R. C. M., Rihm, S. D., Karan, D., Zhu, B., Wang, K., Wang, L., Hippalgaonkar, K., & Lapkin, A. A. (2024). *Accelerating Formulation Design via Machine Learning: Generating a High-throughput Shampoo Formulations Dataset*. **Scientific Data, 11**, 728. https://doi.org/10.1038/s41597-024-03573-w | Artikel pendamping dataset shampoo Figshare yang disimpan pada `data/open_sources/figshare_shampoo/`. | CC BY 4.0 untuk artikel. Dataset dipertahankan sebagai proxy rinse-off shampoo, tidak digabungkan ke supervised F3 moisturizer. |

## Sumber non-jurnal yang tetap dipakai

| ID | Sitasi | Peran di ParaLab | Batas penggunaan |
|---|---|---|---|
| N-01 | Postles, A. (2018). *Factors affecting the measurement of stability and safety of cosmetic products*. PhD thesis, Bournemouth University. [Repository record](https://eprints.bournemouth.ac.uk/32141/) · [PDF](https://eprints.bournemouth.ac.uk/32141/1/POSTLES,%20Andrew_Ph.D._2018.pdf) | Sumber utama kajian F3 mengenai protokol accelerated/real-time, reliabilitas parameter, dan risiko false pass. | Tesis, bukan jurnal. Tidak menjadi data training F3. |
| N-02 | ISO/TR 18811:2018. *Cosmetics — Guidelines on the stability testing of cosmetic products*. https://www.iso.org/standard/63465.html | Konteks standar untuk batas klaim F3 dan larangan memperlakukan alert sebagai pengganti uji stabilitas formal. | Standar teknis, bukan jurnal dan bukan aturan F2 yang dapat dianggap approval regulasi. |
| N-03 | Cosmetics Europe / Colipa (2004). *Guidelines on Stability Testing of Cosmetic Products*. | Referensi historis yang dikutip Postles untuk konteks praktik stability testing. | Dicatat sebagai rujukan sekunder melalui Postles; metadata/tautan primer belum di-ingest. |
| N-04 | Personal Care Products Council (2011). *Guidelines for Industry — The Stability Testing of Cosmetics*. | Referensi historis yang dikutip Postles untuk konteks praktik stability testing. | Dicatat sebagai rujukan sekunder melalui Postles; metadata/tautan primer belum di-ingest. |

## Dataset publik terkait

| Dataset | DOI / tautan | Kaitan dengan jurnal | Peran dan batas |
|---|---|---|---|
| Figshare shampoo formulation dataset | Collection: https://doi.org/10.6084/m9.figshare.c.7132624 · Article: https://doi.org/10.6084/m9.figshare.25451878.v1 | Data pendukung J-03 | Lisensi CC0. Berisi 812 record shampoo rinse-off dengan horizon sekitar 36 jam. Tidak boleh dipakai sebagai label longitudinal F3 moisturizer. |

## Jejak penggunaan di repository

- J-01: `sources/public/PMC7407566_tables_2_5.json`, `data/public_observed/`, dan `docs/data/public_evidence_pipeline.md`.
- J-02 serta N-01 sampai N-04: `docs/reports/f3_early_detection_study.md` bagian Referensi.
- J-03 dan dataset Figshare: `data/open_sources/figshare_shampoo/` dan `docs/data/public_evidence_pipeline.md`.

## Cara menambah sumber baru

Tambahkan source hanya bila seluruh syarat ini tersedia: URL/DOI yang dapat diakses, lisensi penggunaan ulang, tanggal akses, lokasi tabel/section, provenance ekstraksi, serta batas domain yang jelas. Sumber cross-sectional atau lintas product family tetap tidak boleh dipromosikan sebagai data longitudinal F3 tanpa kontrak trajectory dan outcome yang memenuhi syarat.
