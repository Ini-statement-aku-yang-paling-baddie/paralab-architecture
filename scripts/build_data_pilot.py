#!/usr/bin/env python3
"""Pilot integrasi sintetis, bukan resep atau validasi ilmiah. Hanya stdlib."""
import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import random
import shutil

VERSION = 'pilot-v1'
WEEKS = [0, 1, 2, 4, 6, 8, 12]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_source(path):
    entries = json.loads(Path(path).read_text())['entri']
    names = sorted({i['bahan'] for e in entries for i in e['formula']})
    totals = [{'source_id': e['id'], 'total_pct': round(sum(i['pct'] for i in e['formula']), 6)} for e in entries]
    audit = {'entries': len(entries), 'unique_ids': len({e['id'] for e in entries}),
             'trials': sum(len(e['trial']) for e in entries),
             'moisturizer': sum(e['kategori_produk'] == 'moisturizer' for e in entries),
             'partial_formulas': sum(not math.isclose(t['total_pct'], 100) for t in totals),
             'ingredient_alias_count': len(names), 'formula_totals': totals,
             'generator_counts': dict(Counter(e.get('generator', 'unknown') for e in entries)),
             'source_sha256': sha(path),
             'warnings': ['Corpus template sintetis; bukan evidence ilmiah.',
                          'Formula parsial tidak dilengkapi atau dianggap resep.',
                          'Alias, fungsi, narasi, hasil trial belum diverifikasi; bukan trajectory longitudinal.']}
    aliases = [{'id': f'ALIAS-{n:03}', 'name': name, 'aliases': [name],
                'verification': 'unverified_alias', 'human_verified': False,
                'provenance': {'source': 'raw/corpus_formulab.json', 'sha256': sha(path),
                               'source_ids': [e['id'] for e in entries if any(i['bahan'] == name for i in e['formula'])]}}
               for n, name in enumerate(names, 1)]
    return audit, aliases


TABLES = ['projects', 'formulas', 'trials', 'observation_series', 'checkpoints', 'outcomes']
ASSUMPTIONS = {
    'id': 'SIM-001', 'version': VERSION, 'data_origin': 'synthetic_demo',
    'scientific_validation_status': 'not_validated_for_production',
    'human_verified': False, 'source_ids': [],
    'description': 'Skenario matematis buatan, bukan aturan kimia atau evidence publik.',
    'weeks': WEEKS, 'temperatures_c': [25, 40],
    'scenarios': ['pass', 'late_failure', 'early_failure', 'right_censored', 'uncertain', 'missing_invalid'],
    'measurement_ranges': {'ph': [0, 14], 'viscosity_cp': [0, 1000000]},
    'range_note': 'Batas sanity input perangkat lunak; bukan spesifikasi stabilitas kosmetik.',
    'formula_note': 'Komponen demo termasuk placeholder emulsifier/preservative; tidak layak diracik.',
    'trajectory_note': 'Baseline acak seeded; drift kecil. Nilai terminal failure adalah injeksi skenario, tanpa kausalitas bahan.'
}


def entity(identifier, seed, **fields):
    return {'id': identifier, 'data_origin': 'synthetic_demo', 'human_verified': False,
            'scientific_validation_status': 'not_validated_for_production',
            'provenance': {'generator': VERSION, 'seed': seed, 'assumption_id': 'SIM-001'}, **fields}


def note(c):
    parts = []
    for key, unit in [('ph', ''), ('viscosity_cp', ' cP')]:
        q = c['quality'][key]
        value = c['measurements'][key]
        parts.append(f'{key} {value}{unit}' if q == 'observed' else f'{key} {q} (raw={c["raw_measurements"][key]})')
    return f'SIMULASI belum direview. Minggu {c["week"]}; ' + '; '.join(parts) + f'; tampilan {c["appearance"]}.'


