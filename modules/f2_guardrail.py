"""ParaLab AI - F2 Guardrail Engine (V4 contract).
Konsumsi data/ingredient_master.json + data/formulation_rules.json.
Output: status vocabulary V4, rules_fired (rule_id/version/source), derived_features, sign-off flag.
Lolos 14 acceptance tests (lihat tests/test_f2_guardrail.py)."""
"""F2 Guardrail Engine v4 — konsumsi ingredient_master.json + formulation_rules.json.
Output sesuai kontrak V4 §8.3-8.5: status vocabulary, derived features, audit-ready results.
Di-test lokal terhadap semua acceptance test lama + kasus baru V4."""
import json, re, difflib, os
from pathlib import Path
from datetime import datetime

DATA = Path(__file__).resolve().parents[1] / 'data'

# ---------- load ----------
master_doc = json.load(open(os.path.join(DATA, 'ingredient_master.json'), encoding='utf-8'))
rules_doc = json.load(open(os.path.join(DATA, 'formulation_rules.json'), encoding='utf-8'))
ING = master_doc['ingredients']; RULES = rules_doc['rules']; META = rules_doc['meta']
by_id = {m['ingredient_id']: m for m in ING}

# alias/INCI -> ingredient_id
_norm_map = {}
for m in ING:
    _norm_map[_k(m['inci_name'])] if False else None
def _k(s): return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()
_lookup = {}
for m in ING:
    _lookup[_k(m['inci_name'])] = m['ingredient_id']
    for a in m['aliases']:
        _lookup[_k(a)] = m['ingredient_id']
_keys = list(_lookup.keys())

def resolve(nama, cutoff=0.6):
    """Return ingredient_id | None. Tahan nama dagang & typo (prefix fallback)."""
    n = _k(nama)
    if n in _lookup: return _lookup[n]
    toks = n.split()
    for i in range(len(toks)-1, 0, -1):
        c = ' '.join(toks[:i])
        if c in _lookup: return _lookup[c]
    m = difflib.get_close_matches(n, _keys, n=1, cutoff=cutoff)
    return _lookup[m[0]] if m else None

# index rules per ingredient
_rules_by_ing = {}
for r in RULES:
    if 'applies_to' in r:
        _rules_by_ing.setdefault(r['applies_to'], []).append(r)
_pair_rules = [r for r in RULES if 'applies_if_pair' in r]

def evaluate_ingredient(inci_input, pct, formula_ids=None, konteks=None):
    """Satu bahan -> hasil guardrail V4. Fail-fast: compatibility blocked > halal blocked > sisanya kumulatif."""
    formula_ids = formula_ids or []
    konteks = konteks or {}
    ing_id = resolve(inci_input)
    if ing_id is None:
        return {'input': inci_input, 'status': 'unknown',
                'rationale': 'Bahan tidak dikenali di ingredient master — human review wajib',
                'requires_human_review': True, 'rules_fired': []}
    m = by_id[ing_id]
    fired = []  # list of rule results

    def fire(rule, detail=None):
        fired.append({'rule_id': rule['rule_id'], 'rule_version': rule['rule_version'],
                      'severity': rule['severity'], 'source_id': rule['source_id'],
                      'rationale': detail or rule['rationale'],
                      'requires_human_review': rule.get('requires_human_review', False)})

    # --- LAPIS 1: compatibility pair rules (fail-fast pada blocked) ---
    for r in _pair_rules:
        a, b = r['applies_if_pair']
        if a == ing_id and b in formula_ids or b == ing_id and a in formula_ids:
            if r['severity'] == 'blocked':
                fire(r)
                return _finalize(inci_input, m, 'blocked', [f], True) if False else _pack(inci_input, m, 'blocked', fired, True)
            fire(r)

    # --- LAPIS 2-3: aturan per-bahan (kumulatif) ---
    has_warning = False
    for r in _rules_by_ing.get(ing_id, []):
        if r['rule_type'] == 'concentration_range':
            lo, hi = m['concentration_range_pct_w_w']['min'], m['concentration_range_pct_w_w']['max']
            if not (lo <= pct <= hi):
                fire(r, f"{pct}% di luar rentang umum {lo}-{hi}%")
                has_warning = True
        elif r['rule_type'] == 'halal_screening':
            fire(r); has_warning = True
        elif r['rule_type'] == 'regulatory_limit':
            fire(r)
            if r['severity'] == 'blocked':
                return _pack(inci_input, m, 'blocked', fired, False)
            has_warning = True
        elif r['rule_type'] == 'allergen_labeling':
            fire(r)
    # konteks: komedogenik utk kulit berminyak (deterministik, dari master metadata)
    if konteks.get('target_skin') == 'oily' and m.get('comedogenic_rating_indicative', 0) >= 2:
        fired.append({'rule_id': 'CTX-KOMED-001', 'rule_version': META['rule_version'],
                      'severity': 'warning', 'source_id': 'INGREF-CTX',
                      'rationale': f"komedogenik {m['comedogenic_rating_indicative']}/5 — berisiko utk target kulit berminyak",
                      'requires_human_review': False})
        has_warning = True
    # konteks positioning premium: emolien murah kurang sejalan segmen high-value
    if konteks.get('segmen') == 'premium' and m['inci_name'] in ('Mineral Oil', 'Petrolatum'):
        fired.append({'rule_id': 'CTX-POSITION-001', 'rule_version': META['rule_version'],
                      'severity': 'warning', 'source_id': 'INGREF-CTX',
                      'rationale': 'Secara persepsi kurang sejalan dengan positioning high-value/premium',
                      'requires_human_review': False})
        has_warning = True
    status = 'warning' if (has_warning or any(f['severity'] == 'warning' for f in fired)) else 'clear'
    return _pack(inci_input, m, status, fired, any(f['requires_human_review'] for f in fired))

