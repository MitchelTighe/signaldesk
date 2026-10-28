"""Bundled synthetic image only. Fake transport never claims to read pixels."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from signaldesk.budget import Budget, VISION, LIGHTNING, GuardError
from signaldesk.live import LiveProvider
from signaldesk.mock_server import mock_server
from signaldesk.providers import ProviderError
from signaldesk.vision import screenshot, vision_draft, main
from test_live import response


class VisionTests(unittest.TestCase):
    def test_bundled_screenshot_is_hash_pinned_png(self):
        image, fingerprint = screenshot()
        self.assertTrue(image.startswith('data:image/png;base64,'))
        raw = base64.b64decode(image.split(',')[1])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), fingerprint)
        self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')

    def test_altered_screenshot_fails_before_request_or_key_lookup(self):
        with patch('signaldesk.vision.parse', return_value={'case_id':'clean-demo','sha256':'changed'}), \
             patch('signaldesk.live.credential', side_effect=AssertionError('key read')):
            p = LiveProvider(VISION, transport=lambda *a:self.fail('network'))
            with self.assertRaises(ProviderError): vision_draft(p)
            self.assertEqual(p.budget.calls, 0)

    def test_multimodal_payload_omits_numeric_evidence_and_reserves_image_tokens(self):
        seen = []
        def fake(url, payload, token): seen.append(payload); return response()
        p = LiveProvider(VISION, transport=fake)
        r = vision_draft(p)
        content = seen[0]['messages'][-1]['content']
        context = json.loads(content[0]['text'])
        self.assertEqual(content[1]['type'], 'image_url')
        self.assertTrue(content[1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertTrue(all('value' not in e for e in context['incident']['evidence']))
        self.assertNotIn('expected', context['incident'])
        self.assertGreater(p.budget.reserved_tokens, 32768)
        self.assertEqual(r['provenance']['input_kind'], 'bundled-dashboard-screenshot')
        self.assertEqual(r['provenance']['origin'], 'injected-mock')

    def test_text_only_model_cannot_run_vision_route(self):
        with self.assertRaises(ProviderError): vision_draft(LiveProvider(LIGHTNING))

    def test_image_budget_aborts_before_transport(self):
        p = LiveProvider(VISION, budget=Budget(max_tokens=1000), transport=lambda *a:self.fail('network'))
        with self.assertRaises(GuardError): vision_draft(p)
        self.assertEqual(p.budget.calls, 0)

    def test_vision_loopback_and_cache_replay_spend_no_second_call(self):
        with tempfile.TemporaryDirectory() as tmp, mock_server() as (url, calls):
            r = vision_draft(LiveProvider(VISION, cache_dir=tmp, mock_url=url))
            replay = LiveProvider(VISION, cache_dir=tmp, mock_url=url, replay=True)
            second = vision_draft(replay)
            self.assertEqual(len(calls), 1)
            self.assertEqual(r['steps'], second['steps'])
            self.assertEqual(replay.budget.calls, 0)
            self.assertTrue(second['provenance']['replayed'])

    def test_cli_replay_miss_writes_an_honest_partial_report(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            output = Path(tmp)/'vision.json'
            self.assertEqual(main(['--dry-run', '--replay', '--cache', tmp+'/cache', '--output', str(output)]), 2)
            report = json.loads(output.read_text())
            self.assertFalse(report['complete'])
            self.assertFalse(report['quality_gates_passed'])
            self.assertEqual(report['budget']['calls_reserved'], 0)
            self.assertEqual(report['metrics'][VISION]['errors'], 1)
