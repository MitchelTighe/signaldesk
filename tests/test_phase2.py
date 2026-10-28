from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from signaldesk import core
from signaldesk.core import brief, corpus, dataset, evaluate, LocalClassifier, validate_selection
from signaldesk.providers import ENDPOINTS, NebiusProvider, ProviderError
from signaldesk.web import render
from test_signaldesk import envelope


class CorpusTests(unittest.TestCase):
    def test_corpus_has_eight_families_and_sixty_four_real_tickets(self):
        cases = corpus('training')['cases']
        self.assertEqual(len(cases), 64)
        self.assertEqual(len({c['id'] for c in cases}), 64)
        self.assertEqual(set(Counter(c['expected'] for c in cases).values()), {8})
        self.assertEqual(len({c['expected'] for c in cases}), 8)
        self.assertTrue(all(len(c['text'].split()) >= 15 and c['evidence'] for c in cases))
        books = dataset()['runbooks']
        self.assertTrue(all(len(r['steps']) == 3 and r['caveat'] for r in books))
        for c in cases:
            accepted, reason = validate_selection({'runbook_id': c['expected'],
                                                   'evidence_ids': [e['id'] for e in c['evidence']]}, c, books)
            self.assertIsNotNone(accepted, (c['id'], reason))

    def test_heldout_file_has_not_changed_since_freeze(self):
        path = Path(core.__file__).with_name('heldout.json')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '8baefc13ff2668904208bbc96028611db43a273d1ceed883210e55532ce9d9ca')
        cases = corpus('heldout')['cases']
        self.assertEqual(len(cases), 40)
        self.assertEqual(sum(c['expected'] is None for c in cases), 8)

    def test_training_heldout_and_demo_text_and_ids_are_disjoint(self):
        sets = [corpus('training')['cases'], corpus('heldout')['cases'], dataset()['cases']]
        for i, a in enumerate(sets):
            for b in sets[i+1:]:
                self.assertFalse({c['id'] for c in a} & {c['id'] for c in b})
                self.assertFalse({c['text'].lower() for c in a} & {c['text'].lower() for c in b})

    def test_training_does_not_read_heldout_or_evidence(self):
        original = corpus('training')
        def training_only(split):
            self.assertEqual(split, 'training', 'classifier leaked held-out data')
            return original
        with patch('signaldesk.core.corpus', side_effect=training_only):
            model = LocalClassifier(dataset()['runbooks'])
        first = model.select(dataset()['cases'][0])[0]['runbook_id']
        changed = deepcopy(dataset()['cases'][0]); changed['evidence'] = []; changed['expected'] = 'RB-FAKE'
        self.assertEqual(model.select(changed)[0]['runbook_id'], first)

    def test_metric_denominators_count_wrong_accepted_predictions(self):
        cases = [{'id': 'A', 'expected':'RB-CLEAN'}, {'id':'B','expected':'RB-MEDIA'},
                 {'id':'C','expected':'RB-HWFAULT'}, {'id':'D','expected':None}]
        actual = iter(['RB-CLEAN', 'RB-CLEAN', None, None])
        def fake_brief(c, provider):
            return {'runbook_id':next(actual),'reason':None,'provenance':{'score':0.8}}
        with patch('signaldesk.core.corpus', return_value={'cases':cases}), \
             patch('signaldesk.core.LocalClassifier'), patch('signaldesk.core.brief', side_effect=fake_brief):
            result = evaluate()
        m = result['metrics']
        self.assertEqual(m['precision'], 1/2)
        self.assertEqual(m['recall'], 1/3)
        self.assertEqual(m['abstention_rate'], 1/2)
        self.assertEqual(result['correct'], 2)
        self.assertEqual(result['per_family']['RB-CLEAN']['precision'], 1/2)
        self.assertEqual(result['per_family']['RB-MEDIA']['recall'], 0)

    def test_heldout_quality_gates_and_misses_remain_visible(self):
        result = evaluate(); m = result['metrics']
        self.assertGreaterEqual(m['precision'], .8)
        self.assertGreaterEqual(m['recall'], .65)
        self.assertEqual(m['unknown_rejection_rate'], 1)
        self.assertGreater(len([r for r in result['cases'] if not r['correct']]), 0)
        self.assertEqual(sum(r['actual'] is None for r in result['cases']), m['abstained'])

    def test_all_splits_render_only_corroborated_local_steps(self):
        books = {r['id']: r for r in dataset()['runbooks']}
        for case in corpus('training')['cases'] + corpus('heldout')['cases']:
            r = brief(case)
            self.assertEqual(r['actions_executed'], 0)
            if r['runbook_id']:
                self.assertEqual([s['text'] for s in r['steps']], books[r['runbook_id']]['steps'])
                self.assertTrue(all(e in case['evidence'] for e in r['evidence']))
            else:
                self.assertEqual(r['steps'], [])


