# Modul inti

Folder ini berisi capability yang dapat diimpor dan dijalankan sebagai bagian inti ParaLab.

## Isi folder

| Path | Fungsi |
|---|---|
| `f2_guardrail.py` | Normalisasi bahan, eksekusi rule deterministik, dan derived feature untuk F3 |
| `f3_stability_sentinel/train_stability_sentinel.py` | Training dan evaluasi baseline tabular F3 |
| `f3_stability_sentinel/landmark_sweep.py` | Membandingkan informasi pada minggu 1, 2, 4, 6, dan 8 |
| `f3_stability_sentinel/weight_sensitivity.py` | Menguji sensitivitas terhadap asumsi hazard sintetis |
| `f3_stability_sentinel/outputs/1/` | Model dan laporan reproducible dari run baseline |

## F2 Guardrail

F2 memerlukan `data/ingredient_master.json` dan `data/formulation_rules.json`.

```python
from modules.f2_guardrail import screen_formula

result = screen_formula(
    [{"bahan": "Niacinamide", "pct": 5.0}],
    konteks={"target_skin": "oily"},
    ph=5.7,
)
```

Output F2 bukan approval regulasi atau keselamatan. Status `clear_for_current_screening` hanya berarti tidak ada rule prototipe yang aktif.

## F3 Stability Sentinel

Instal dependency:

```bash
uv pip install --python .venv-f3/bin/python -r requirements/f3_stability_sentinel.txt
```

Jalankan:

```bash
.venv-f3/bin/python modules/f3_stability_sentinel/train_stability_sentinel.py
.venv-f3/bin/python modules/f3_stability_sentinel/landmark_sweep.py
.venv-f3/bin/python modules/f3_stability_sentinel/weight_sensitivity.py
```

F3 dilatih dan diuji hanya pada synthetic-demo. Keluaran rendah risiko tetap berarti `continue_observation`, bukan early pass.
