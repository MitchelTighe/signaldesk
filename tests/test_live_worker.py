"""Cross-language validator parity and the static deployment opt-in boundary."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from signaldesk.core import corpus, dataset
from signaldesk.live import DraftRejection, runbooks, validate_draft
from signaldesk.telemetry import split_cases

ENTRY = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('configure_live', ENTRY / 'scripts/configure_live.py')
configure_live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure_live)


class LiveWorkerTests(unittest.TestCase):
    def test_js_validator_matches_python_on_all_bundled_cases_and_runbook_proposals(self):
        cases = (dataset()['cases'] + corpus('heldout')['cases'] + split_cases('hard')
                 + split_cases('second-author'))
        vectors, expected = [], []
        for case in cases:
            for book in runbooks():
                draft = {'runbook_id': book['id'], 'hypothesis': book['title'],
                         'evidence_ids': [e['id'] for e in case['evidence']],
                         'steps': [{'source': book['id'], 'step': 1, 'text': book['steps'][0]}],
                         'web_citations': []}
                try:
                    result = validate_draft(draft, case)
                    verdict = 'veto' if result['validation'] == 'telemetry-abstention' else 'accept'
                except (DraftRejection, ValueError):
                    verdict = 'veto'
                vectors.append({'draft': draft, 'case': case})
                expected.append(verdict)
        program = """import {readFileSync} from 'node:fs';
import {validateDraft} from './worker/cascade.mjs';
const vectors=JSON.parse(readFileSync(0,'utf8'));
console.log(JSON.stringify(vectors.map(v=>validateDraft(v.draft,v.case).verdict)));"""
        result = subprocess.run(['node', '--input-type=module', '-e', program], cwd=ENTRY,
                                input=json.dumps(vectors), text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), expected)
        self.assertGreater(len(vectors), 400)

    def test_endpoint_validation_accepts_one_https_origin_only(self):
        self.assertEqual(configure_live.endpoint_origin('https://signaldesk.example/api/live'),
                         'https://signaldesk.example')
        for endpoint in ['http://signaldesk.example/api/live', 'https://user@signaldesk.example/api/live',
                         'https://signaldesk.example/api/live?q=x', 'https://signaldesk.example:444/api/live',
                         'https://signaldesk.example/api/live#fragment', 'https://signaldesk.example/other',
                         "https://bad.example/'unsafe-inline'/api/live"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                configure_live.endpoint_origin(endpoint)

    def test_live_configuration_changes_only_html_and_policy_not_recorded_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for name in ['index.html', '_headers', 'manifest.json', 'replay.json']:
                (target / name).write_bytes((ENTRY / 'site' / name).read_bytes())
            before = (target / 'replay.json').read_bytes()
            configure_live.configure(target, 'https://signaldesk.example/api/live')
            html = (target / 'index.html').read_text()
            self.assertIn('connect-src https://signaldesk.example;', html)
            self.assertIn('content="https://signaldesk.example/api/live"', html)
            self.assertIn('connect-src https://signaldesk.example;', (target / '_headers').read_text())
            self.assertEqual(before, (target / 'replay.json').read_bytes())
            configure_live.configure(target)
            self.assertEqual((target / 'index.html').read_bytes(), (ENTRY / 'site/index.html').read_bytes())
            self.assertEqual(before, (target / 'replay.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