def generate(seed=17):
    rng = random.Random(seed)
    d = {name: [] for name in TABLES}
    # Enam keluarga formula, masing-masing dua proyek; split SEBELUM turunan.
    for p in range(12):
        family = p // 2
        split = 'train' if family < 4 else ('validation' if family == 4 else 'test')
        pid = f'P-{p+1:03}'
        common = {'project_id': pid, 'split': split}
        d['projects'].append(entity(pid, seed, family_id=f'FAMILY-{family+1:02}',
                                    split=split, product_family='o_w_gel_cream_moisturizer', target_skin='oily'))
        for t in range(2):
            tid = f'{pid}-T{t+1}'
            fid = f'{pid}-FORM{t+1}'
            glycerin = 3 + family * 0.2 + t * 0.1
            ingredients = [{'ingredient_id': name, 'pct': pct} for name, pct in [
                ('DEMO:WATER', round(100 - glycerin - 12, 6)), ('DEMO:GLYCERIN', glycerin),
                ('DEMO:SQUALANE', 5), ('DEMO:NIACINAMIDE', 3),
                ('DEMO:EMULSIFIER_UNSPECIFIED', 3), ('DEMO:PRESERVATIVE_UNSPECIFIED', 1)]]
            d['formulas'].append(entity(fid, seed, **common, ingredients=ingredients,
                review_status='unreviewed_not_lab_recipe', created_at='2026-01-01',
                process={'mixing_time_min': 15 + t, 'homogenization_rpm': 2400 + 100*t, 'heating_temp_c': 70},
                disclaimer='Formula lengkap secara aritmetika saja; placeholder bukan resep laboratorium.'))
            d['trials'].append(entity(tid, seed, **common, formula_id=fid, started_at='2026-01-01'))
            for temp in [25, 40]:
                sid = f'{tid}-S{temp}'
                # Jadwal eksplisit menjamin contoh horizon dikenal di setiap split kecil.
                scenario_base = [0, 1, 2, 3, 4, 5, 0, 1, 0, 3, 4, 5][p]
                scenario = (scenario_base + t + (temp == 40)) % 6
                status, last, failure = [('passed', 12, None), ('failed', 8, 8),
                    ('failed', 2, 2), ('right_censored', 6, None),
                    ('uncertain', 12, None), ('passed', 12, None)][scenario]
                d['observation_series'].append(entity(sid, seed, **common, trial_id=tid,
                    temperature_c=temp, humidity_pct=None))
                ph0 = rng.uniform(5.3, 5.9)
                vis0 = rng.randint(12000, 18000)
                for week in WEEKS:
                    if week > last:
                        continue
                    measures = {'ph': round(ph0 + week*.012 + rng.uniform(-.05, .05), 2),
                                'viscosity_cp': round(vis0 - week*80 + rng.uniform(-200, 200))}
                    appearance = 'uncertain' if scenario == 4 and week >= 6 else 'uniform'
                    if week == failure:
                        measures['viscosity_cp'] = round(vis0*.3)
                        appearance = 'separated'
                    raw = dict(measures)
                    quality = dict.fromkeys(measures, 'observed')
                    if scenario == 5 and week == 2:
                        measures['viscosity_cp'] = raw['viscosity_cp'] = None
                        quality['viscosity_cp'] = 'missing'
                    if scenario == 5 and week == 4:
                        raw['ph'], measures['ph'], quality['ph'] = '99.0', None, 'invalid'
                    c = entity(f'{sid}-W{week:02}', seed, **common, series_id=sid, week=week,
                        observed_at=(date(2026, 1, 1) + timedelta(weeks=week)).isoformat(),
                        measurements=measures, raw_measurements=raw, quality=quality,
                        missing_reasons={k: ('not_recorded' if v == 'missing' else 'out_of_range')
                                         for k, v in quality.items() if v != 'observed'},
                        appearance=appearance)
                    c['note'] = note(c)
                    d['checkpoints'].append(c)
                d['outcomes'].append(entity(f'{sid}-OUT', seed, **common, series_id=sid,
                    status=status, last_week=last, failure_week=failure,
                    endpoint_checkpoint_id=f'{sid}-W{last:02}',
                    stopped=status == 'failed', horizon_week=12,
                    censor_reason='administrative_demo_cutoff' if status == 'right_censored' else None))
    return d


