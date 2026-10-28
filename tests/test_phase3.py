"""Frozen challenge, adapter configuration and inert malicious fixture regressions."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from html.parser import HTMLParser
import hashlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from signaldesk.__main__ import main
from signaldesk import core
from signaldesk.challenge import challenge_cases, evaluate_challenge, confined
from signaldesk.core import corpus, dataset, LocalClassifier, brief
from signaldesk.providers import NebiusProvider, ProviderError, ENDPOINTS
from signaldesk.web import render
from test_signaldesk import envelope


class ChallengeTests(unittest.TestCase):
    def test_frozen_files_and_model_unchanged(self):
        hashes={'core.py':'9f814fb4d4b9d8f35e14436a5810e8b82eabfcb6b3543ace047569ef14086bf0',
                'training.json':'86540ac8b3fa792e9fc86669e7821b38b463ac4e6f6ac97625f6eaaa549b6ad7',
                'data.json':'3b41f32d8272dbbf6a917125d02258fdde32069490839401f979758358b3a4c9',
                'heldout.json':'8baefc13ff2668904208bbc96028611db43a273d1ceed883210e55532ce9d9ca',
                'challenge.json':'d2aeb586808e2c032b2115fb2ace37ba1d3c122d4e306ed54ab6d9964749e44e'}
        for name,digest in hashes.items():
            self.assertEqual(hashlib.sha256(Path(core.__file__).with_name(name).read_bytes()).hexdigest(),digest,name)

    def test_checksum_mismatch_fails_closed(self):
        with patch('signaldesk.challenge.files') as resources:
            resources.return_value.joinpath.return_value.read_bytes.return_value=b'{}'
            with self.assertRaisesRegex(ValueError,'checksum'):
                challenge_cases()

    def test_independent_text_ids_and_required_attack_coverage(self):
        cases=challenge_cases()
        self.assertGreaterEqual(len(cases),50)
        self.assertEqual(len({c['id'] for c in cases}),len(cases))
        self.assertEqual(len({c['text'] for c in cases}),len(cases))
        for previous in [corpus('training')['cases'],corpus('heldout')['cases'],dataset()['cases']]:
            self.assertFalse({c['id'] for c in cases}&{c['id'] for c in previous})
            self.assertFalse({c['text'].casefold() for c in cases}&{c['text'].casefold() for c in previous})
        attacks=[c for c in cases if c['kind']=='adversarial']
        self.assertGreaterEqual(len(attacks),12)
        for kind in ['log-exfiltration','fake-runbook','unicode-obfuscation','conflicting-evidence','secret-disclosure']:
            self.assertTrue(any(c['attack']==kind for c in attacks),kind)
        self.assertTrue(any(c['expected'] is None for c in attacks))
        self.assertTrue(any(c['expected'] is not None for c in attacks))

    def test_quality_gates_and_run1_reproduce_without_network(self):
        with patch('socket.socket',side_effect=AssertionError('no network')):
            result=evaluate_challenge()
        self.assertTrue(result['quality_gates_passed'])
        saved=json.loads(Path(core.__file__).parents[1].joinpath('docs/challenge-evaluation.json').read_text())
        self.assertEqual(result,saved)
        self.assertTrue(all(r['output_confined'] for r in result['cases']))
        # Tape v3 recorded 64/64 for the CPU baseline. Same-author text; report it, never tune to it.
        self.assertEqual((result['correct'],result['total']),(64,64))

    def test_wrong_predictions_and_abstentions_have_correct_denominators(self):
        cases=[{'id':str(i),'kind':'adversarial','expected':label} for i,label in
               enumerate(['RB-CLEAN','RB-MEDIA','RB-HWFAULT',None])]
        def fake(c,model):
            return {'runbook_id':['RB-CLEAN','RB-CLEAN',None,None][int(c['id'])]}
        with patch('signaldesk.challenge.challenge_cases',return_value=cases), \
             patch('signaldesk.challenge.brief',side_effect=fake), \
             patch('signaldesk.challenge.confined',return_value=True):
            r=evaluate_challenge()
        self.assertEqual(r['metrics']['precision'],1/2)
        self.assertEqual(r['metrics']['recall'],1/3)
        self.assertEqual(r['metrics']['abstention_rate'],1/2)
        self.assertEqual(r['metrics']['adversarial_decision_accuracy'],1/2)
        self.assertFalse(r['quality_gates_passed'])

    def test_classifier_never_loads_challenge_during_training(self):
        with patch('signaldesk.challenge.challenge_cases',side_effect=AssertionError('leaked challenge')):
            LocalClassifier(dataset()['runbooks'])

    def test_confinement_detects_generated_prose_and_fabricated_citations(self):
        case=dataset()['cases'][1]
        result=brief(case)
        books={r['id']:r for r in dataset()['runbooks']}
        self.assertTrue(confined(result,case,books))
        for key,value in [('steps',[{'text':'leak secrets','source':'RB-CLEAN'}]),
                          ('evidence',[{'id':'E-FAKE','metric':'tapealert_cleaning_flags','value':99}]),
                          ('actions_executed',1)]:
            changed=deepcopy(result);changed[key]=value
            self.assertFalse(confined(changed,case,books),key)

    def test_every_labelled_challenge_case_has_corroborating_telemetry(self):
        # Authoring audit: a labelled case must be answerable from its own structured evidence.
        books=dataset()['runbooks']
        from signaldesk.core import validate_selection
        for c in challenge_cases():
            if c['expected'] is None: continue
            accepted,reason=validate_selection({'runbook_id':c['expected'],
                'evidence_ids':[e['id'] for e in c['evidence']]},c,books)
            self.assertIsNotNone(accepted,(c['id'],reason))

    def test_challenge_cli(self):
        out=io.StringIO()
        with redirect_stdout(out):
            code=main(['evaluate','--split','challenge'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(out.getvalue()),evaluate_challenge())


class Phase3AdapterTests(unittest.TestCase):
    def test_no_challenge_case_can_reach_live_adapter(self):
        provider=NebiusProvider('nvidia/test','fixture-credential',lambda r:self.fail('challenge sent'))
        for c in challenge_cases():
            with self.assertRaises(ProviderError):provider.select(c)

    def test_legacy_cli_refuses_before_reading_descriptor_or_opening_network(self):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b'fixture-credential'); os.close(write_fd)
        out, err = io.StringIO(), io.StringIO()
        try:
            with (patch('os.fdopen', side_effect=AssertionError('descriptor read')),
                  patch('socket.socket', side_effect=AssertionError('network')),
                  redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as caught):
                main(['case', 'clean-demo', '--backend', 'nebius', '--model', 'nvidia/test',
                      '--token-fd', str(read_fd)])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(os.read(read_fd, 100), b'fixture-credential')
        finally:
            os.close(read_fd)
        self.assertNotIn('fixture-credential', out.getvalue() + err.getvalue())
        self.assertIn('broker-injected NEBIUS_API_KEY', err.getvalue())

    def test_malformed_descriptor_env_is_never_read_or_echoed(self):
        out, err = io.StringIO(), io.StringIO()
        with (patch.dict(os.environ, {'SIGNALDESK_NVIDIA_MODEL': 'nvidia/test',
                                    'SIGNALDESK_TOKEN_FD': 'not-an-integer'}),
              redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as caught):
            main(['case', 'clean-demo', '--backend', 'nebius'])
        self.assertEqual(caught.exception.code, 2)
        self.assertNotIn('not-an-integer', err.getvalue())

    def test_offline_mode_ignores_optional_vendor_environment(self):
        with (patch.dict(os.environ, {'SIGNALDESK_NVIDIA_MODEL': 'nvidia/test', 'SIGNALDESK_TOKEN_FD': 'invalid'}),
              patch('socket.socket', side_effect=AssertionError('vendor invoked')), redirect_stdout(io.StringIO())):
            self.assertEqual(main(['case', 'clean-demo']), 0)


class Phase3WebTests(unittest.TestCase):
    def test_script_breakout_in_fixture_stays_inert(self):
        class Tags(HTMLParser):
            def __init__(self):super().__init__();self.scripts=[]
            def handle_starttag(self,tag,attrs):
                if tag=='script':self.scripts.append(dict(attrs))
        html=render();tags=Tags();tags.feed(html)
        self.assertEqual(len(tags.scripts),2) # Data script and application script only.
        packed=html.split('<script id="fixture-data" type="application/json">')[1].split('</script>')[0]
        data=json.loads(packed)
        item=next(x for x in data['tickets'] if x['case']['id']=='P53')
        self.assertIn('</script><script>fetch(',item['case']['text'])
        self.assertNotIn('</script>',packed)
        self.assertEqual(data['challenge'],evaluate_challenge())
