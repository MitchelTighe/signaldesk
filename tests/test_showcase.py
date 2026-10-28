"""Presentation coverage and isolation; mocks cannot become live evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signaldesk import demo_data
from signaldesk.budget import LIGHTNING, SUPER
from signaldesk.core import corpus, dataset
from signaldesk.demo import recorded_demo
from signaldesk.live import public_case
from signaldesk.providers import ProviderError
from signaldesk.replay import sanitize_report
from signaldesk.safeio import pack

ENTRY = Path(__file__).resolve().parents[1]


class ShowcaseTests(unittest.TestCase):
    def test_generator_is_deterministic_without_clock_credentials_or_transport(self):
        with patch('socket.socket', side_effect=AssertionError('network')), \
             patch('signaldesk.live.credential', side_effect=AssertionError('credential')):
            self.assertEqual(pack(demo_data.generate_report()), pack(demo_data.generate_report()))
        self.assertEqual(demo_data.fixture_cases()[:40], corpus('heldout')['cases'])
        self.assertEqual(len(demo_data.fixture_cases()), 58)

    def test_every_walkthrough_step_resolves_for_both_models(self):
        data = sanitize_report(demo_data.generate_report())
        rows = {(r['model'], r['case_id']): r for r in data['rows']}
        for step in demo_data.walkthrough()['steps']:
            for model in (LIGHTNING, SUPER):
                with self.subTest(step=step['id'], model=model):
                    row = rows[model, step['case_id']]
                    self.assertEqual(row['outcome'], step['outcome'])
                    self.assertEqual(row['brief']['status'], step['status'])
                    self.assertEqual(row['brief']['actions_executed'], 0)
                    if step['status'] == 'needs-human':
                        self.assertEqual(row['brief']['steps'], [])

    def test_all_eight_families_have_supported_presentation_cases(self):
        rows = sanitize_report(demo_data.generate_report())['rows']
        ids = {r['actual'] for r in rows if r['case_id'].startswith('D') and r['actual']}
        self.assertEqual(ids, {b['id'] for b in dataset()['runbooks']})

    def test_presentation_cases_cannot_enter_live_provider(self):
        for case in demo_data.fixture_cases()[40:]:
            with self.subTest(case=case['id']), self.assertRaises(ProviderError):
                public_case(case)

    def test_showcase_cannot_be_promoted_to_live(self):
        report = demo_data.generate_report()
        with self.assertRaises(ValueError):
            sanitize_report(report, require_live=True)
        report['rows'][0]['brief']['provenance']['origin'] = 'live-nebius'
        with self.assertRaisesRegex(ValueError, 'mock provenance'):
            sanitize_report(report)

    def test_errors_and_not_run_are_not_correct_abstentions(self):
        data = sanitize_report(demo_data.generate_report())
        for model in data['models']:
            m = data['metrics'][model]
            self.assertEqual(m['total'], 58)
            self.assertEqual(m['errors'], 2)
            self.assertEqual(m['not_run'], 1)
            self.assertEqual(m['correct'], 55)

    def test_saved_showcase_revalidates_and_unavailable_rows_cannot_gain_steps(self):
        result = recorded_demo()
        self.assertEqual(len(result['briefs']), 3)
        report = demo_data.generate_report()
        report['rows'] = sanitize_report(report)['rows']
        self.assertEqual(len(sanitize_report(report)['rows']), 116)
        row = next(r for r in report['rows'] if r['case_id'] == 'D16')
        row['brief']['steps'] = [{'source': 'RB-CLEAN', 'step': 1, 'text': 'invented'}]
        with self.assertRaises(ValueError):
            sanitize_report(report)

    def test_presentation_input_or_membership_drift_is_rejected(self):
        report = demo_data.generate_report()
        report['rows'][-1]['case']['title'] = 'Changed'
        with self.assertRaises(ValueError):
            sanitize_report(report)
        report = demo_data.generate_report()
        report['rows'].pop()
        with self.assertRaises(ValueError):
            sanitize_report(report)

    def test_export_rejects_private_identifiers_in_new_files(self):
        spec = importlib.util.spec_from_file_location('exporter', ENTRY/'scripts/package_public.py')
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        import hashlib
        synthetic = 'syntheticreviewer'
        # Test the policy mechanism without redistributing private identities.
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                exporter, 'IDENTITY_DIGESTS', {hashlib.sha256(synthetic.encode()).hexdigest()}):
            root = Path(tmp)
            for text in (synthetic, synthetic.upper(), 'Hello, '+synthetic+'!'):
                (root/'README.md').write_text(text)
                with self.assertRaisesRegex(ValueError, 'Private identifier'):
                    exporter.public_files(root)

    def test_checked_in_fixture_and_walkthrough_match_generator(self):
        self.assertEqual(json.loads((ENTRY/'fixtures/showcase.json').read_text()), demo_data.fixture_cases())
        self.assertEqual(json.loads((ENTRY/'fixtures/walkthrough.json').read_text()), demo_data.walkthrough())

    def test_bundle_budget_rejects_unbounded_growth(self):
        import sys
        with patch.object(sys, 'path', [str(ENTRY/'scripts')]+sys.path):
            import artifact_check
        self.assertTrue(artifact_check.bundle_budget(ENTRY)['passed'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'site').mkdir()
            (root/'site/index.html').write_text('x'*300_001)
            with self.assertRaisesRegex(ValueError, 'size budget'):
                artifact_check.bundle_budget(root)