def finite(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate(d):
    """Validasi relasional dan semantik; kembalikan daftar kesalahan, bukan memperbaiki data."""
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    try:
        maps = {}
        seen = set()
        seeds = set()
        schema = contract()
        require(set(d) == set(TABLES), 'Tabel kanonis tidak cocok')
        require(len(d['projects']) == 12 and len(d['trials']) == 24, 'Ukuran pilot wajib 12 project / 24 trial')
        for table in TABLES:
            require(isinstance(d[table], list), f'{table}: bukan array')
            maps[table] = {}
            for r in d[table]:
                require(set(schema['common_required']) | set(schema['tables'][table]['required']) <= set(r), f'{table}: field wajib hilang')
                rid = r['id']
                require(isinstance(rid, str) and bool(rid) and rid not in seen, f'{table}: ID kosong/duplikat {rid}')
                seen.add(rid)
                maps[table][rid] = r
                require(r['human_verified'] is False and r['data_origin'] == 'synthetic_demo' and
                        r['scientific_validation_status'] == 'not_validated_for_production', f'{rid}: status provenance')
                prov = r['provenance']
                seeds.add(prov.get('seed'))
                require(prov.get('generator') == VERSION and type(prov.get('seed')) is int and
                        prov.get('assumption_id') == 'SIM-001', f'{rid}: provenance hilang')
                require(r['split'] in ['train', 'validation', 'test'], f'{rid}: split ilegal')
        require(len(seeds) == 1, 'Provenance seed tidak konsisten')
        families = {}
        for p in d['projects']:
            require(p['product_family'] == 'o_w_gel_cream_moisturizer', f'{p["id"]}: domain')
            require(families.setdefault(p['family_id'], p['split']) == p['split'], 'family: leakage split')
        for table in TABLES[1:]:
            for r in d[table]:
                p = maps['projects'].get(r['project_id'])
                require(p is not None and p['split'] == r['split'], f'{r["id"]}: project/split')
        def join(row, key, table):
            parent = maps[table].get(row[key])
            require(parent is not None and parent.get('project_id') == row['project_id'], f'{row["id"]}: join {key}')
            return parent
        for f in d['formulas']:
            items = f['ingredients']
            require(all(i['ingredient_id'] in DEMO_COMPONENTS and set(i) == {'ingredient_id', 'pct'} for i in items), f'{f["id"]}: join komponen')
            require(set(f['process']) == {'mixing_time_min', 'homogenization_rpm', 'heating_temp_c'}, f'{f["id"]}: field proses di luar kontrak')
            require(bool(items) and all(finite(i['pct'], 0, 100) for i in items), f'{f["id"]}: konsentrasi')
            require(math.isclose(sum(i['pct'] for i in items), 100, abs_tol=1e-6), f'{f["id"]}: total bukan 100')
            require(len({i['ingredient_id'] for i in items}) == len(items), f'{f["id"]}: bahan duplikat')
            require(f['review_status'] == 'unreviewed_not_lab_recipe', f'{f["id"]}: review formula')
            date.fromisoformat(f['created_at'])
            for k, lo, hi in [('mixing_time_min', 0, 1000), ('homogenization_rpm', 0, 100000), ('heating_temp_c', 0, 150)]:
                require(finite(f['process'][k], lo, hi), f'{f["id"]}: proses {k}')
        for t in d['trials']:
            f = join(t, 'formula_id', 'formulas')
            date.fromisoformat(t['started_at'])
            require(f is None or f['created_at'] <= t['started_at'], f'{t["id"]}: tanggal formula')
            series = [s for s in d['observation_series'] if s['trial_id'] == t['id']]
            require(len(series) == 2 and {s['temperature_c'] for s in series} == {25, 40}, f'{t["id"]}: storage group')
        for s in d['observation_series']:
            t = join(s, 'trial_id', 'trials')
            cs = [c for c in d['checkpoints'] if c['series_id'] == s['id']]
            os = [o for o in d['outcomes'] if o['series_id'] == s['id']]
            require(len(os) == 1, f'{s["id"]}: satu outcome wajib')
            if len(os) != 1:
                continue
            o = os[0]
            require(o['last_week'] in WEEKS, f'{s["id"]}: last week')
            require([c['week'] for c in cs] == [w for w in WEEKS if w <= o['last_week']], f'{s["id"]}: jadwal/stop/order')
            require(bool(cs) and cs[-1]['id'] == o['endpoint_checkpoint_id'], f'{s["id"]}: endpoint')
            require(o['horizon_week'] == 12 and o['status'] in ['passed', 'failed', 'right_censored', 'uncertain'], f'{s["id"]}: status')
            if o['status'] == 'failed':
                require(o['stopped'] is True and o['failure_week'] == o['last_week'] and cs[-1]['appearance'] == 'separated', f'{s["id"]}: failure')
            else:
                require(o['stopped'] is False and o['failure_week'] is None, f'{s["id"]}: nonfailure')
                if o['status'] == 'right_censored':
                    require(o['last_week'] < 12 and bool(o['censor_reason']), f'{s["id"]}: censor')
                else:
                    require(o['last_week'] == 12 and o['censor_reason'] is None, f'{s["id"]}: horizon incomplete')
                if o['status'] == 'passed':
                    require(all(c['appearance'] == 'uniform' for c in cs), f'{s["id"]}: pass contradiction')
                if o['status'] == 'uncertain':
                    require(cs[-1]['appearance'] == 'uncertain', f'{s["id"]}: uncertain contradiction')
            for c in cs:
                if t:
                    require(date.fromisoformat(c['observed_at']) == date.fromisoformat(t['started_at']) + timedelta(weeks=c['week']), f'{c["id"]}: tanggal')
        for o in d['outcomes']:
            join(o, 'series_id', 'observation_series')
        for c in d['checkpoints']:
            join(c, 'series_id', 'observation_series')
            require(c['appearance'] in ['uniform', 'uncertain', 'separated'], f'{c["id"]}: appearance')
            for payload in ['measurements', 'quality', 'raw_measurements']:
                require(set(c[payload]) == set(ASSUMPTIONS['measurement_ranges']), f'{c["id"]}: field {payload} di luar kontrak')
            require(set(c['missing_reasons']) <= set(ASSUMPTIONS['measurement_ranges']), f'{c["id"]}: missing reason di luar kontrak')
            for k, (lo, hi) in ASSUMPTIONS['measurement_ranges'].items():
                v, q, raw = c['measurements'][k], c['quality'][k], c['raw_measurements'][k]
                require(q in ['observed', 'missing', 'invalid'], f'{c["id"]}: quality')
                if q == 'observed':
                    require(finite(v, lo, hi) and raw == v and k not in c['missing_reasons'], f'{c["id"]}: nilai/range/raw')
                else:
                    require(v is None and bool(c['missing_reasons'].get(k)), f'{c["id"]}: missing policy')
                    if q == 'invalid':
                        try:
                            require(not finite(float(raw), lo, hi), f'{c["id"]}: raw valid disalahlabel invalid')
                        except (TypeError, ValueError):
                            pass
                    require((q == 'missing' and raw is None) or (q == 'invalid' and isinstance(raw, str) and bool(raw)), f'{c["id"]}: raw invalid/missing')
            require(c['note'] == note(c), f'{c["id"]}: narasi tidak sesuai checkpoint')
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        errors.append(f'Schema tidak valid: {exc}')
    return errors


DERIVED = ['journal_documents', 'f1_train_corpus', 'forecast_features', 'forecast_labels',
           'forecast_censored', 'forecast_excluded', 'f5_examples', 'image_manifest']


def derive(d):
    r = {name: [] for name in DERIVED}
    trials = {t['id']: t for t in d['trials']}
    formulas = {f['id']: f for f in d['formulas']}
    outcomes = {o['series_id']: o for o in d['outcomes']}
    for s in d['observation_series']:
        sid = s['id']
        seed = s['provenance']['seed']
        common = {'project_id': s['project_id'], 'series_id': sid, 'split': s['split']}
        cs = [c for c in d['checkpoints'] if c['series_id'] == sid]
        o = outcomes[sid]
        f = formulas[trials[s['trial_id']]['formula_id']]
        doc = entity(f'DOC-{sid}', seed, **common, formula_id=f['id'],
                     checkpoint_ids=[c['id'] for c in cs], outcome_id=o['id'],
                     document_scope='historical_full_trajectory_not_forecast_input',
                     text='\n'.join([f'SIMULASI O/W; {sid}; split={s["split"]}; storage={s["temperature_c"]} C.'] +
                                    [c['note'] for c in cs] + [f'Outcome skenario: {o["status"]}; terakhir minggu {o["last_week"]}. Bukan hasil lab.']))
        r['journal_documents'].append(doc)
        if s['split'] == 'train':
            r['f1_train_corpus'].append(doc.copy())
        early = [c for c in cs if c['week'] <= 4]
        feature = entity(f'FEAT-{sid}', seed, **common, feature_schema_version='landmark4-v1',
                         landmark_week=4, horizon_week=12, formula_id=f['id'],
                         checkpoint_ids=[c['id'] for c in early], temperature_c=s['temperature_c'],
                         formula_concentrations=f['ingredients'], process=f['process'],
                         observations=[{'week': c['week'], 'measurements': c['measurements'],
                                        'quality': c['quality'], 'appearance': c['appearance']} for c in early])
        reasons = []
        if o['failure_week'] is not None and o['failure_week'] <= 4:
            reasons.append('not_at_risk_at_landmark')
        if o['status'] == 'uncertain':
            reasons.append('uncertain_outcome')
        if [c['week'] for c in early] != [0, 1, 2, 4] or any(q != 'observed' for c in early for q in c['quality'].values()):
            reasons.append('insufficient_observation_no_imputation')
        if o['status'] == 'right_censored':
            r['forecast_censored'].append(entity(f'CENS-{sid}', seed, **common,
                outcome_id=o['id'], last_observed_week=o['last_week'], feature_snapshot=feature,
                reasons=['right_censored_no_binary_label'] + reasons))
        elif reasons:
            r['forecast_excluded'].append(entity(f'EXCL-{sid}', seed, **common, outcome_id=o['id'], reasons=reasons))
        else:
            r['forecast_features'].append(feature)
            r['forecast_labels'].append(entity(f'LABEL-{sid}', seed, **common, feature_id=feature['id'],
                outcome_id=o['id'], failed_by_12=int(o['status'] == 'failed'),
                label_basis='scenario_not_human_verified', horizon_week=12))
        for c in cs:
            r['f5_examples'].append(entity(f'VOICE-{c["id"]}', seed, **common, checkpoint_id=c['id'],
                transcript=c['note'], transcript_origin='deterministic_text_not_recorded_audio',
                requires_confirmation=True, target={'measurements': c['measurements'], 'quality': c['quality'],
                'raw_measurements': c['raw_measurements'], 'missing_reasons': c['missing_reasons'],
                'appearance': c['appearance'], 'week': c['week'], 'observed_at': c['observed_at']}))
    return r


def validate_derived(d, r):
    errors = validate(d)
    if errors:
        return errors
    expected = derive(d)
    # Turunan adalah view deterministik; exact replay juga menolak field bocor/tambahan.
    for table in DERIVED:
        if r.get(table) != expected[table]:
            errors.append(f'{table}: tidak konsisten dengan view kanonis / leakage')
    if set(r) != set(DERIVED):
        errors.append('Tabel turunan tidak dikenal')
    return errors


ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ['corpus_formulab.json', 'embeddings_formulab.npy']
DEMO_COMPONENTS = {'DEMO:WATER': 'Air demo', 'DEMO:GLYCERIN': 'Glycerin',
                   'DEMO:SQUALANE': 'Squalane', 'DEMO:NIACINAMIDE': 'Niacinamide',
                   'DEMO:EMULSIFIER_UNSPECIFIED': 'Placeholder emulsifier',
                   'DEMO:PRESERVATIVE_UNSPECIFIED': 'Placeholder preservative'}


def dump(path, obj, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    def encode(x):
        return json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=None if lines else 2)
    path.write_text((''.join(encode(row) + '\n' for row in obj) if lines else encode(obj) + '\n'), encoding='utf-8')


def contract():
    return {'contract_version': VERSION, 'format': 'JSONL, satu objek per baris; UTF-8',
        'common_required': {'id': 'string unik global', 'split': 'train|validation|test',
            'data_origin': 'synthetic_demo', 'human_verified': False,
            'scientific_validation_status': 'not_validated_for_production',
            'provenance': {'generator': VERSION, 'seed': 'integer', 'assumption_id': 'SIM-001'}},
        'tables': {
            'projects': {'required': ['family_id', 'product_family', 'target_skin']},
            'formulas': {'required': ['project_id', 'ingredients', 'process', 'created_at', 'review_status'],
                         'foreign_keys': {'project_id': 'projects.id', 'ingredients[].ingredient_id': 'demo_components.id'},
                         'ingredients': {'ingredient_id': 'string', 'pct': 'finite number [0,100]; total 100±1e-6'}},
            'trials': {'required': ['project_id', 'formula_id', 'started_at'], 'foreign_keys': {'formula_id': 'formulas.id'}},
            'observation_series': {'required': ['project_id', 'trial_id', 'temperature_c', 'humidity_pct'],
                                   'foreign_keys': {'trial_id': 'trials.id'}, 'temperature_c': [25, 40]},
            'checkpoints': {'required': ['project_id', 'series_id', 'week', 'observed_at', 'measurements',
                'raw_measurements', 'quality', 'missing_reasons', 'appearance', 'note'],
                'foreign_keys': {'series_id': 'observation_series.id'}, 'weeks': WEEKS,
                'measurements': {'ph': 'number [0,14] | null', 'viscosity_cp': 'number [0,1000000] | null'},
                'quality': ['observed', 'missing', 'invalid']},
            'outcomes': {'required': ['project_id', 'series_id', 'status', 'last_week', 'failure_week',
                'endpoint_checkpoint_id', 'stopped', 'horizon_week', 'censor_reason'],
                'foreign_keys': {'series_id': 'observation_series.id', 'endpoint_checkpoint_id': 'checkpoints.id'},
                'status': ['passed', 'failed', 'right_censored', 'uncertain']}},
        'derived_tables': DERIVED,
        'forecast_contract': {'feature_file': 'derived/forecast_features.jsonl', 'label_file': 'derived/forecast_labels.jsonl',
            'join': 'features.id = labels.feature_id', 'landmark_week': 4, 'horizon_week': 12,
            'feature_columns': ['temperature_c', 'formula_concentrations', 'process', 'observations'],
            'metadata_not_model_features': ['id', 'project_id', 'series_id', 'formula_id', 'split', 'provenance', 'checkpoint_ids'],
            'exclusions': ['failure_week<=4', 'right_censored', 'uncertain', 'missing/invalid measurement through week4'],
            'target': 'failed_by_12: 0|1; known terminal event after week4 counts even if stopped before week12'},
        'invariants': ['family/project/trial/storage/checkpoint tetap satu split',
            'tanggal ISO sesuai started_at + week*7 hari; jadwal berurutan tanpa data sesudah stop',
            'observed: finite dan raw sama; missing: null/null; invalid: null/raw string; alasan wajib',
            'catatan tepat dari checkpoint yang sama; turunan direplay untuk validasi',
            'bukan JSON Schema resmi: kontrak semantik dijalankan validate CLI'],
        'validator_command': 'python3 scripts/build_data_pilot.py validate'}


def metrics(d, r):
    return {'evaluation_scope': 'synthetic-demo structural validation only; bukan metrik model',
            'canonical_counts': {k: len(v) for k, v in d.items()},
            'derived_counts': {k: len(v) for k, v in r.items()},
            'project_splits': dict(Counter(p['split'] for p in d['projects'])),
            'outcome_counts': dict(Counter(o['status'] for o in d['outcomes'])),
            'measurement_quality_counts': dict(Counter(q for c in d['checkpoints'] for q in c['quality'].values())),
            'supervised_by_split_label': dict(Counter(f'{x["split"]}:{x["failed_by_12"]}' for x in r['forecast_labels'])),
            'validation_errors': validate_derived(d, r), 'ml_training_executed': False}


def build(output, seed=17):
    output = Path(output).resolve()
    originals = {name: sha(ROOT / name) for name in ORIGINALS}
    previous = output / 'sha256_manifest.json'
    if previous.exists() and json.loads(previous.read_text())['originals'] != originals:
        raise ValueError('Hash sumber berubah dari snapshot sebelumnya; perlu review, tidak ditimpa.')
    raw = output / 'raw/corpus_formulab.json'
    if raw.exists() and sha(raw) != originals['corpus_formulab.json']:
        raise ValueError('Snapshot raw berbeda; tidak ditimpa.')
    raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'corpus_formulab.json', raw)
    audit, aliases = audit_source(raw)
    d = generate(seed)
    errors = validate(d)
    if errors:
        raise ValueError(errors)
    r = derive(d)
    for group, tables in [('canonical', d), ('derived', r)]:
        for name, rows in tables.items():
            dump(output / group / f'{name}.jsonl', rows, lines=True)
    dump(output / 'audit_original.json', audit)
    dump(output / 'ingredient_aliases.json', aliases)
    dump(output / 'demo_components.json', [entity(k, seed, name=v, verification='unverified_demo_component',
        properties=None, alias_candidate=('ALIAS name-match only; unverified' if v in [a['name'] for a in aliases] else None))
        for k, v in DEMO_COMPONENTS.items()])
    dump(output / 'simulation_assumptions.json', ASSUMPTIONS)
    dump(output / 'authentic_rules.json', {'rules': [], 'sources': [], 'status': 'no_verified_public_rules_imported',
        'warning': 'Tidak ada klaim kimia/regulatory yang disahkan pipeline ini.'})
    dump(output / 'schema_contract.json', contract())
    dump(output / 'metrics.json', metrics(d, r))
    dump(output / 'metadata.json', {'version': VERSION, 'seed': seed, 'source_sha256': originals,
        'script_sha256': sha(Path(__file__)), 'scope': '12 project, 2 trial/project, 2 storage/trial',
        'split_policy': '6 keluarga formula; 4 train, 1 validation, 1 test; ditetapkan sebelum derivasi',
        'limitations': ['Semua angka adalah simulasi.', 'Tidak ada resep lab, human review, model, embedding, audio, atau gambar nyata.',
                        'Split keluarga demo bukan bukti generalisasi ilmiah.']})
    if originals != {name: sha(ROOT / name) for name in ORIGINALS}:
        raise ValueError('Sumber asli berubah selama build')
    # Output integrasi lain adalah pipeline mandiri; tidak boleh mengubah manifest pilot sintetis.
    excluded_roots = {'public_observed', 'training', 'open_sources', 'full_synthetic'}
    files = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*'))
             if p.is_file() and p.name != 'sha256_manifest.json' and p.relative_to(output).parts[0] not in excluded_roots}
    dump(previous, {'algorithm': 'sha256', 'originals': originals, 'files': files})
    errors = validate_directory(output)
    if errors:
        raise ValueError(errors)
    return metrics(d, r)


