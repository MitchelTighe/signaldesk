"""Static packaging and independent replay-validation regressions."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from signaldesk.budget import Budget, LIGHTNING
from signaldesk.core import corpus
from signaldesk.live_eval import evaluate_models
from signaldesk.mock_server import mock_draft
from signaldesk.replay import build, sanitize_report
from test_live import response

ENTRY = Path(__file__).parents[1]


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def fake(url, payload, token):
            context = json.loads(payload['messages'][-1]['content'])
            return response(mock_draft(context))
        with tempfile.TemporaryDirectory() as tmp:
            cls.report = evaluate_models([LIGHTNING], corpus('heldout')['cases'], Budget(), tmp, transport=fake)

    def test_build_from_report_revalidates_and_recomputes_metrics(self):
        report = deepcopy(self.report); report['metrics'] = {'fabricated': 'UNTRUSTED BODY'}
        with tempfile.TemporaryDirectory() as tmp, patch('socket.socket', side_effect=AssertionError('network')):
            output = Path(tmp)/'site'
            previous_umask = os.umask(0o077)
            try:
                data = build(report, output)
            finally:
                os.umask(previous_umask)
            self.assertEqual(output.stat().st_mode & 0o777, 0o755)
            self.assertEqual(data['metrics'][LIGHTNING]['total'], 40)
            self.assertEqual(data['origins'], ['injected-mock'])
            html = (output/'index.html').read_text()
            self.assertIn('LOCAL MOCK PREVIEW', html)
            self.assertNotIn('UNTRUSTED BODY', html)
            self.assertNotIn('__REPLAY_DATA__', html)
            self.assertTrue((output/'manifest.json').exists())
            for name in ['index.html', 'replay.json', 'manifest.json']:
                self.assertEqual((output/name).stat().st_mode & 0o777, 0o644)

    def test_mock_data_can_never_pass_require_live(self):
        with self.assertRaises(ValueError): sanitize_report(self.report, require_live=True)

    def test_tampered_prose_citations_labels_or_case_are_rejected(self):
        for field, value in [('hypothesis', 'UNTRUSTED BODY'), ('actions_executed', 1),
                             ('evidence', [{'id': 'E-FAKE', 'metric': 'tapealert_cleaning_flags', 'value': 99}])]:
            r = deepcopy(self.report); r['rows'][0]['brief'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): sanitize_report(r)
        r = deepcopy(self.report); r['rows'][0]['expected'] = 'RB-FAKE'
        with self.assertRaises(ValueError): sanitize_report(r)
        r = deepcopy(self.report); r['rows'][0]['case']['text'] = 'arbitrary input'
        with self.assertRaises(ValueError): sanitize_report(r)

    def test_duplicate_missing_and_changed_dataset_rows_are_rejected(self):
        for change in [lambda r:r['rows'].append(r['rows'][0]), lambda r:r['rows'].pop(),
                       lambda r:r.update(dataset_sha256='changed')]:
            r = deepcopy(self.report); change(r)
            with self.assertRaises(ValueError): sanitize_report(r)

    def test_original_report_data_is_not_mutated(self):
        before = deepcopy(self.report); sanitize_report(self.report)
        self.assertEqual(before, self.report)

    def test_recorded_boolean_reasoning_survives_replay_without_mutating_report(self):
        for thinking in (False, True):
            with self.subTest(thinking=thinking):
                report = deepcopy(self.report)
                report['rows'][0]['brief']['provenance']['thinking'] = thinking
                before = deepcopy(report)
                replay = sanitize_report(report)
                self.assertIs(replay['rows'][0]['brief']['provenance'].get('thinking'), thinking)
                self.assertEqual(report, before)

    def test_unknown_or_nonboolean_reasoning_is_omitted_without_mutating_report(self):
        variants = [('missing',), ('null', None), ('zero', 0), ('one', 1),
                    ('string-false', 'false'), ('string-true', 'true'),
                    ('empty-string', ''), ('list', []), ('object', {'enabled': True})]
        for variant in variants:
            with self.subTest(thinking=variant[0]):
                report = deepcopy(self.report)
                provenance = report['rows'][0]['brief']['provenance']
                provenance.pop('thinking', None)
                if len(variant) == 2:
                    provenance['thinking'] = variant[1]
                before = deepcopy(report)
                replay = sanitize_report(report)
                self.assertNotIn('thinking', replay['rows'][0]['brief']['provenance'])
                self.assertEqual(report, before)

    def test_payload_cannot_close_inert_script(self):
        from signaldesk.safeio import pack
        self.assertNotIn('</script>', pack({'text': '</script>'}).decode().replace('<', '\\u003c'))
        template = (ENTRY/'web/replay-template.html').read_text()
        self.assertIn('connect-src \'none\'', template)
        self.assertNotIn('innerHTML', template)
        self.assertIn('if(!endpoint){replayMessage(', template)
        self.assertIn('name="signaldesk-live-endpoint" content=""', template)
        self.assertNotIn('localStorage', template)


class PublicPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('package_public', ENTRY/'scripts/package_public.py')
        cls.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.module)

    def test_package_is_allowlisted_and_contains_no_runtime_cache_or_parent_repo(self):
        files = self.module.public_files()
        names = [n for n, _ in files]
        self.assertIn('LICENSE', names); self.assertIn('README.md', names)
        self.assertIn('site/index.html', names)
        for required in ['DEPLOY.md', 'worker/index.mjs', 'worker/package.json', 'worker/package-lock.json']:
            self.assertIn(required, names)
        for name in names:
            self.assertFalse(any(p in name.split('/') for p in ['.git', 'cache', 'runs', 'state']))
        self.assertNotIn('REPORT.md', names)

    def test_archive_manifest_matches_bytes_and_export_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.module.export(Path(tmp)/'one'); second = self.module.export(Path(tmp)/'two')
            self.assertEqual(first, second)
            self.assertEqual(Path(tmp, 'one/signaldesk.tar.gz').read_bytes(), Path(tmp, 'two/signaldesk.tar.gz').read_bytes())
            with tarfile.open(Path(tmp, 'one/signaldesk.tar.gz')) as archive:
                self.assertTrue(all(n.startswith('signaldesk/') and '..' not in n for n in archive.getnames()))
                self.assertEqual(len(archive.getnames()), len(first))
            with self.assertRaises(FileExistsError): self.module.export(Path(tmp)/'one')

    def test_symlink_source_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'signaldesk').mkdir()
            (root/'signaldesk/link.py').symlink_to('/dev/null')
            with self.assertRaisesRegex(ValueError, 'Symlink'): self.module.public_files(root)

    def test_private_unix_and_windows_paths_cannot_enter_public_text(self):
        examples = ['/' + 'home/fictional/work', '/' + 'mnt/fictional/work',
                    '/' + 'Users/fictional/work', 'C:' + '\\' + 'Users' + '\\fictional\\work',
                    '/' + 'run/user/1234/session']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for sample in examples:
                (root/'README.md').write_text(sample)
                with self.subTest(path_kind=sample.split('fictional')[0]), self.assertRaisesRegex(ValueError, 'Private path'):
                    self.module.public_files(root)

    def test_checked_in_site_matches_its_template_data_and_manifest(self):
        from signaldesk.safeio import pack
        import hashlib
        data = json.loads((ENTRY/'site/replay.json').read_text())
        template = (ENTRY/'web/replay-template.html').read_text()
        html = template.replace('__REPLAY_DATA__', pack(data).decode().replace('<', '\\u003c'))
        self.assertEqual(html, (ENTRY/'site/index.html').read_text())
        manifest = json.loads((ENTRY/'site/manifest.json').read_text())
        for name, fingerprint in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ENTRY/'site'/name).read_bytes()).hexdigest(), fingerprint)
