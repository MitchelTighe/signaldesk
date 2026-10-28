"""Hidden-reasoning control found during the first genuine Nebius run (2026-10-20)."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from signaldesk.budget import Budget, GuardError, LIGHTNING
from signaldesk.core import case_by_id
from signaldesk.live import LiveProvider, public_case, runbooks
from signaldesk.live_eval import main
from signaldesk.mock_server import mock_draft

CASE = case_by_id('clean-demo')


def ok(payload):
    content = json.loads(payload['messages'][1]['content'])
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(mock_draft(content))}}],
            'usage': {'prompt_tokens': 500, 'completion_tokens': 100, 'total_tokens': 600}}


class ThinkingToggleTests(unittest.TestCase):
    def capture(self, **kw):
        seen = []
        def transport(url, payload, token):
            seen.append(payload)
            return ok(payload)
        result = LiveProvider(LIGHTNING, Budget(), transport=transport, **kw).draft(CASE)
        return seen[0], result

    def test_default_payload_is_unchanged_spec(self):
        payload, result = self.capture()
        self.assertNotIn('chat_template_kwargs', payload)
        self.assertTrue(result['provenance']['thinking'])
        self.assertEqual(result['provenance']['finish_reason'], 'stop')

    def test_no_thinking_sends_template_flag_and_still_validates(self):
        payload, result = self.capture(thinking=False)
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(result['status'], 'supported-hypothesis')
        self.assertFalse(result['provenance']['thinking'])

    def test_thinking_must_be_boolean(self):
        with self.assertRaises(GuardError):
            LiveProvider(LIGHTNING, thinking='off')

    def test_reasoning_exhaustion_is_a_visible_error_with_finish_reason(self):
        def transport(url, payload, token):
            return {'choices': [{'finish_reason': 'length', 'message': {'content': ''}}],
                    'usage': {'prompt_tokens': 1500, 'completion_tokens': 1600, 'total_tokens': 3100}}
        r = LiveProvider(LIGHTNING, Budget(), transport=transport).draft(CASE)
        self.assertEqual(r['validation'], 'rejected-draft')
        self.assertEqual(r['provenance']['finish_reason'], 'length')

    def test_cache_is_partitioned_by_thinking_option(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            def transport(url, payload, token):
                calls.append(1)
                return ok(payload)
            LiveProvider(LIGHTNING, Budget(), d, transport=transport).draft(CASE)
            LiveProvider(LIGHTNING, Budget(), d, transport=transport, thinking=False).draft(CASE)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(list(Path(d).glob('*.json'))), 2)

    def test_cli_dry_run_records_request_options(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'r.json'
            with redirect_stdout(io.StringIO()):
                code = main(['--dry-run', '--no-thinking', '--case', 'clean-demo', '--models', LIGHTNING,
                             '--max-calls', '1', '--cache', str(Path(d) / 'c'), '--output', str(out)])
            self.assertEqual(code, 0)
            report = json.loads(out.read_text())
            self.assertEqual(report['request_options'], {'thinking': False, 'grounding': False,
                                                         'max_output_tokens': 1600})


if __name__ == '__main__':
    unittest.main()