def validate_directory(output):
    output = Path(output)
    try:
        def read_rows(group, names):
            return {name: [json.loads(line) for line in (output / group / f'{name}.jsonl').read_text().splitlines()]
                    for name in names}
        d, r = read_rows('canonical', TABLES), read_rows('derived', DERIVED)
        errors = validate_derived(d, r)
        manifest = json.loads((output / 'sha256_manifest.json').read_text())
        excluded_roots = {'public_observed', 'training', 'open_sources', 'full_synthetic'}
        actual = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*'))
                  if p.is_file() and p.name != 'sha256_manifest.json' and p.relative_to(output).parts[0] not in excluded_roots}
        if manifest['files'] != actual:
            errors.append('Manifest file/hash tidak cocok')
        if manifest['originals'] != {name: sha(ROOT / name) for name in ORIGINALS}:
            errors.append('Hash sumber asli berubah')
        if sha(output / 'raw/corpus_formulab.json') != manifest['originals']['corpus_formulab.json']:
            errors.append('Raw snapshot tidak identik')
        audit, aliases = audit_source(output / 'raw/corpus_formulab.json')
        for name, expected in [('audit_original.json', audit), ('ingredient_aliases.json', aliases),
                               ('schema_contract.json', contract()), ('metrics.json', metrics(d, r)),
                               ('simulation_assumptions.json', ASSUMPTIONS)]:
            if json.loads((output / name).read_text()) != expected:
                errors.append(f'{name}: kontrak/audit tidak cocok')
        return errors
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return [f'Gagal membaca/validasi: {exc}']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'validate'])
    parser.add_argument('--output', type=Path, default=ROOT / 'data')
    parser.add_argument('--seed', type=int, default=17)
    args = parser.parse_args()
    try:
        result = build(args.output, args.seed) if args.command == 'build' else {'validation_errors': validate_directory(args.output)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return int(bool(result.get('validation_errors')))
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