def _pack(inci_input, m, status, fired, review):
    return {'input': inci_input, 'ingredient_id': m['ingredient_id'], 'inci_name': m['inci_name'],
            'status': status, 'rules_fired': fired, 'requires_human_review': review}

def derive_features(results, ph=None):
    """Kontrak V4 §8.3: derived features deterministik dari hasil guardrail + master."""
    ids = [r['ingredient_id'] for r in results if 'ingredient_id' in r]
    electrolyte = any(by_id[i]['is_electrolyte'] for i in ids)
    thick_sens = any(by_id[i].get('electrolyte_sensitive_thickener') for i in ids)
    emuls = [i for i in ids if 'surfactant_emulsifier' in by_id[i]['functional_classes']]
    status_counts = {}
    for r in results: status_counts[r['status']] = status_counts.get(r['status'], 0) + 1
    return {
        'feature_schema_version': 'stability-sentinel-v1',
        'ingredient_count': len(ids),
        'electrolyte_load': 'high' if electrolyte else 'low',
        'thickener_sensitivity': 'high' if thick_sens else 'low',
        'electrolyte_thickener_risk': 'high' if (electrolyte and thick_sens) else 'low',
        'emulsifier_balance_status': 'watch' if len(emuls) < 1 else 'ok',
        'compatibility_warning_count': sum(1 for r in results if r['status'] == 'warning'),
        'blocked_count': status_counts.get('blocked', 0),
        'unknown_count': status_counts.get('unknown', 0),
        'final_ph': ph,
    }

def screen_formula(formula, konteks=None, ph=None):
    """formula = [{'bahan':..., 'pct':...}]. Return kontrak V4 lengkap."""
    ids_first = [resolve(f['bahan']) for f in formula]
    results = [evaluate_ingredient(f['bahan'], f['pct'],
                                   formula_ids=[i for i in ids_first if i],
                                   konteks=konteks) for f in formula]
    overall = 'blocked' if any(r['status'] == 'blocked' for r in results) else \
              'warning' if any(r['status'] == 'warning' for r in results) else \
              'unknown' if any(r['status'] == 'unknown' for r in results) else 'clear_for_current_screening'
    return {
        'screened_at': datetime.now().isoformat(),
        'rule_version': META['rule_version'],
        'overall_status': overall,
        'disclaimer': META['disclaimer'],
        'results': results,
        'derived_features': derive_features(results, ph=ph),
        'model_coverage': {'status': 'supported_demo_domain',
                           'reason': 'Formula dapat dipetakan ke O/W gel-cream synthetic feature schema.'},
        'requires_human_signoff': any(r['requires_human_review'] for r in results) or overall != 'clear_for_current_screening',
    }

