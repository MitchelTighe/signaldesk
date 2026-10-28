"""Live path acceptance: production modules, fake transports and loopback HTTP only."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signaldesk.budget import Budget, GuardError, LIGHTNING, SUPER
from signaldesk.core import case_by_id, corpus
from signaldesk.grounding import PublicDocs, SOURCES, allowed_url, validate_docs
from signaldesk.live import LiveProvider, validate_draft, public_case, runbooks
from signaldesk.live_eval import evaluate_models, metrics, main
from signaldesk.mock_server import mock_draft, mock_server
from signaldesk.providers import ProviderError
from signaldesk.safeio import digest, pack, parse, post

CASE = case_by_id('clean-demo')
PUBLIC = public_case(CASE)


def draft(case=CASE):
    return mock_draft({'incident': public_case(case), 'runbooks': runbooks()})


def response(value=None, usage=None, finish='stop'):
    return {'choices': [{'finish_reason': finish, 'message': {'content': json.dumps(value if value is not None else draft())}}],
            'usage': usage or {'prompt_tokens': 500, 'completion_tokens': 500, 'total_tokens': 1000}}


class DraftTests(unittest.TestCase):
    def test_model_drafts_a_supported_hypothesis_and_ordered_subset_of_cited_steps(self):
        d = draft(); d['steps'] = list(reversed(d['steps']))[:2]
        r = validate_draft(d, PUBLIC)
        self.assertEqual(r['hypothesis'], 'Drive requests cleaning')
        self.assertEqual([s['step'] for s in r['steps']], [3, 2])
        self.assertEqual(r['actions_executed'], 0)
        self.assertEqual(r['evidence'], PUBLIC['evidence'])

    def test_unknown_abstention_contains_no_unvalidated_prose(self):
        c = case_by_id('unknown-demo'); r = validate_draft(draft(c), public_case(c))
        self.assertIsNone(r['hypothesis']); self.assertEqual(r['steps'], [])
        self.assertEqual(r['status'], 'needs-human')

    def test_forged_duplicate_cross_case_and_malformed_evidence_references(self):
        for ids in [['E-FAKE'], ['E-L1'], ['E-C1', 'E-C1'], [True], 'E-C1', {}]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                d = draft(); d['evidence_ids'] = ids; validate_draft(d, PUBLIC)

    def test_draft_schema_and_title_are_not_free_prose(self):
        changes = [{'runbook_id': []}, {'runbook_id': 'RB-FAKE'}, {'secret': 'unsafe'},
                   {'steps': 'unsafe'}, {'web_citations': [{}]},
                   {'hypothesis': 'Proven root cause: restart now'}, {'hypothesis': '</script><script>unsafe()</script>'}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                d = draft(); d.update(change); validate_draft(d, PUBLIC)
        for d in [None, [], True]:
            with self.assertRaises(ValueError): validate_draft(d, PUBLIC)

    def test_step_entailment_requires_exact_text_source_and_index(self):
        for change in [{'text': 'Restart everything'}, {'source': 'RB-HWFAULT'}, {'step': True},
                       {'step': 0}, {'step': 4}, {'unexpected': 'extra'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                d = draft(); d['steps'][0].update(change); validate_draft(d, PUBLIC)
        d = draft(); d['steps'][1] = deepcopy(d['steps'][0])
        with self.assertRaises(ValueError): validate_draft(d, PUBLIC)

    def test_abstention_cannot_smuggle_steps_claims_or_citations(self):
        for field, value in [('steps', draft()['steps']), ('hypothesis', 'Unknown root cause'),
                             ('evidence_ids', ['E-U1']), ('web_citations', ['WEB-FAKE'])]:
            c = case_by_id('unknown-demo'); d = draft(c); d[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): validate_draft(d, public_case(c))

    def test_two_abnormal_families_force_abstention_over_model_choice(self):
        c = deepcopy(PUBLIC); c['evidence'].append({'id': 'E-T1', 'metric': 'tapealert_hardware_flags', 'value': 90})
        r = validate_draft(draft(), c)
        self.assertEqual(r['validation'], 'telemetry-abstention'); self.assertFalse(r['steps'])
        self.assertIn('Multiple failure', r['reason'])

    def test_invalid_numeric_and_below_threshold_values_cannot_support_steps(self):
        for value in ['1', True, None, -1, 0.99, 0]:
            c = deepcopy(PUBLIC); c['evidence'][0]['value'] = value
            r = validate_draft(draft(), c)
            self.assertEqual(r['status'], 'needs-human'); self.assertFalse(r['steps'])
        for value in [float('inf'), float('nan')]:
            c = deepcopy(PUBLIC); c['evidence'][0]['value'] = value
            with self.assertRaises(ValueError): validate_draft(draft(), c)

    def test_noise_and_unretrieved_web_citations_are_rejected(self):
        c = deepcopy(PUBLIC); c['evidence'].append({'id': 'E-NOISE', 'metric': 'cpu_pct', 'value': 50})
        d = draft(); d['evidence_ids'].append('E-NOISE')
        with self.assertRaises(ValueError): validate_draft(d, c)
        d = draft(); d['web_citations'] = ['WEB-FAKE']
        with self.assertRaises(ValueError): validate_draft(d, PUBLIC)


class BudgetTests(unittest.TestCase):
    def test_call_cap_aborts_before_second_request(self):
        b = Budget(max_calls=1); b.reserve(LIGHTNING, 1000, 512)
        with self.assertRaisesRegex(GuardError, 'Call cap'): b.reserve(SUPER, 1000, 512)
        self.assertEqual(b.calls, 1)

    def test_run_token_cap_includes_input_and_max_output(self):
        b = Budget(max_tokens=1600); b.reserve(LIGHTNING, 1000, 512)
        with self.assertRaisesRegex(GuardError, 'Token cap'): b.reserve(LIGHTNING, 1, 256)
        self.assertEqual(b.reserved_tokens, 1512)

    def test_dollar_cap_is_checked_before_send(self):
        b = Budget(max_usd='.001')
        with self.assertRaisesRegex(GuardError, 'USD cap'): b.reserve(SUPER, 4000, 2048)
        self.assertEqual(b.calls, 0); self.assertEqual(b.reserved_usd, 0)

    def test_snapshot_rates_are_doubled_in_reservation_and_not_refunded(self):
        b = Budget(); reservation = b.reserve(SUPER, 1000, 1000)
        self.assertEqual(b.reserved_usd, Decimal('.0024'))
        b.observe(SUPER, {'prompt_tokens': 100, 'completion_tokens': 100, 'total_tokens': 200}, reservation)
        self.assertEqual(b.reserved_usd, Decimal('.0024'))
        self.assertEqual(b.observed_usd, Decimal('.00012'))

    def test_limits_cannot_be_disabled_or_nonfinite(self):
        for kw in [{'max_calls': 0}, {'max_calls': True}, {'max_calls': 101}, {'max_tokens': 0},
                   {'max_usd': '1.01'}, {'max_usd': 'NaN'}, {'max_usd': 'Infinity'}, {'max_usd': 'bad'},
                   {'max_usd': '0'}, {'multiplier': '1.99'}, {'multiplier': 'NaN'}]:
            with self.subTest(kw=kw), self.assertRaises(GuardError): Budget(**kw)

    def test_missing_bad_and_overrun_usage_stops_all_further_calls(self):
        usages = [None, {}, {'prompt_tokens': True, 'completion_tokens': 1, 'total_tokens': 2},
                  {'prompt_tokens': 1, 'completion_tokens': -1, 'total_tokens': 0},
                  {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 3},
                  {'prompt_tokens': 2000, 'completion_tokens': 1, 'total_tokens': 2001},
                  {'prompt_tokens': 1, 'completion_tokens': 2049, 'total_tokens': 2050}]
        for usage in usages:
            b = Budget(); reservation = b.reserve(SUPER, 1000, 2048)
            with self.subTest(usage=usage), self.assertRaises(GuardError): b.observe(SUPER, usage, reservation)
            self.assertEqual(b.calls, 1)


class TransportTests(unittest.TestCase):
    def test_valid_env_credential_is_used_only_as_header_with_mocked_http(self):
        fixture = 'fixture-key-for-env-test'
        with patch.dict(os.environ, {'NEBIUS_API_KEY': fixture}), patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = pack(response())
            result = LiveProvider(LIGHTNING).draft(CASE)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header('Authorization'), 'Bearer ' + fixture)
            self.assertNotIn(fixture, request.data.decode())
            self.assertNotIn(fixture, json.dumps(result))
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_legacy_live_selector_cannot_bypass_run_guard(self):
        from signaldesk.providers import NebiusProvider
        with patch('urllib.request.build_opener') as opener:
            with self.assertRaisesRegex(ProviderError, 'Legacy live selector retired'):
                NebiusProvider(LIGHTNING, 'fixture-only').select(CASE)
            opener.assert_not_called()

    def test_payload_excludes_labels_training_and_credentials(self):
        seen = []
        def fake(url, payload, token): seen.append(payload); return response()
        r = LiveProvider(LIGHTNING, transport=fake).draft(CASE)
        raw = json.dumps(seen)
        context = json.loads(seen[0]['messages'][-1]['content'])
        self.assertNotIn('expected', context['incident'])
        self.assertNotIn('training', context)
        self.assertTrue(all('training' not in r for r in context['runbooks']))
        self.assertNotIn('local-fixture-only', raw)
        self.assertEqual(seen[0]['max_tokens'], 1600)
        self.assertEqual(r['provenance']['origin'], 'injected-mock')

    def test_modified_arbitrary_and_training_cases_never_reach_transport(self):
        p = LiveProvider(LIGHTNING, transport=lambda *a: self.fail('network'))
        changed = deepcopy(CASE); changed['text'] = 'arbitrary input'
        for c in [changed, corpus('training')['cases'][0], {'id': 'anything'}]:
            with self.assertRaises(ProviderError): p.draft(c)

    def test_env_key_required_only_for_real_http(self):
        with patch.dict(os.environ, {'NEBIUS_API_KEY': ''}), patch('urllib.request.build_opener') as opener:
            with self.assertRaises(ProviderError): LiveProvider(LIGHTNING).draft(CASE)
            opener.assert_not_called()

    def test_unknown_model_and_nonloopback_mock_urls_are_rejected(self):
        with self.assertRaises(ProviderError): LiveProvider('nvidia/unknown')
        for url in ['http://localhost:1234/v1/chat/completions', 'https://example.invalid/v1/chat/completions',
                    'http://127.0.0.1.evil:1234/v1/chat/completions',
                    'http://user@127.0.0.1:1234/v1/chat/completions',
                    'http://127.0.0.1:1234/v1/chat/completions?bad=1']:
            with self.subTest(url=url), self.assertRaises(ProviderError): LiveProvider(LIGHTNING, mock_url=url)

    def test_malformed_unfinished_and_forged_drafts_are_visible_errors(self):
        bad = response(); bad['choices'][0]['message']['content'] = 'UNTRUSTED BODY'
        d = draft(); d['steps'][0]['text'] = 'UNTRUSTED BODY'
        for envelope in [bad, response(d), response(finish='length')]:
            p = LiveProvider(LIGHTNING, transport=lambda *a: envelope); r = p.draft(CASE)
            self.assertEqual(r['validation'], 'rejected-draft')
            self.assertNotIn('UNTRUSTED BODY', json.dumps(r)); self.assertEqual(p.budget.calls, 1)

    def test_failure_retains_reservation_and_has_no_retry(self):
        seen = []
        def bad(*args): seen.append(1); raise RuntimeError('UNTRUSTED BODY')
        p = LiveProvider(LIGHTNING, transport=bad)
        with self.assertRaisesRegex(ProviderError, 'Transport failed'): p.draft(CASE)
        self.assertEqual(seen, [1]); self.assertEqual(p.budget.calls, 1)
        with self.assertRaises(GuardError): LiveProvider(LIGHTNING, transport=lambda *a: {'usage': None}).draft(CASE)

    def test_duplicate_json_keys_nonfinite_and_oversized_json_rejected(self):
        for raw in ['{"x":1,"x":2}', '{"x":NaN}', 'x' * 131073]:
            with self.assertRaises(ValueError): parse(raw)

    def test_loopback_http_uses_fake_key_without_reading_real_env(self):
        with mock_server() as (url, calls), patch('signaldesk.live.credential', side_effect=AssertionError('key read')):
            p = LiveProvider(LIGHTNING, mock_url=url); r = p.draft(CASE)
        self.assertEqual(len(calls), 1); self.assertEqual(r['runbook_id'], 'RB-CLEAN')
        self.assertEqual(r['provenance']['origin'], 'local-mock')

    def test_http_error_body_never_echoed_and_no_proxies_redirects(self):
        from urllib.error import HTTPError
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('url', 401, 'UNTRUSTED BODY', {}, None)
            with self.assertRaisesRegex(ProviderError, 'Request failed') as error: post('https://example.invalid', {}, 'fixture-only')
            self.assertNotIn('UNTRUSTED BODY', str(error.exception))
        with patch('urllib.request.build_opener') as opener:
            stream = opener.return_value.open.return_value.__enter__.return_value; stream.read.return_value = b'{}'
            self.assertEqual(post('https://example.invalid', {}, 'fixture-only'), {})
            handlers = opener.call_args.args; self.assertEqual(handlers[0].proxies, {})
            self.assertIsNone(handlers[1].redirect_request(None, None, 302, 'move', {}, 'https://other.invalid'))
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 45)
            self.assertEqual(stream.read.call_args.args, (131073,))


class CacheTests(unittest.TestCase):
    def test_forced_multifault_reason_survives_cache_and_static_revalidation(self):
        case = next(c for c in corpus('heldout')['cases'] if c['id'] == 'H35')
        rb = next(r for r in runbooks() if r['id'] == 'RB-CLEAN')
        value = {'runbook_id': rb['id'], 'hypothesis': rb['title'],
                 'evidence_ids': [e['id'] for e in case['evidence'] if e['metric'] == rb['metric']],
                 'steps': [{'source': rb['id'], 'step': i+1, 'text': text} for i, text in enumerate(rb['steps'])],
                 'web_citations': []}
        with tempfile.TemporaryDirectory() as tmp:
            first = LiveProvider(LIGHTNING, cache_dir=tmp, transport=lambda *a: response(value)).draft(case)
            replay = LiveProvider(LIGHTNING, cache_dir=tmp, replay=True, transport=lambda *a: self.fail('network')).draft(case)
            self.assertIn('Multiple failure families', first['reason'])
            self.assertEqual(first['reason'], replay['reason'])
            report = evaluate_models([LIGHTNING], [case], Budget(), tmp, replay=True,
                                     transport=lambda *a: self.fail('network'))
            from signaldesk.replay import sanitize_report
            self.assertEqual(sanitize_report(report)['rows'][0]['brief']['reason'], first['reason'])

    def test_replay_needs_no_env_and_spends_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            r1 = LiveProvider(LIGHTNING, cache_dir=tmp, transport=lambda *a: response()).draft(CASE)
            self.assertEqual(next(Path(tmp).glob('*.json')).stat().st_mode & 0o777, 0o600)
            second = LiveProvider(LIGHTNING, cache_dir=tmp, replay=True, transport=lambda *a: self.fail('network'))
            r2 = second.draft(CASE)
            self.assertTrue(r2['provenance']['replayed']); self.assertEqual(second.budget.calls, 0)
            self.assertEqual(r1['steps'], r2['steps'])

    def test_replay_miss_never_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = LiveProvider(LIGHTNING, cache_dir=tmp, replay=True, transport=lambda *a: self.fail('network'))
            with self.assertRaisesRegex(ProviderError, 'cache miss'): p.draft(CASE)
            self.assertEqual(p.budget.calls, 0)

    def test_cache_is_partitioned_by_model_prompt_schema_and_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = lambda *a: response()
            LiveProvider(LIGHTNING, cache_dir=tmp, transport=fake).draft(CASE)
            with self.assertRaises(ProviderError): LiveProvider(SUPER, cache_dir=tmp, replay=True, transport=fake).draft(CASE)
            with self.assertRaises(ProviderError): LiveProvider(LIGHTNING, cache_dir=tmp, replay=True).draft(CASE)
            with patch('signaldesk.live.SYSTEM', 'new prompt'):
                with self.assertRaises(ProviderError): LiveProvider(LIGHTNING, cache_dir=tmp, replay=True, transport=fake).draft(CASE)

    def test_tampered_cache_fails_even_with_recomputed_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = lambda *a: response(); LiveProvider(LIGHTNING, cache_dir=tmp, transport=fake).draft(CASE)
            path = next(Path(tmp).glob('*.json')); cache = json.loads(path.read_text())
            cache['record']['result']['steps'][0]['text'] = 'UNTRUSTED BODY'
            cache['sha256'] = digest(cache['record']); path.write_bytes(pack(cache))
            with self.assertRaisesRegex(ProviderError, 'integrity or validation'):
                LiveProvider(LIGHTNING, cache_dir=tmp, replay=True, transport=fake).draft(CASE)

    def test_rejected_drafts_are_cached_without_raw_remote_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = draft(); d['hypothesis'] = 'UNTRUSTED BODY'
            LiveProvider(LIGHTNING, cache_dir=tmp, transport=lambda *a: response(d)).draft(CASE)
            self.assertNotIn('UNTRUSTED BODY', next(Path(tmp).glob('*.json')).read_text())
            r = LiveProvider(LIGHTNING, cache_dir=tmp, replay=True, transport=lambda *a: self.fail('network')).draft(CASE)
            self.assertEqual(r['validation'], 'rejected-draft')


class EvaluationTests(unittest.TestCase):
    def test_unknown_errors_do_not_become_correct_abstentions(self):
        rows = [{'expected': None, 'actual': None, 'outcome': 'error'},
                {'expected': None, 'actual': None, 'outcome': 'validated'},
                {'expected': 'RB-CLEAN', 'actual': 'RB-HWFAULT', 'outcome': 'validated'},
                {'expected': 'RB-HWFAULT', 'actual': None, 'outcome': 'not-run'}]
        m = metrics(rows)
        self.assertEqual(m['unknown_rejection_rate'], .5); self.assertEqual(m['precision'], 0)
        self.assertEqual(m['recall'], 0); self.assertEqual(m['errors'], 1)
        self.assertEqual(m['not_run'], 1); self.assertEqual(m['abstained'], 1)

    def test_guard_leaves_partial_report_and_full_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = evaluate_models([LIGHTNING, SUPER], corpus('heldout')['cases'], Budget(max_calls=1), tmp,
                                transport=lambda *a: response())
        self.assertFalse(r['complete']); self.assertEqual(len(r['rows']), 80)
        self.assertEqual(r['budget']['calls_reserved'], 1)
        self.assertEqual(sum(m['not_run'] for m in r['metrics'].values()), 78)
        self.assertFalse(r['quality_gates_passed'])

    def test_cli_80_local_http_requests_then_zero_cost_replay(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            args = ['--dry-run', '--output', tmp+'/report.json', '--cache', tmp+'/cache']
            self.assertEqual(main(args), 0)
            r = json.loads(Path(tmp+'/report.json').read_text())
            self.assertEqual(r['origins'], ['local-mock']); self.assertEqual(r['budget']['calls_reserved'], 80)
            self.assertEqual(r['metrics'][LIGHTNING]['total'], 40)
            self.assertEqual(main(args+['--replay']), 0)
            replay = json.loads(Path(tmp+'/report.json').read_text())
            self.assertEqual(replay['cache_hits'], 80); self.assertEqual(replay['budget']['calls_reserved'], 0)
            self.assertEqual(replay['budget']['usd_reserved_upper_estimate'], 0)
        self.assertIn('NOT VENDOR INFERENCE', out.getvalue())

    def test_cli_rejects_dry_run_search_duplicates_and_bad_caps(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            for args in [['--dry-run', '--tavily'], ['--max-usd', '1.1'],
                         ['--models', LIGHTNING, LIGHTNING], ['--max-output-tokens', '9000']]:
                self.assertEqual(main(args), 2)


class GroundingTests(unittest.TestCase):
    def test_disabled_grounding_never_reads_key_network_or_cache(self):
        with tempfile.TemporaryDirectory() as tmp, patch('signaldesk.grounding.credential', side_effect=AssertionError('key read')):
            p = PublicDocs(Budget(), tmp, transport=lambda *a: self.fail('network'))
            self.assertEqual(p.search('RB-CLEAN'), []); self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_fixed_public_queries_filter_urls_and_return_citable_cached_documents(self):
        seen = []
        def fake(url, payload, token):
            seen.append(payload)
            return {'usage': {'credits': 1}, 'results': [
                {'url': 'https://manpages.debian.org/bookworm/sg3-utils/sg_logs.8.en.html', 'content': 'Read public client connection documentation.'},
                {'url': 'http://127.0.0.1/private', 'content': 'bad'},
                {'url': 'https://manpages.debian.org.evil.invalid/bookworm/sg3-utils/', 'content': 'bad'}]}
        with tempfile.TemporaryDirectory() as tmp:
            b = Budget(); p = PublicDocs(b, tmp, enabled=True, transport=fake)
            docs = p.search('RB-CLEAN'); self.assertEqual(docs, p.search('RB-CLEAN'))
            self.assertEqual(len(docs), 1); self.assertEqual(b.calls, 1)
            self.assertEqual(seen[0]['query'], 'sg_logs TapeAlert log page cleaning flags')
            self.assertNotIn('incident', json.dumps(seen)); self.assertFalse(seen[0]['auto_parameters'])
            validate_docs(docs); d = draft(); d['web_citations'] = [docs[0]['id']]
            self.assertEqual(validate_draft(d, PUBLIC, docs)['public_docs'][0]['url'], docs[0]['url'])
            self.assertEqual(PublicDocs(Budget(), tmp, True, True, fake).search('RB-CLEAN'), docs)

    def test_allowlist_checks_protocol_credentials_port_domain_path_and_encoding(self):
        for url in ['https://manpages.debian.org/', 'https://manpages.debian.org:443/bookworm/sg3-utils/', 'https://user@manpages.debian.org/bookworm/sg3-utils/',
                    'https://manpages.debian.org/bookworm/sg3-utils/../private', 'https://manpages.debian.org/bookworm/sg3-utils/%2e%2e/private',
                    'https://manpages.debian.org/bookworm/sg3-utils/?q=secret', 'https://manpages.debian.org/bookworm/sg3-utils/#fragment',
                    'https://manpages.debian.org/bookworm/sg3-utils/\\other', 'javascript:alert(1)', 'https://manpages.debian.org.evil/bookworm/sg3-utils/']:
            self.assertFalse(allowed_url(url, 'RB-CLEAN'), url)
        self.assertTrue(allowed_url('https://manpages.debian.org/bookworm/sg3-utils/sg_logs.8.en.html', 'RB-CLEAN'))

    def test_unexpected_credits_stop_and_missing_key_does_not_spend(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = Budget(); p = PublicDocs(b, tmp, True, transport=lambda *a: {'usage': {'credits': 2}, 'results': []})
            with self.assertRaises(GuardError): p.search('RB-CLEAN')
            self.assertEqual(b.calls, 1)
            with patch.dict(os.environ, {'TAVILY_API_KEY': ''}):
                p = PublicDocs(Budget(), tmp, True)
                with self.assertRaises(ProviderError): p.search('RB-CLEAN')
                self.assertEqual(p.budget.calls, 0)

    def test_search_replay_miss_never_sends(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = PublicDocs(Budget(), tmp, True, True, lambda *a: self.fail('network'))
            with self.assertRaisesRegex(ProviderError, 'cache miss'): p.search('RB-CLEAN')

    def test_grounding_pipeline_uses_shared_budget_and_cited_docs_without_labels(self):
        seen = []
        def search(url, payload, token):
            seen.append(payload)
            return {'usage': {'credits': 1}, 'results': [
                {'url': 'https://manpages.debian.org/bookworm/sg3-utils/sg_logs.8.en.html', 'content': 'Read public connection documentation.'}]}
        def model(url, payload, token):
            context = json.loads(payload['messages'][-1]['content'])
            self.assertNotIn('expected', context['incident'])
            value = mock_draft(context)
            value['web_citations'] = [context['public_docs'][0]['id']]
            return response(value)
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate_models([LIGHTNING, SUPER], [CASE], Budget(max_calls=3), tmp,
                                     grounding=True, transport=model, search_transport=search)
        self.assertTrue(report['complete']); self.assertEqual(len(seen), 1)
        self.assertEqual(report['budget']['calls_reserved'], 3)
        self.assertEqual(report['budget']['search_calls'], 1)
        self.assertTrue(all(r['brief']['public_docs'] for r in report['rows']))

    def test_full_grounded_comparison_fits_88_calls_and_shared_dollar_ceiling(self):
        queries = []
        def search(url, payload, token):
            queries.append(payload['query'])
            _, host, prefix = next(v for v in SOURCES.values() if v[0] == payload['query'])
            return {'usage': {'credits': 1}, 'results': [
                {'url': 'https://' + host + prefix + 'fixture-topic-' + str(i),
                 'content': ' '.join(['synthetic-public-documentation'] * 20)} for i in range(3)]}
        def model(url, payload, token):
            context = json.loads(payload['messages'][-1]['content'])
            value = mock_draft(context)
            if value['runbook_id']:
                value['web_citations'] = [d['id'] for d in context['public_docs'] if d['family'] == value['runbook_id']]
            return response(value)
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate_models([LIGHTNING, SUPER], corpus('heldout')['cases'], Budget(max_calls=88), tmp,
                                     grounding=True, transport=model, search_transport=search)
        self.assertTrue(report['complete']); self.assertTrue(report['quality_gates_passed'])
        self.assertEqual(len(queries), 8)
        self.assertEqual(report['budget']['calls_reserved'], 88)
        self.assertEqual(report['budget']['tavily_credits_observed'], 8)
        self.assertLessEqual(report['budget']['usd_reserved_upper_estimate'], 1)
        self.assertLessEqual(report['budget']['tokens_reserved'], 1_500_000)

    def test_retrieved_document_cannot_cite_a_different_family(self):
        family, url = 'RB-HWFAULT', 'https://www.t10.org/lists/asc-num.htm'
        doc = {'id': 'WEB-' + digest({'family': family, 'url': url})[:16], 'family': family,
               'url': url, 'title': SOURCES[family][0], 'excerpt': '', 'origin': 'injected-mock',
               'retrieved_at': '2026-10-18T00:00:00+00:00'}
        validate_docs([doc])
        value = draft(); value['web_citations'] = [doc['id']]
        with self.assertRaisesRegex(ValueError, 'different runbook family'): validate_draft(value, PUBLIC, [doc])
