"""Credential-free recorded demo, with explicit opt-in guarded live rehearsal."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from .budget import Budget, GuardError, LIGHTNING
from .core import corpus
from .live import LiveProvider
from .providers import ProviderError
from .replay import sanitize_report
from .safeio import parse

ENTRY = Path(__file__).resolve().parents[1]
CASES = ('H05', 'H35', 'H36')
ROUTED_TOUR = ('H05', 'X06', 'X02', 'H35', 'X01')


def recorded_demo(site=None):
    """Revalidate recorded rows against bundled fixtures and exact authored sources.

    Hashes detect accidental corruption, not authenticity of a vendor response.
    No credential lookup, network call or mutable user cache is involved.
    """
    site = Path(site) if site is not None else ENTRY / 'site'
    manifest = parse((site / 'manifest.json').read_bytes())
    raw = (site / 'replay.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['files']['replay.json']:
        raise ValueError('Recorded demo integrity mismatch')
    data = parse(raw, max_bytes=2_000_000)
    if data.get('schema') != 'signaldesk-static-replay-v1':
        raise ValueError('Unknown recorded demo schema')
    report = {'schema': 'signaldesk-live-eval-v1', 'synthetic_only': True,
              'split': data.get('split', 'heldout'), 'complete': True, 'models': data['models'],
              'dataset_sha256': data['dataset_sha256'], 'rows': data['rows']}
    checked = sanitize_report(report)
    rows = [r for r in checked['rows'] if r['model'] == LIGHTNING and r['case_id'] in CASES]
    if len(rows) != len(CASES):
        raise ValueError('Required recorded demo cases absent')
    routed = []
    for case_id in ROUTED_TOUR if checked.get('routing') else ():
        route = next((c for c in checked['routing']['cases'] if c['case_id'] == case_id), None)
        if route is None:
            continue
        mine = {r['model']: r for r in checked['rows'] if r['case_id'] == case_id}
        vetoes = ['%s proposed %s; vetoed: %s' % (m.split('/')[1], r['brief']['model_proposal']['runbook_id'],
                                                 r['brief']['reason'])
                  for m, r in sorted(mine.items()) if r['brief'].get('model_proposal')]
        chosen = None if route['path'] == 'pre-triage' else mine[
            LIGHTNING if route['path'] == 'lightning' else next(m for m in mine if m != LIGHTNING)]
        routed.append({'case_id': case_id, 'title': mine[LIGHTNING]['case']['title'],
                       'telemetry': route['telemetry'], 'path': route['path'], 'reason': route['reason'],
                       'usd': route['usd'], 'latency_ms': route['latency_ms'], 'vetoes': vetoes,
                       'brief': chosen['brief'] if chosen else None})
    return {'mode': 'recorded', 'synthetic_only': True,
            'notice': ('RECORDED NEBIUS RESPONSES — no new inference' if checked['live_recorded']
                       else 'LOCAL MOCK RECORDING — NOT NVIDIA INFERENCE; qualifying runtime pending'),
            'fallback_reason': None, 'calls_reserved_this_run': 0,
            'budget': None, 'briefs': [r['brief'] for r in rows], 'routed': routed}


def run_demo(live=False, site=None, provider_factory=LiveProvider):
    # Validate the fallback before attempting a request. Never overwrite the recording.
    recorded = recorded_demo(site)
    if not live:
        return recorded
    budget = Budget(max_calls=3, max_tokens=100_000, max_usd='0.05')
    cases = {c['id']: c for c in corpus('heldout')['cases']}
    try:
        provider = provider_factory(LIGHTNING, budget=budget)
        briefs = [provider.draft(cases[i]) for i in CASES]
    except (ProviderError, GuardError):
        # No exception text: transport errors may contain sensitive remote content.
        recorded.update(fallback_reason='Live access unavailable or stopped by a budget guard; recorded responses shown',
                        calls_reserved_this_run=budget.calls, budget=budget.summary())
        return recorded
    return {'mode': 'live', 'synthetic_only': True,
            'notice': 'LIVE MODE — inspect each brief provenance and validation outcome',
            'fallback_reason': None, 'calls_reserved_this_run': budget.calls,
            'budget': budget.summary(), 'briefs': briefs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true',
                        help='Authorized use only: broker-injected NEBIUS_API_KEY; up to 3 requests, no retries')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = run_demo(live=args.live)
    except (ValueError, KeyError, TypeError, OSError, RecursionError):
        print('Demo refused: bundled recording failed validation. No replacement or automatic request.', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        print(result['notice'])
        if result['fallback_reason']:
            print(result['fallback_reason'])
        print('Requests reserved this run: %d' % result['calls_reserved_this_run'])
        for brief in result['briefs']:
            print('\n%s | %s' % (brief['case_id'], brief['status']))
            print(brief['hypothesis'] or brief['reason'])
            for step in brief['steps']:
                print('  [%s §%d] %s' % (step['source'], step['step'], step['text']))
            print('Actions executed: %d' % brief['actions_executed'])
        if result.get('routed'):
            print('\n=== SignalDesk route (Lightning first, Super with reasoning for physical actions,'
                  ' vetoes and abstentions; validator pre-triage) ===')
            for r in result['routed']:
                b = r['brief']
                decision = (b['hypothesis'] if b and b['runbook_id'] else
                            'NO INCIDENT' if r['telemetry'] == 'healthy' else 'HAND OFF to a person')
                print('\n%s %s | %s' % (r['case_id'], r['title'], decision))
                print('  route: %s (%s); recorded %.1f s, USD %.4f' %
                      (r['path'], r['reason'], r['latency_ms'] / 1000, r['usd']))
                for v in r['vetoes']:
                    print('  VETO: ' + v + (' (recorded for comparison; the route asks no model here)'
                                           if r['path'] == 'pre-triage' else ''))
        print('\nOpen site/index.html for the interactive recorded demo.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
