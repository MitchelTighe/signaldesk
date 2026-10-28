"""Lead-only live held-out comparison; --dry-run uses a fake key on loopback."""
import argparse
from decimal import Decimal
import math
from contextlib import nullcontext
from pathlib import Path
import sys
from .budget import Budget, GuardError, LIGHTNING, SUPER, MODELS, PRICING
from .core import case_by_id, corpus, dataset
from .live import LiveProvider, abstention, public_case
from .providers import ProviderError
from .safeio import atomic_json, digest


def metrics(rows):
    # Invalid/missing output is an error, NEVER a correct rejection of an unknown.
    valid = [r for r in rows if r['outcome'] == 'validated']
    accepted = [r for r in valid if r['actual'] is not None]
    known = sum(r['expected'] is not None for r in rows)
    tp = sum(r['actual'] == r['expected'] for r in accepted)
    rejected = sum(r['actual'] is None for r in valid)
    correct_rejected = sum(r['actual'] is None and r['expected'] is None for r in valid)
    unknown = len(rows) - known
    return {'total': len(rows), 'known': known, 'accepted': len(accepted), 'correct_supported': tp,
            'abstained': rejected, 'correct_abstained': correct_rejected,
            'errors': sum(r['outcome'] == 'error' for r in rows),
            'not_run': sum(r['outcome'] == 'not-run' for r in rows),
            'correct': tp + correct_rejected,
            'precision': tp / len(accepted) if accepted else None,
            'recall': tp / known if known else None,
            'abstention_rate': rejected / len(rows) if rows else None,
            'unknown_rejection_rate': correct_rejected / unknown if unknown else None,
            'decision_accuracy': (tp + correct_rejected) / len(rows) if rows else None}


def complete_rows(rows):
    return all(r['outcome'] != 'not-run' for r in rows)


