"""Frozen second-author inputs and the actual guarded CLI; never vendor evidence."""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signaldesk import live_eval, mock_server
from signaldesk.budget import LIGHTNING, SUPER
from signaldesk.core import corpus, dataset
from signaldesk.live import public_case
from signaldesk.providers import ProviderError
from signaldesk.telemetry import split_cases

ENTRY = Path(__file__).resolve().parents[1]
AUTHOR = ENTRY/'fixtures/second-author-20261022'


class SecondAuthorTests(unittest.TestCase):
    def test_all_ten_original_cases_and_author_files_remain_frozen(self):
        freeze = json.loads((AUTHOR/'FREEZE.json').read_text())
        for name, sha in freeze['files'].items():
            self.assertEqual(hashlib.sha256((AUTHOR/name).read_bytes()).hexdigest(), sha)
        raw = json.loads((AUTHOR/'CASES.json').read_text())['cases']
        cases = split_cases('second-author')
        self.assertEqual([c['id'] for c in cases], ['B%02d' % i for i in range(1, 11)])
        self.assertEqual([(c['id'], c['title'], c['text']) for c in cases],
                         [(c['id'], c['title'], c['text']) for c in raw])
        old = corpus('training')['cases']+corpus('heldout')['cases']+split_cases('hard')+dataset()['cases']
        self.assertFalse({c['id'] for c in cases} & {c['id'] for c in old})
        self.assertFalse(json.loads((AUTHOR/'NORMALIZATION.json').read_text())['labels_consulted_before_mapping'])

    def test_only_unchanged_bundled_cases_enter_the_provider_without_labels(self):
        for case in split_cases('second-author'):
            self.assertEqual(set(public_case(case)), {'id', 'title', 'text', 'evidence'})
            changed = deepcopy(case); changed['text'] += ' edited'
            with self.subTest(case=case['id']), self.assertRaises(ProviderError):
                public_case(changed)

    def test_actual_cli_posts_twenty_mock_requests_without_gold_or_kind(self):
        calls = []
        real_server = mock_server.mock_server

        @contextmanager
        def observed_server():
            with real_server() as (url, received):
                yield url, received
                calls.extend(received)

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(mock_server, 'mock_server', observed_server), redirect_stdout(io.StringIO()):
            output = Path(tmp)/'report.json'
            rc = live_eval.main(['--split', 'second-author', '--dry-run', '--no-thinking',
                                 '--reasoning-for', SUPER, '--max-calls', '20', '--max-usd', '0.25',
                                 '--output', str(output), '--cache', str(Path(tmp)/'cache')])
            self.assertIn(rc, (0, 1))  # Mock quality is not a required vendor-quality result.
            report = json.loads(output.read_text())
        self.assertTrue(report['complete'])
        self.assertEqual(report['split'], 'second-author')
        self.assertEqual(len(report['rows']), 20)
        self.assertEqual(len(calls), 20)
        self.assertEqual({r['model'] for r in calls}, {LIGHTNING, SUPER})
        for request in calls:
            context = json.loads(request['messages'][-1]['content'])
            self.assertEqual(set(context['incident']), {'id', 'title', 'text', 'evidence'})
            self.assertNotIn('author_disposition', context['incident'])
            if request['model'] == LIGHTNING:
                self.assertIs(request['chat_template_kwargs']['enable_thinking'], False)
            else:
                self.assertNotIn('chat_template_kwargs', request)  # Existing Super default path.
        self.assertIn('second AI author', report['note'])
