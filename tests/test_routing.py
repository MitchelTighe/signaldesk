"""Hard split, deterministic pre-triage, recorded vetoes and cost-aware routing."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from signaldesk.budget import LIGHTNING, SUPER
from signaldesk.core import corpus, dataset
from signaldesk.live import canonical_draft, public_case, runbooks, validate_draft
from signaldesk.replay import merge_reports, sanitize_report
from signaldesk.routing import PHYSICAL, claims, compare
from signaldesk.telemetry import rules_decision, split_cases, telemetry_state

ENTRY = Path(__file__).parents[1]
RUNTIME = ENTRY / 'docs/runtime'
RAW = ENTRY / 'fixtures/tape-captures-20261021/raw'


def report(name):
    return json.loads((RUNTIME / name).read_text())


class HardSplitTests(unittest.TestCase):
    def test_hard_split_is_disjoint_and_covers_the_adversarial_kinds(self):
        hard = split_cases('hard')
        self.assertEqual(len(hard), 14)
        others = corpus('training')['cases'] + corpus('heldout')['cases'] + dataset()['cases']
        self.assertFalse({c['id'] for c in hard} & {c['id'] for c in others})
        self.assertFalse({c['text'].lower() for c in hard} & {c['text'].lower() for c in others})
        kinds = {c['kind'] for c in hard}
        for kind in ('healthy', 'caveat', 'injection', 'conflict', 'text-conflict', 'threshold-edge', 'thin'):
            self.assertIn(kind, kinds)

    def test_capture_derived_text_quotes_lines_that_exist_in_the_raw_mhvtl_files(self):
        raw = '\n'.join(p.read_text() for p in RAW.rglob('*.txt'))
        quotes = {'X01': 'Cleaning required: 0', 'X02': 'Cleaning requested: 1',
                  'X03': 'MOVE MEDIUM from Element Address 1038 to 500 Failed',
                  'X04': 'Cleaning media: 1', 'X09': 'Data Transfer Element 1:Full (Storage Element 5 Loaded):VolumeTag = A00005L8',
                  'X13': 'Invalid field in cdb'}
        cases = {c['id']: c for c in split_cases('hard')}
        for cid, quote in quotes.items():
            self.assertIn(quote, raw, cid)
            self.assertTrue(cases[cid]['capture'].startswith('mhvtl:'))

    def test_labels_kind_and_rationale_never_reach_the_model(self):
        for case in split_cases('hard'):
            sent = public_case(case)
            self.assertEqual(set(sent), {'id', 'title', 'text', 'evidence'})
        changed = deepcopy(split_cases('hard')[0]); changed['text'] += ' edited'
        with self.assertRaises(Exception):
            public_case(changed)


class TelemetryTests(unittest.TestCase):
    def test_rejected_draft_is_not_a_correct_model_or_routed_handoff(self):
        cases = split_cases('hard')
        original = report('live-evaluation-20261021-routed-hard.json')['rows']
        before = compare(original, cases)
        # X02 has a real, valid Super handoff after Lightning proposes cleaning.
        self.assertEqual(next(c for c in cases if c['id'] == 'X02')['expected'], None)
        self.assertEqual(next(c for c in before['cases'] if c['case_id'] == 'X02')['path'], 'escalated-to-super')
        rejected = deepcopy(original)
        row = next(r for r in rejected if r['model'] == SUPER and r['case_id'] == 'X02')
        self.assertEqual(row['outcome'], 'validated')
        row.update(outcome='error', actual=None)
        after = compare(rejected, cases)
        self.assertEqual(after['super_only']['correct'], before['super_only']['correct'] - 1)
        self.assertEqual(after['routed']['correct'], before['routed']['correct'] - 1)
        self.assertEqual(after['rules_only'], before['rules_only'])
        # A conclusive zero-call pre-triage answer stays valid even if separate
        # experimental model calls for the same case fail.
        rejected = deepcopy(original)
        for row in rejected:
            if row['case_id'] == 'X01':
                row.update(outcome='error', actual=None)
        after = compare(rejected, cases)
        self.assertEqual(after['routed']['correct'], before['routed']['correct'])
        self.assertEqual(after['super_only']['correct'], before['super_only']['correct'] - 1)

    def test_states_cover_healthy_single_conflict_missing_invalid(self):
        hard = {c['id']: c for c in split_cases('hard')}
        held = {c['id']: c for c in corpus('heldout')['cases']}
        self.assertEqual(telemetry_state(hard['X01'])['state'], 'healthy')
        self.assertEqual(telemetry_state(hard['X09'])['state'], 'single')
        self.assertEqual(telemetry_state(hard['X10'])['state'], 'conflict')
        self.assertEqual(telemetry_state(held['H36'])['state'], 'missing')
        self.assertEqual(telemetry_state(held['H39'])['state'], 'invalid')
        self.assertEqual(telemetry_state(hard['X08'])['state'], 'healthy')  # 119 s < 120 s gate

    def test_rules_only_baseline_matches_heldout_but_cannot_read_caveats(self):
        held = corpus('heldout')['cases']
        self.assertEqual(sum(rules_decision(c) == c['expected'] for c in held), 40)
        wrong = [c['id'] for c in split_cases('hard') if rules_decision(c) != c['expected']]
        self.assertEqual(wrong, ['X02', 'X03'])  # it would clean a third time / repeat a failed move


class VetoTests(unittest.TestCase):
    def setUp(self):
        self.case = public_case(next(c for c in corpus('heldout')['cases'] if c['id'] == 'H35'))
        book = next(r for r in runbooks() if r['id'] == 'RB-INVENTORY')
        self.draft = {'runbook_id': 'RB-INVENTORY', 'evidence_ids': ['H35-E1'], 'hypothesis': book['title'],
                      'steps': [{'source': 'RB-INVENTORY', 'step': 1, 'text': book['steps'][0]}],
                      'web_citations': []}

    def test_vetoed_proposal_is_recorded_as_ids_only_and_re_derives(self):
        result = validate_draft(self.draft, self.case)
        self.assertEqual(result['validation'], 'telemetry-abstention')
        self.assertIsNone(result['runbook_id'])
        self.assertEqual(result['model_proposal'], {'runbook_id': 'RB-INVENTORY',
                                                    'evidence_ids': ['H35-E1'], 'step_numbers': [1]})
        again = validate_draft(canonical_draft(result), self.case)
        self.assertEqual(again['model_proposal'], result['model_proposal'])

    def test_forged_recorded_proposal_is_refused(self):
        result = validate_draft(self.draft, self.case)
        for bad in [{'runbook_id': 'RB-FAKE', 'evidence_ids': [], 'step_numbers': [1]},
                    {'runbook_id': 'RB-INVENTORY', 'evidence_ids': [], 'step_numbers': [9]},
                    {'runbook_id': 'RB-INVENTORY', 'evidence_ids': [], 'step_numbers': ['1'], 'x': 1}]:
            forged = deepcopy(result); forged['model_proposal'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                canonical_draft(forged)


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = report('live-evaluation-20261021-routed-hard.json')
        cls.held = report('live-evaluation-20261021-routed-heldout.json')

    def test_recorded_reports_are_genuine_and_complete(self):
        for r in (self.hard, self.held):
            self.assertEqual(r['origins'], ['live-nebius'])
            self.assertTrue(r['complete'])
            self.assertEqual(r['models'], [LIGHTNING, SUPER])

    def test_route_is_recomputed_from_rows_and_pre_triage_costs_nothing(self):
        cases = split_cases('hard')
        routed = compare(self.hard['rows'], cases)
        self.assertEqual(routed['cases'], self.hard['routing']['cases'])
        for policy in ('routed', 'lightning_only', 'super_only', 'rules_only'):
            for key in ('correct', 'total', 'unsafe_accepts', 'model_calls'):
                self.assertEqual(routed[policy][key], self.hard['routing'][policy][key])
        for c in routed['cases']:
            if c['path'] == 'pre-triage':
                self.assertEqual((c['usd'], c['latency_ms'], c['models_called']), (0.0, 0.0, []))
            if c['path'] == 'lightning':
                self.assertNotIn(c['decision'], PHYSICAL)

    def test_route_has_no_unsafe_action_where_rules_and_lightning_do(self):
        r = self.hard['routing']
        self.assertEqual(r['routed']['unsafe_accepts'], 0)
        self.assertEqual(r['rules_only']['unsafe_accepts'], 2)
        self.assertEqual(r['lightning_only']['unsafe_accepts'], 2)
        self.assertLess(r['routed']['usd'], r['super_only']['usd'])

    def test_claim_counts_add_up(self):
        for model, c in claims(self.held['rows'] + self.hard['rows']).items():
            self.assertEqual(c['proposed'], c['backed'] + c['vetoed'])
            self.assertEqual(len(c['vetoed_cases']), c['vetoed'])


class MergeTests(unittest.TestCase):
    def test_merge_needs_one_heldout_and_one_hard_report(self):
        held = report('live-evaluation-20261021-routed-heldout.json')
        hard = report('live-evaluation-20261021-routed-hard.json')
        merged = sanitize_report(merge_reports([held, hard]), require_live=True)
        self.assertEqual(merged['split'], 'heldout+hard')
        self.assertEqual(len(merged['rows']), 108)
        self.assertEqual(set(merged['groups']), {'heldout', 'hard'})
        self.assertTrue(all('telemetry' in r for r in merged['rows']))
        with self.assertRaises(ValueError):
            merge_reports([held, held])
        # A stored veto must still be a veto when re-derived: turning Lightning's vetoed
        # X06 proposal into the runbook the readings DO back is refused.
        tampered = deepcopy(hard)
        row = next(r for r in tampered['rows'] if r['case_id'] == 'X06' and r['model'] == LIGHTNING)
        row['brief']['model_proposal'].update(runbook_id='RB-MEDIA', evidence_ids=['X06-E1'])
        with self.assertRaises(ValueError):
            sanitize_report(merge_reports([held, tampered]))


if __name__ == '__main__':
    unittest.main()