def recorded_usage(rows, model):
    """Original recorded request usage, including rejected drafts; not replay spend."""
    provenance = [r['brief']['provenance'] for r in rows if r.get('brief')]
    inp = sum(p['usage']['prompt_tokens'] for p in provenance)
    out = sum(p['usage']['completion_tokens'] for p in provenance)
    rates = PRICING['models'][model]
    estimate = (Decimal(str(rates['input'])) * inp + Decimal(str(rates['output'])) * out) / 1_000_000
    latency = sorted(p['elapsed_ms'] for p in provenance)
    return {'prompt_tokens': inp, 'completion_tokens': out, 'total_tokens': inp + out,
            'usd_token_estimate': float(estimate),
            'rates_usd_per_million': dict(rates), 'rate_observed_at': PRICING['observed_at'],
            'rate_source': PRICING['source'],
            'latency_p50_ms': latency[(len(latency)-1)//2] if latency else None,
            'latency_p95_ms': latency[max(0, math.ceil(len(latency)*.95)-1)] if latency else None,
            'note': 'Original recorded usage at the public rate snapshot; not new replay spend. '
                    'Mock token counts/latencies are plumbing data, not vendor measurements.'}


def evaluate_models(models, cases, budget, cache, replay=False, mock_url=None, output_cap=1600,
                    grounding=False, transport=None, search_transport=None, thinking=True):
    from .grounding import PublicDocs
    from .safeio import post
    public_docs = PublicDocs(budget, Path(cache) / 'public-docs', enabled=grounding, replay=replay,
                             transport=search_transport or post)
    providers = {m: LiveProvider(m, budget, cache, replay, mock_url, output_cap,
                                transport=transport or post,
                                thinking=thinking.get(m, True) if isinstance(thinking, dict) else thinking)
                 for m in models}
    rows, stopped = [], None
    for model in models:
        provider = providers[model]
        for case in cases:
            row = {'model': model, 'case_id': case['id'], 'case': public_case(case),
                   'expected': case['expected'], 'actual': None, 'outcome': 'not-run', 'brief': None}
            if stopped:
                rows.append(row)
                continue
            try:
                if grounding:
                    # All fixed public queries are cached once per family. No incident is sent to search.
                    # Retrieve docs only for families with a metric present; no label leakage.
                    families = [r['id'] for r in dataset()['runbooks'] if
                                any(e['metric'] == r['metric'] for e in case['evidence'])]
                    provider.docs = [d for family in families for d in public_docs.search(family)]
                result = provider.draft(case)
                row.update(brief=result, actual=result['runbook_id'],
                           outcome='error' if result['validation'] == 'rejected-draft' else 'validated')
            except GuardError as error:
                row.update(outcome='error', error=str(error))
                stopped = str(error)
            except ProviderError:
                row.update(outcome='error', error='Provider/cache failure; no body, credential or automatic fallback')
                # Stop on access/transport failures: don't burn the whole budget on a broken endpoint.
                stopped = 'Provider/cache failure; remaining cases were not run'
            rows.append(row)
    per_model = {m: metrics([r for r in rows if r['model'] == m]) for m in models}
    quality = all((m['precision'] or 0) >= .8 and (m['recall'] or 0) >= .65
                  and m['unknown_rejection_rate'] in (None, 1) and not m['errors'] and not m['not_run']
                  for m in per_model.values())
    origins = sorted({r['brief']['provenance']['origin'] for r in rows if r['brief']})
    from .routing import claims, compare
    from .telemetry import split_cases
    split = ('heldout' if cases == corpus('heldout')['cases'] else
             'hard' if cases == split_cases('hard') else
             'second-author' if cases == split_cases('second-author') else 'demo')
    by_kind = {}
    for kind in sorted({c.get('kind', 'demo') for c in cases}):
        ids = {c['id'] for c in cases if c.get('kind', 'demo') == kind}
        by_kind[kind] = {m: metrics([r for r in rows if r['model'] == m and r['case_id'] in ids])['correct']
                         for m in models}
        by_kind[kind]['total'] = len(ids)
    return {'schema': 'signaldesk-live-eval-v1', 'synthetic_only': True, 'split': split,
            'claims': claims(rows), 'by_kind': by_kind,
            'routing': compare(rows, cases) if complete_rows(rows) else None,
            'dataset_sha256': digest(cases), 'models': list(models), 'origins': origins,
            'complete': stopped is None, 'stop_reason': stopped, 'quality_gates_passed': quality,
            'request_options': {'thinking': thinking, 'grounding': grounding, 'max_output_tokens': output_cap},
            'metrics': per_model, 'budget': budget.summary(), 'pricing': PRICING,
            'recorded_usage': {m: recorded_usage([r for r in rows if r['model'] == m], m) for m in models},
            'cache_hits': sum(p.cache_hits for p in providers.values()), 'rows': rows,
            'note': ('Synthetic fixtures from a second AI author blind to the product runbooks and previous cases/results; '
                     'reviewer-normalized observations, not independent human or field validation. '
                     if split == 'second-author' else 'Same-author synthetic fixtures; no external validation. ')
                    + 'Local-mock numbers only test plumbing. '
                    'Models draft constrained hypotheses and exact cited steps; independent Python gates every result. '
                    'Cached provenance is a local record, not cryptographic vendor attestation.'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('runs/live-evaluation.json'))
    p.add_argument('--cache', type=Path, default=Path('cache'))
    p.add_argument('--models', nargs='+', choices=MODELS, default=[LIGHTNING, SUPER])
    p.add_argument('--case', help='Optional one unchanged demo case; default evaluates all 40 held-out cases per model')
    p.add_argument('--split', choices=['heldout', 'hard', 'second-author'], default='heldout',
                   help='heldout: 40 frozen cases; hard: 14 adversarial cases; second-author: 10 blind-authored synthetic cases')
    p.add_argument('--dry-run', action='store_true', help='Local HTTP mock, fake credential; never a vendor call')
    p.add_argument('--replay', action='store_true', help='Cache only; cache misses never use network')
    p.add_argument('--tavily', action='store_true', help='Optional fixed public-doc searches; needs TAVILY_API_KEY')
    p.add_argument('--no-thinking', action='store_true',
                   help='Send chat_template_kwargs enable_thinking=false (avoids hidden-reasoning truncation)')
    p.add_argument('--reasoning-for', nargs='+', choices=MODELS, default=[],
                   help='With --no-thinking, keep reasoning ON for these models (routing: Super reasons)')
    p.add_argument('--max-calls', type=int, default=80)
    p.add_argument('--max-tokens', type=int, default=1_500_000)
    p.add_argument('--max-usd', default='1')
    p.add_argument('--cost-multiplier', default='2')
    p.add_argument('--max-output-tokens', type=int, default=1600)
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        if len(args.models) != len(set(args.models)):
            raise GuardError('Duplicate model IDs are not allowed')
        if args.dry_run and args.tavily:
            raise GuardError('Dry-run forbids external search; Tavily is tested with injected transports')
        budget = Budget(args.max_calls, args.max_tokens, args.max_usd, args.cost_multiplier)
        from .telemetry import split_cases
        cases = [case_by_id(args.case)] if args.case else split_cases(args.split)
        from .mock_server import mock_server
        with mock_server() if args.dry_run else nullcontext((None, [])) as (url, calls):
            report = evaluate_models(args.models, cases, budget, args.cache, args.replay, url,
                                     args.max_output_tokens, args.tavily,
                                     thinking=(not args.no_thinking) if not args.reasoning_for else
                                     {m: (not args.no_thinking) or m in args.reasoning_for for m in args.models})
        atomic_json(args.output, report)
        # Print safe summaries only, no raw remote body/credential/exception repr.
        print('LOCAL MOCK — NOT VENDOR INFERENCE' if args.dry_run else 'CACHE REPLAY' if args.replay
              else 'NEBIUS EVALUATION — inspect completion and provenance')
        for model, measured in report['metrics'].items():
            print('%s: correct=%d/%d, errors=%d, not_run=%d' %
                  (model, measured['correct'], measured['total'], measured['errors'], measured['not_run']))
        b = report['budget']
        print('calls=%d tokens_reserved=%d USD_reserved=%.6f cache_hits=%d' %
              (b['calls_reserved'], b['tokens_reserved'], b['usd_reserved_upper_estimate'], report['cache_hits']))
        print('Complete=%s; quality_gates=%s; report written' % (report['complete'], report['quality_gates_passed']))
        return 2 if not report['complete'] else 0 if report['quality_gates_passed'] else 1
    except (GuardError, ProviderError, ValueError, OSError):
        print('Invalid configuration or artifact access; no credential or remote body logged', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
