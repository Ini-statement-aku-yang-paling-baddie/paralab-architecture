"""Uji kontrak pilot; seluruh data hanya simulasi."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/build_data_pilot.py'


def api():
    spec = importlib.util.spec_from_file_location('pilot', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PilotTests(unittest.TestCase):
    def test_raw_audit_and_aliases(self):
        self.assertTrue(SCRIPT.exists(), 'CLI pilot belum tersedia')
        m = api()
        audit, aliases = m.audit_source(ROOT / 'corpus_paralab.json')
        self.assertEqual((audit['entries'], audit['unique_ids'], audit['trials'], audit['moisturizer'], len(aliases)), (200, 200, 492, 90, 23))
        self.assertEqual(audit['partial_formulas'], 200)
        self.assertTrue(audit['warnings'])
        self.assertTrue(all(a['verification'] == 'unverified_alias' and 'properties' not in a for a in aliases))

    def test_canonical_longitudinal_universe(self):
        m = api()
        self.assertTrue(hasattr(m, 'generate'), 'Generator kanonis belum tersedia')
        d = m.generate(seed=17)
        self.assertEqual(d, m.generate(seed=17))
        self.assertEqual(len(d['projects']), 12)
        self.assertEqual(len(d['trials']), 24)
        self.assertEqual(len(d['observation_series']), 48)
        for table in d.values():
            for row in table:
                self.assertIn('id', row)
                self.assertIn('provenance', row)
                self.assertFalse(row['human_verified'])
        for f in d['formulas']:
            self.assertAlmostEqual(sum(x['pct'] for x in f['ingredients']), 100)
            self.assertEqual(f['review_status'], 'unreviewed_not_lab_recipe')
        outcomes = {o['series_id']: o for o in d['outcomes']}
        for s in d['observation_series']:
            cs = [c for c in d['checkpoints'] if c['series_id'] == s['id']]
            self.assertEqual([c['week'] for c in cs], [w for w in m.WEEKS if w <= outcomes[s['id']]['last_week']])
        self.assertEqual({s['temperature_c'] for s in d['observation_series']}, {25, 40})
        self.assertTrue(any(o['status'] == 'right_censored' for o in d['outcomes']))
        self.assertTrue(any(o['status'] == 'uncertain' for o in d['outcomes']))
        self.assertTrue(any(c['quality']['ph'] == 'invalid' for c in d['checkpoints']))
        self.assertTrue(any(c['quality']['viscosity_cp'] == 'missing' for c in d['checkpoints']))

    def test_validator_rejects_corruption(self):
        m = api()
        self.assertTrue(hasattr(m, 'validate'), 'Validator belum tersedia')
        good = m.generate()
        self.assertEqual(m.validate(good), [])
        mutations = {
            'duplicate_id': lambda d: d['projects'].append(copy.deepcopy(d['projects'][0])),
            'broken_join': lambda d: d['trials'][0].update(formula_id='absent'),
            'cross_project': lambda d: d['trials'][0].update(formula_id=d['formulas'][2]['id']),
            'total': lambda d: d['formulas'][0]['ingredients'][0].update(pct=1),
            'nan': lambda d: d['checkpoints'][0]['measurements'].update(ph=float('nan')),
            'range': lambda d: d['checkpoints'][0]['measurements'].update(ph=99),
            'date': lambda d: d['checkpoints'][1].update(observed_at='2025-01-01'),
            'split': lambda d: d['checkpoints'][0].update(split='test'),
            'family_leak': lambda d: d['projects'][-1].update(family_id=d['projects'][0]['family_id']),
            'provenance': lambda d: d['checkpoints'][0].update(provenance={}),
            'human': lambda d: d['outcomes'][0].update(human_verified=True),
            'future_after_stop': lambda d: d['outcomes'][0].update(last_week=2, status='failed', stopped=True, failure_week=2),
            'future_narrative': lambda d: d['checkpoints'][0].update(note='Akan gagal minggu 12'),
            'missing_policy': lambda d: d['checkpoints'][0]['measurements'].update(ph=None),
            'orphan_outcome': lambda d: d['outcomes'].pop(),
            'false_pass': lambda d: d['outcomes'][1].update(status='passed'),
            'bad_temperature': lambda d: d['observation_series'][0].update(temperature_c=500),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                bad = copy.deepcopy(good)
                mutation(bad)
                self.assertTrue(m.validate(bad), name)

    def test_derivations_prevent_leakage_and_match_checkpoint(self):
        m = api()
        self.assertTrue(hasattr(m, 'derive'), 'Turunan belum tersedia')
        d = m.generate()
        r = m.derive(d)
        self.assertEqual({x['split'] for x in r['f1_train_corpus']}, {'train'})
        self.assertEqual({x['split'] for x in r['journal_documents']}, {'train', 'validation', 'test'})
        checkpoints = {c['id']: c for c in d['checkpoints']}
        outcomes = {o['series_id']: o for o in d['outcomes']}
        for x in r['forecast_features']:
            self.assertEqual(x['landmark_week'], 4)
            self.assertTrue(all(checkpoints[c]['week'] <= 4 for c in x['checkpoint_ids']))
            self.assertNotIn('status', x)
            self.assertNotIn('failure_week', x)
            self.assertNotIn('scenario', x)
            o = outcomes[x['series_id']]
            self.assertTrue(o['status'] == 'passed' or (o['status'] == 'failed' and o['failure_week'] > 4))
        self.assertEqual({x['id'] for x in r['forecast_features']}, {x['feature_id'] for x in r['forecast_labels']})
        self.assertTrue(r['forecast_censored'])
        self.assertTrue(r['forecast_excluded'])
        for x in r['f5_examples']:
            c = checkpoints[x['checkpoint_id']]
            self.assertEqual(x['transcript'], c['note'])
            self.assertEqual(x['target']['measurements'], c['measurements'])
            self.assertTrue(x['requires_confirmation'])
        self.assertEqual(r['image_manifest'], [])
        self.assertEqual(m.validate_derived(d, r), [])
        for table, field, value in [('f1_train_corpus', 'split', 'test'), ('f5_examples', 'transcript', 'pH 99'),
                                    ('forecast_features', 'checkpoint_ids', [d['checkpoints'][6]['id']]),
                                    ('forecast_labels', 'failed_by_12', 99)]:
            broken = copy.deepcopy(r)
            broken[table][0][field] = value
            self.assertTrue(m.validate_derived(d, broken))
        future = copy.deepcopy(d)
        future['checkpoints'][6]['measurements']['ph'] = 7
        future['checkpoints'][6]['raw_measurements']['ph'] = 7
        future['checkpoints'][6]['note'] = m.note(future['checkpoints'][6])
        self.assertEqual(m.derive(future)['forecast_features'], r['forecast_features'])

    def test_cli_exports_verified_deterministic_snapshot(self):
        import subprocess
        import sys
        m = api()
        self.assertTrue(hasattr(m, 'build'), 'Ekspor CLI belum tersedia')
        originals = {name: m.sha(ROOT / name) for name in ['corpus_paralab.json', 'embeddings_paralab.npy']}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'pilot'
            command = [sys.executable, str(SCRIPT), 'build', '--output', str(out)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*') if p.is_file()}
            subprocess.run(command, check=True, capture_output=True)
            after = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            manifest = json.loads((out / 'sha256_manifest.json').read_text())
            self.assertNotIn('sha256_manifest.json', manifest['files'])
            self.assertEqual(set(manifest['files']), set(before) - {'sha256_manifest.json'})
            self.assertEqual(m.sha(out / 'raw/corpus_paralab.json'), originals['corpus_paralab.json'])
            self.assertEqual(manifest['originals'], originals)
            self.assertTrue((out / 'schema_contract.json').exists())
            check = [sys.executable, str(SCRIPT), 'validate', '--output', str(out)]
            self.assertEqual(subprocess.run(check, capture_output=True).returncode, 0)
            cp = out / 'canonical/checkpoints.jsonl'
            cp.write_text(cp.read_text().replace('uniform', 'nonsense', 1))
            self.assertNotEqual(subprocess.run(check, capture_output=True).returncode, 0)
        self.assertEqual(originals, {name: m.sha(ROOT / name) for name in originals})

    def test_pilot_manifest_ignores_independent_integrated_outputs(self):
        m = api()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pilot"
            m.build(out)
            extra = out / "full_synthetic" / "metrics.json"
            extra.parent.mkdir(parents=True)
            extra.write_text("{}\n")
            self.assertEqual(m.validate_directory(out), [])

    def test_validator_enforces_component_schema_and_provenance(self):
        m = api()
        good = m.generate()
        mutations = {
            'unknown_component': lambda d: d['formulas'][0]['ingredients'][0].update(ingredient_id='ING:UNKNOWN'),
            'missing_required_field': lambda d: d['projects'][0].pop('target_skin'),
            'mixed_seed': lambda d: d['checkpoints'][0]['provenance'].update(seed=999),
            'extra_future_feature': lambda d: d['formulas'][0]['process'].update(future_failure_week=8),
            'invalid_raw_actually_valid': lambda d: next(c for c in d['checkpoints'] if c['quality']['ph'] == 'invalid')['raw_measurements'].update(ph='5.5'),
            'empty_universe': lambda d: [d[k].clear() for k in d],
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                bad = copy.deepcopy(good)
                mutation(bad)
                if name == 'invalid_raw_actually_valid':
                    for c in bad['checkpoints']:
                        c['note'] = m.note(c)
                self.assertTrue(m.validate(bad), name)

    def test_each_split_has_known_horizon_examples(self):
        m = api()
        r = m.derive(m.generate())
        for split in ['train', 'validation', 'test']:
            with self.subTest(split=split):
                self.assertEqual({x['failed_by_12'] for x in r['forecast_labels'] if x['split'] == split}, {0, 1})

    def test_measurement_payload_cannot_smuggle_future_fields(self):
        m = api()
        d = m.generate()
        d['checkpoints'][0]['measurements']['future_failure_week'] = 8
        self.assertTrue(m.validate(d))


if __name__ == '__main__':
    unittest.main()
