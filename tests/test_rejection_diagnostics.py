"""Privacy-preserving diagnostics through the real provider/cache/evaluation path."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from signaldesk.budget import Budget, LIGHTNING
from signaldesk.core import case_by_id
from signaldesk.live import LiveProvider, public_case, runbooks
from signaldesk.live_eval import evaluate_models
from signaldesk.mock_server import mock_draft
from signaldesk.providers import ProviderError
from signaldesk.safeio import digest, pack

CASE = case_by_id('clean-demo')
MARKER = 'UNTRUSTED-DIAGNOSTIC-BODY'


def draft():
    return mock_draft({'incident': public_case(CASE), 'runbooks': runbooks()})


def response(value=None, raw=None, finish='stop'):
    return {'choices': [{'finish_reason': finish, 'message': {
        'content': raw if raw is not None else json.dumps(draft() if value is None else value)}}],
        'usage': {'prompt_tokens': 500, 'completion_tokens': 500, 'total_tokens': 1000}}


class RejectionDiagnosticsTests(unittest.TestCase):
    def rejected(self, envelope, code):
        p = LiveProvider(LIGHTNING, transport=lambda *a: envelope)
        result = p.draft(CASE)
        self.assertEqual(result['validation'], 'rejected-draft')
        self.assertEqual(result['rejection_code'], code)
        self.assertIsNone(result['runbook_id'])
        self.assertEqual(result['actions_executed'], 0)
        self.assertNotIn(MARKER, json.dumps(result))
        self.assertEqual(p.budget.calls, 1)
        return result

    def test_missing_response_fields_have_an_envelope_code(self):
        for choices in [[], [{}], [{'finish_reason': 'stop'}]]:
            with self.subTest(choices=choices):
                self.rejected({'choices': choices, 'usage': response()['usage']}, 'response-envelope')

    def test_unfinished_responses_are_distinct_from_json_errors(self):
        for finish in ['length', 'content_filter', 'tool_calls', MARKER]:
            with self.subTest(finish=finish):
                self.rejected(response(raw=MARKER, finish=finish), 'unfinished-response')

    def test_invalid_json_does_not_echo_parser_details(self):
        for raw in [MARKER, '{"x":1,"x":2}', '{"x":NaN}', MARKER * 6000]:
            with self.subTest(length=len(raw)):
                self.rejected(response(raw=raw), 'invalid-json')

    def test_validator_failures_have_fixed_content_free_codes(self):
        changes = [({'unexpected': MARKER}, 'draft-schema'),
                   ({'steps': MARKER}, 'draft-lists'),
                   ({'web_citations': [MARKER]}, 'web-citation'),
                   ({'runbook_id': MARKER}, 'selection-invalid'),
                   ({'evidence_ids': [MARKER]}, 'selection-invalid'),
                   ({'hypothesis': MARKER}, 'runbook-content')]
        for change, code in changes:
            with self.subTest(code=code):
                value = draft(); value.update(change)
                self.rejected(response(value), code)
        value = draft(); value['steps'][0]['text'] = MARKER
        self.rejected(response(value), 'step-citation')
        value = draft(); value.update(runbook_id=None, hypothesis=MARKER)
        self.rejected(response(value), 'abstention-shape')

    def test_reason_code_survives_cache_replay_without_raw_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = draft(); value['steps'][0]['text'] = MARKER
            LiveProvider(LIGHTNING, cache_dir=tmp, transport=lambda *a: response(value)).draft(CASE)
            raw = next(Path(tmp).glob('*.json')).read_text()
            self.assertNotIn(MARKER, raw)
            p = LiveProvider(LIGHTNING, cache_dir=tmp, replay=True,
                             transport=lambda *a: self.fail('network'))
            result = p.draft(CASE)
            self.assertEqual(result['rejection_code'], 'step-citation')
            self.assertEqual(p.cache_hits, 1); self.assertEqual(p.budget.calls, 0)

    def test_legacy_rejection_is_explicitly_unknown_not_inferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = draft(); value['hypothesis'] = MARKER
            LiveProvider(LIGHTNING, cache_dir=tmp, transport=lambda *a: response(value)).draft(CASE)
            path = next(Path(tmp).glob('*.json')); saved = json.loads(path.read_text())
            saved['record']['result'].pop('rejection_code', None)
            saved['sha256'] = digest(saved['record']); path.write_bytes(pack(saved))
            p = LiveProvider(LIGHTNING, cache_dir=tmp, replay=True,
                             transport=lambda *a: self.fail('network'))
            self.assertEqual(p.draft(CASE)['rejection_code'], 'unknown-legacy')
            self.assertEqual(p.budget.calls, 0)

    def test_cache_cannot_supply_arbitrary_diagnostic_prose(self):
        for rejected in [False, True]:
            with self.subTest(rejected=rejected), tempfile.TemporaryDirectory() as tmp:
                value = draft()
                if rejected: value['hypothesis'] = MARKER
                LiveProvider(LIGHTNING, cache_dir=tmp, transport=lambda *a: response(value)).draft(CASE)
                path = next(Path(tmp).glob('*.json')); saved = json.loads(path.read_text())
                saved['record']['result']['rejection_code'] = MARKER
                saved['sha256'] = digest(saved['record']); path.write_bytes(pack(saved))
                with self.assertRaisesRegex(ProviderError, 'integrity or validation'):
                    LiveProvider(LIGHTNING, cache_dir=tmp, replay=True,
                                 transport=lambda *a: self.fail('network')).draft(CASE)

    def test_evaluation_retains_code_and_counts_failure_as_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_models([LIGHTNING], [CASE], Budget(), tmp,
                                     transport=lambda *a: response(raw=MARKER))
        self.assertTrue(result['complete']); self.assertFalse(result['quality_gates_passed'])
        self.assertEqual(result['rows'][0]['brief']['rejection_code'], 'invalid-json')
        self.assertEqual(result['metrics'][LIGHTNING]['errors'], 1)
        self.assertEqual(result['metrics'][LIGHTNING]['correct'], 0)
        self.assertNotIn(MARKER, json.dumps(result))