class GateAndAdapterTests(unittest.TestCase):
    def test_multi_fault_abstains_even_if_model_hides_other_metric(self):
        case = deepcopy(dataset()['cases'][1])
        case['evidence'].append({'id':'OTHER','metric':'tapealert_media_flags','value':99})
        accepted, reason = validate_selection({'runbook_id':'RB-CLEAN','evidence_ids':['E-C1']}, case, dataset()['runbooks'])
        self.assertIsNone(accepted)
        self.assertIn('Multiple', reason)

    def test_percentage_outside_domain_is_not_evidence(self):
        # No tape family uses percent today; the validator's percent ceiling is still enforced.
        book = {'id': 'RB-PCT', 'metric': 'synthetic_pct', 'minimum': 20, 'unit': 'percent'}
        for value, ok in [(101, False), (100, True), (20, True)]:
            case = {'evidence': [{'id': 'E', 'metric': 'synthetic_pct', 'value': value}]}
            accepted, _ = validate_selection({'runbook_id': 'RB-PCT', 'evidence_ids': ['E']}, case, [book])
            self.assertEqual(accepted is not None, ok, value)
        case = deepcopy(dataset()['cases'][1]); case['evidence'][0]['value'] = -1
        self.assertIsNone(brief(case)['runbook_id'])

    def test_threshold_boundary_is_inclusive(self):
        for rb in dataset()['runbooks']:
            case = {'evidence':[{'id':'E','metric':rb['metric'],'value':rb['minimum']}]}
            selection = {'runbook_id':rb['id'],'evidence_ids':['E']}
            self.assertIsNotNone(validate_selection(selection, case, dataset()['runbooks'])[0])
            case['evidence'][0]['value'] -= 1
            self.assertIsNone(validate_selection(selection, case, dataset()['runbooks'])[0])

    def test_regional_adapter_is_mocked_and_has_no_labels_or_training(self):
        requests = []
        def fake(req):
            requests.append(req)
            return envelope({'runbook_id':'RB-CLEAN','evidence_ids':['E-C1']})
        with patch('socket.socket', side_effect=AssertionError('network prohibited')):
            provider = NebiusProvider('nvidia/nvidia-nemotron-3-nano-30b-a3b','fixture-credential',fake,'us-central1')
            result = brief(dataset()['cases'][1],provider)
        self.assertEqual(requests[0].full_url, ENDPOINTS['us-central1'])
        context = json.loads(json.loads(requests[0].data)['messages'][1]['content'])
        self.assertNotIn('expected', context['incident'])
        self.assertFalse(any('training' in r for r in context['runbooks']))
        self.assertNotIn('T-CLEAN-01', json.dumps(context))
        self.assertNotIn('H01', json.dumps(context))
        self.assertEqual(result['provenance']['transport'], 'injected-test-transport')
        self.assertIsInstance(result['provenance']['elapsed_ms'], float)

    def test_arbitrary_endpoint_is_rejected(self):
        with self.assertRaises(ProviderError):
            NebiusProvider('nvidia/test','fixture-credential', endpoint='https://other.invalid')

    def test_training_and_heldout_are_never_eligible_for_live_send(self):
        provider = NebiusProvider('nvidia/test','fixture-credential',lambda req:self.fail('sent corpus'))
        for split in ['training','heldout']:
            with self.assertRaises(ProviderError):
                provider.select(corpus(split)['cases'][0])


class WebExportTests(unittest.TestCase):
    def test_export_is_current_and_embeds_actual_briefs(self):
        html = render()
        self.assertEqual(html, Path(core.__file__).parents[1].joinpath('web/index.html').read_text())
        packed = html.split('<script id="fixture-data" type="application/json">',1)[1].split('</script>',1)[0]
        data = json.loads(packed)
        self.assertEqual(len(data['tickets']), 176)
        self.assertEqual(len(data['runbooks']), 8)
        for item in data['tickets']:
            self.assertNotIn('expected', item['case'])
        self.assertEqual(data['tickets'][0]['brief'], brief(dataset()['cases'][0]))

    def test_export_remains_local_and_displays_text_safely(self):
        html = render()
        self.assertIn("connect-src 'none'", html)
        self.assertNotIn('src="https://', html)
        # Adversarial fixtures intentionally contain fetch/HTML as inert data.
        executable = html.rsplit('<script>', 1)[1].split('</script>', 1)[0]
        self.assertNotIn('fetch(', executable)
        self.assertNotIn('.innerHTML', executable)
        self.assertIn('aria-live="polite"', html)
