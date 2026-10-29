"""Judge-entry contracts; no credentials or vendor transport."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from signaldesk.budget import Budget
from signaldesk.core import case_by_id
from signaldesk.live import LiveProvider, checked_url
from signaldesk.live_eval import evaluate_models, parser
from signaldesk.mock_server import mock_draft
from test_live import response
import test_replay

ENTRY = test_replay.ENTRY


class JudgeRouteTests(unittest.TestCase):
    def test_default_live_request_targets_nvidia_nemotron_on_token_factory(self):
        args = parser().parse_args([])
        self.assertEqual(args.models, ['nvidia/Nemotron-3_5-Lightning',
                                      'nvidia/nemotron-3-super-120b-a12b'])
        self.assertFalse(args.dry_run or args.replay or args.tavily)
        url = 'https://api.tokenfactory.nebius.com/v1/chat/completions'
        self.assertEqual(checked_url(), (url, 'live-nebius'))
        for model in args.models:
            self.assertEqual(LiveProvider(model).url, url)
            self.assertEqual(LiveProvider(model).origin, 'live-nebius')
        calls = []
        def transport(destination, payload, token):
            calls.append((destination, payload['model']))
            self.assertEqual(token, 'local-fixture-only')
            return response(mock_draft(json.loads(payload['messages'][-1]['content'])))
        with tempfile.TemporaryDirectory() as tmp, \
                patch('signaldesk.live.credential', side_effect=AssertionError('credential read')), \
                patch('socket.socket', side_effect=AssertionError('network')):
            report = evaluate_models(args.models, [case_by_id('clean-demo')],
                                     Budget(), tmp, transport=transport)
        self.assertEqual(calls, [(url, m) for m in args.models])
        self.assertEqual(report['origins'], ['injected-mock'])
        self.assertTrue(report['complete'])
        self.assertEqual(report['budget']['calls_reserved'], 2)

    def test_judge_build_names_required_stack_and_mock_boundary(self):
        html = (ENTRY/'site/index.html').read_text()
        self.assertIn('NVIDIA Nemotron on Nebius Token Factory', html)
        self.assertIn('LOCAL MOCK PREVIEW', html)
        self.assertIn('Start 30-second walkthrough', html)
        self.assertIn("connect-src 'none'", html)


class ExportAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_replay.PublicPackageTests.setUpClass()
        cls.exporter = test_replay.PublicPackageTests.module

    def test_export_archive_has_no_extra_parent_cache_key_or_personal_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'entry'
            shutil.copytree(ENTRY, root, ignore=shutil.ignore_patterns('__pycache__', 'cache', 'runs', 'node_modules', '.scratch'))
            for name in ['state/private.md', 'cache/raw.json', 'docs/cache/raw.json',
                         '.env', 'signaldesk/.credentials.json', 'REPORT.md']:
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('SYNTHETIC ' + 'EXCLUSION CANARY')
            # Hidden credential files within public trees fail closed.
            with self.assertRaisesRegex(ValueError, 'Hidden file'):
                self.exporter.export(Path(tmp)/'blocked', root)
            (root/'signaldesk/.credentials.json').unlink()  # Own synthetic fixture only.
            manifest = self.exporter.export(Path(tmp)/'export', root)
            with tarfile.open(Path(tmp)/'export/signaldesk.tar.gz') as archive:
                self.assertEqual(set(archive.getnames()),
                                 {'signaldesk/'+name for name in manifest})
                for member in archive.getmembers():
                    self.assertTrue(member.isfile())
                    raw = archive.extractfile(member).read()
                    self.assertNotIn(b'SYNTHETIC ' + b'EXCLUSION CANARY', raw)
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),
                                     manifest[member.name.removeprefix('signaldesk/')])
            self.assertIn('site/_headers', manifest)
            self.assertIn('HOSTING.md', manifest)

    def test_export_refuses_synthetic_secret_and_personal_path_controls(self):
        filler = ''.join(chr(97 + i % 26) for i in range(30))  # synthetic, generated at runtime
        samples = ['api' + '_key = "' + filler + '"',
                   's' + 'k-' + filler,
                   '~/' + 'tmp/personal-note', '/' + 'root/private-note']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for sample in samples:
                (root/'README.md').write_text(sample)
                with self.subTest(kind=sample[:6]), self.assertRaisesRegex(
                        ValueError, 'Credential|Private path'):
                    self.exporter.public_files(root)
