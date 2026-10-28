"""Finish acceptance: real recorded-demo fallback and new frozen evaluation."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from signaldesk import demo, finish_eval
from signaldesk.budget import LIGHTNING
from signaldesk.core import corpus
from signaldesk.live import LiveProvider, runbooks
from signaldesk.mock_server import mock_draft
from signaldesk.providers import ProviderError
from signaldesk.safeio import pack

ENTRY = Path(__file__).parents[1]


class RecordedDemoTests(unittest.TestCase):
    def test_default_never_reads_a_key_or_opens_network(self):
        with patch('signaldesk.live.credential', side_effect=AssertionError('key read')), \
             patch('socket.socket', side_effect=AssertionError('network')):
            result = demo.run_demo()
        self.assertEqual(result['mode'], 'recorded')
        # The bundled site is the genuine recorded Nebius run (rebuilt with --require-live).
        self.assertIn('RECORDED NEBIUS RESPONSES', result['notice'])
        self.assertEqual(result['calls_reserved_this_run'], 0)
        self.assertEqual([r['case_id'] for r in result['routed']], list(demo.ROUTED_TOUR))
        routed = {r['case_id']: r for r in result['routed']}
        self.assertEqual(routed['X01']['path'], 'pre-triage')
        self.assertEqual(routed['X01']['telemetry'], 'healthy')
        self.assertTrue(routed['X06']['vetoes'])
        self.assertEqual([b['case_id'] for b in result['briefs']], list(demo.CASES))
        self.assertEqual([b['status'] for b in result['briefs']],
                         ['supported-hypothesis', 'needs-human', 'needs-human'])
        self.assertTrue(all(b['actions_executed'] == 0 for b in result['briefs']))

    def test_missing_key_falls_back_without_request(self):
        with patch.dict(os.environ, {'NEBIUS_API_KEY': ''}), \
             patch('socket.socket', side_effect=AssertionError('network')):
            result = demo.run_demo(live=True)
        self.assertEqual(result['mode'], 'recorded')
        self.assertIn('unavailable', result['fallback_reason'])
        self.assertEqual(result['calls_reserved_this_run'], 0)

    def test_transport_failure_keeps_reservation_and_never_echoes_remote_body(self):
        calls = []
        def transport(*args):
            calls.append(1)
            raise ProviderError('SYNTHETIC UNTRUSTED REMOTE ERROR BODY')
        def provider(model, budget):
            return LiveProvider(model, budget=budget, transport=transport)
        result = demo.run_demo(live=True, provider_factory=provider)
        self.assertEqual(calls, [1])
        self.assertEqual(result['mode'], 'recorded')
        self.assertEqual(result['calls_reserved_this_run'], 1)
        self.assertGreater(result['budget']['tokens_reserved'], 0)
        self.assertNotIn('UNTRUSTED', json.dumps(result))

    def test_explicit_live_path_uses_three_bundled_inputs_and_guarded_provider(self):
        calls = []
        def transport(url, payload, token):
            context = json.loads(payload['messages'][-1]['content'])
            calls.append(context['incident']['id'])
            return {'choices': [{'finish_reason': 'stop', 'message': {'content':
                    json.dumps(mock_draft(context))}}],
                    'usage': {'prompt_tokens': 500, 'completion_tokens': 500, 'total_tokens': 1000}}
        def provider(model, budget):
            return LiveProvider(model, budget=budget, transport=transport)
        result = demo.run_demo(live=True, provider_factory=provider)
        self.assertEqual(calls, list(demo.CASES))
        self.assertEqual(result['mode'], 'live')
        self.assertEqual(result['calls_reserved_this_run'], 3)
        self.assertTrue(all(b['provenance']['origin'] == 'injected-mock' for b in result['briefs']))

    def test_partial_live_failure_switches_whole_demo_to_recordings(self):
        calls = []
        def transport(url, payload, token):
            calls.append(1)
            if len(calls) == 2:
                raise ProviderError('synthetic outage')
            context = json.loads(payload['messages'][-1]['content'])
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(mock_draft(context))}}],
                    'usage': {'prompt_tokens': 500, 'completion_tokens': 500, 'total_tokens': 1000}}
        result = demo.run_demo(live=True, provider_factory=lambda m, budget: LiveProvider(m, budget=budget, transport=transport))
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['mode'], 'recorded')
        self.assertEqual(result['calls_reserved_this_run'], 2)
        self.assertEqual(result['briefs'], demo.recorded_demo()['briefs'])

    def test_corrupt_recording_fails_before_any_live_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            shutil.copy(ENTRY/'site/manifest.json', target)
            (target/'replay.json').write_text('{}')
            with self.assertRaises(ValueError), patch('signaldesk.live.credential', side_effect=AssertionError('key')):
                demo.run_demo(live=True, site=target)

    def test_rehashed_forged_steps_fail_independent_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            raw = json.loads((ENTRY/'site/replay.json').read_text())
            raw['rows'][0]['brief']['steps'][0]['text'] = 'Synthetic unsourced instruction'
            payload = pack(raw)
            (target/'replay.json').write_bytes(payload)
            (target/'manifest.json').write_text(json.dumps({'files': {'replay.json': hashlib.sha256(payload).hexdigest()}}))
            with self.assertRaises(ValueError):
                demo.recorded_demo(target)

    def test_cli_outputs_reproducible_json_and_safe_failure(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(demo.main(['--json']), 0)
        self.assertEqual(json.loads(out.getvalue())['mode'], 'recorded')
        with patch('signaldesk.demo.run_demo', side_effect=ValueError('UNTRUSTED BODY')), \
             redirect_stderr(io.StringIO()) as err:
            self.assertEqual(demo.main([]), 2)
        self.assertNotIn('UNTRUSTED', err.getvalue())

    def test_real_cli_from_foreign_working_directory(self):
        environment = dict(os.environ, PYTHONPATH=str(ENTRY), PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([os.sys.executable, '-m', 'signaldesk.demo', '--json'],
                                    cwd=tmp, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['calls_reserved_this_run'], 0)


class FinishEvaluationTests(unittest.TestCase):
    def test_ten_independent_scenarios_cover_all_criteria_and_boundaries(self):
        cases = finish_eval.finish_cases()
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({c['id'] for c in cases}), 10)
        self.assertEqual(set.union(*(set(c['judging_criteria']) for c in cases)),
                         {'implementation', 'design', 'impact', 'idea'})
        self.assertTrue(any(c['case']['text'] == '' for c in cases))
        self.assertTrue(any(not c['case']['evidence'] for c in cases))
        self.assertTrue(any(len(c['case']['text']) > 50_000 for c in cases))
        self.assertTrue(any(c['expected_outcome'] == 'rejected-draft' for c in cases))

    def test_finish_eval_invokes_real_validator_without_network(self):
        with patch('socket.socket', side_effect=AssertionError('network')):
            result = finish_eval.evaluate_finish()
        self.assertEqual(result['passed'], result['total'])
        self.assertEqual(result['total'], 10)
        self.assertTrue(result['quality_gates_passed'])
        self.assertEqual(sum(r['actual_outcome'] == 'rejected-draft' for r in result['cases']), 4)

    def test_incorrect_decision_remains_a_failure(self):
        cases = deepcopy(finish_eval.finish_cases())
        cases[0]['expected_outcome'] = 'supported-hypothesis'
        with patch('signaldesk.finish_eval.finish_cases', return_value=cases):
            result = finish_eval.evaluate_finish()
        self.assertEqual(result['passed'], 9)
        self.assertFalse(result['quality_gates_passed'])

    def test_baseline_outcomes_are_reported_with_full_denominator_and_misses(self):
        result = finish_eval.evaluate_finish()
        self.assertEqual(result['baseline_backend'], 'offline-naive-bayes')
        self.assertEqual(result['baseline_label_matches'],
                         sum(r['baseline_actual'] == r['baseline_expected'] for r in result['cases']))
        self.assertEqual(result['baseline_misses'],
                         [r['id'] for r in result['cases'] if not r['baseline_label_match']])
        self.assertTrue(all(r['baseline_output_confined'] for r in result['cases']))
        self.assertEqual(len(result['cases']), 10)

    def test_programming_exception_is_not_counted_as_safe_rejection(self):
        with patch('signaldesk.finish_eval.validate_draft', side_effect=KeyError('implementation bug')):
            with self.assertRaises(KeyError):
                finish_eval.evaluate_finish()

    def test_new_cases_never_become_allowed_live_inputs(self):
        provider = LiveProvider(LIGHTNING, transport=lambda *a: self.fail('request'))
        for row in finish_eval.finish_cases():
            with self.subTest(row=row['id']), self.assertRaises(ProviderError):
                provider.draft(row['case'])
        self.assertEqual(provider.budget.calls, 0)

    def test_frozen_case_corruption_is_rejected(self):
        with patch('signaldesk.finish_eval.Path') as path:
            path.return_value.with_name.return_value.read_bytes.return_value = b'{}'
            with self.assertRaisesRegex(ValueError, 'checksum'):
                finish_eval.finish_cases()
