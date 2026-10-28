"""Build a credential-free static judge site from sanitized, revalidated run records."""
import argparse
from datetime import datetime
import math
from pathlib import Path
import sys
from .budget import MODELS
from .core import corpus, dataset
from .grounding import validate_docs
from .live import abstention, canonical_draft, public_case, validate_draft, telemetry_abstention_reason
from .live_eval import metrics, recorded_usage
from .safeio import atomic_json, digest, pack, parse


ORIGINS = {'live-nebius', 'local-mock', 'injected-mock'}


def safe_provenance(p, model):
    if not isinstance(p, dict) or p.get('origin') not in ORIGINS or p.get('model') != model:
        raise ValueError('Invalid run provenance')
    stamp = p.get('observed_at')
    if not isinstance(stamp, str) or len(stamp) > 40:
        raise ValueError('Missing observation time')
    datetime.fromisoformat(stamp)
    elapsed = p.get('elapsed_ms')
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or not 0 <= elapsed <= 3_600_000:
        raise ValueError('Invalid elapsed time')
    usage = p.get('usage')
    if (not isinstance(usage, dict) or set(usage) != {'prompt_tokens', 'completion_tokens', 'total_tokens'}
            or any(type(v) is not int or not 0 <= v <= 2_000_000 for v in usage.values())
            or usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']):
        raise ValueError('Invalid usage')
    fingerprint = p.get('request_sha256')
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
        raise ValueError('Invalid request hash')
    safe = {'origin': p['origin'], 'model': model, 'observed_at': stamp, 'elapsed_ms': elapsed,
            'usage': usage, 'request_sha256': fingerprint, 'replayed': True,
            'endpoint': 'https://api.tokenfactory.nebius.com/v1/' if p['origin'] == 'live-nebius' else 'local test transport'}
    if type(p.get('thinking')) is bool:
        safe['thinking'] = p['thinking']
    return safe


def sanitize_report(report, require_live=False):
    if (not isinstance(report, dict) or report.get('schema') != 'signaldesk-live-eval-v1'
            or report.get('synthetic_only') is not True or not isinstance(report.get('rows'), list)
            or not 1 <= len(report['rows']) <= 320):
        raise ValueError('Not a bounded synthetic evaluation report')
    models = report.get('models')
    if (not isinstance(models, list) or not models or any(m not in MODELS for m in models)
            or len(models) != len(set(models))):
        raise ValueError('Invalid report models')
    from .demo_data import SPLIT, fixture_cases
    showcase = report.get('split') == SPLIT
    if showcase and require_live:
        raise ValueError('Presentation fixtures are mock-only, never qualifying runtime evidence')
    from .telemetry import split_cases
    fixtures = {c['id']: c for c in (fixture_cases() if showcase else
                                   dataset()['cases'] + corpus('heldout')['cases'] + split_cases('hard'))}
    safe, seen, origins = [], set(), set()
    for row in report['rows']:
        model, case_id = row.get('model'), row.get('case_id')
        if model not in models or case_id not in fixtures or (model, case_id) in seen:
            raise ValueError('Unknown or duplicate replay row')
        seen.add((model, case_id))
        case = fixtures[case_id]
        public = {k: case[k] for k in ('id', 'title', 'text', 'evidence')} if showcase else public_case(case)
        if row.get('case') != public or row.get('expected') != case['expected']:
            raise ValueError('Replay fixture or label changed')
        outcome = row.get('outcome')
        if outcome not in {'validated', 'error', 'not-run'}:
            raise ValueError('Unknown row outcome')
        original = row.get('brief')
        if original and original.get('provenance'):
            provenance = safe_provenance(original.get('provenance'), model)
            if showcase and provenance['origin'] != 'local-mock':
                raise ValueError('Presentation fixtures must retain mock provenance')
            origins.add(provenance['origin'])
            docs = validate_docs(original.get('public_docs', []))
            checked = validate_draft(canonical_draft(original), public, docs, provenance)
            for field in ('case_id', 'title', 'synthetic', 'input_sha256', 'status', 'runbook_id',
                          'hypothesis', 'evidence', 'steps', 'public_docs', 'actions_executed'):
                if checked[field] != original.get(field):
                    raise ValueError('Replay result does not match current independent validator')
            if checked.get('model_proposal') != original.get('model_proposal'):
                raise ValueError('Recorded veto does not re-derive from the fixture and runbooks')
            validation = original.get('validation')
            if validation not in {'valid', 'telemetry-abstention', 'rejected-draft'}:
                raise ValueError('Unknown validation outcome')
            if validation == 'rejected-draft':
                if outcome != 'error' or checked['runbook_id'] is not None:
                    raise ValueError('Rejected output was promoted')
                checked = abstention(public, 'Model draft rejected by the validator; operator review required', provenance, 'rejected-draft')
            elif outcome != 'validated':
                raise ValueError('Validated brief has inconsistent outcome')
            elif validation == 'telemetry-abstention':
                if checked['runbook_id'] is not None:
                    raise ValueError('Forced handoff was promoted')
                checked['reason'] = telemetry_abstention_reason(public)
                checked['validation'] = validation
            if row.get('actual') != checked['runbook_id']:
                raise ValueError('Actual label disagrees with validated output')
        else:
            if outcome == 'validated' or row.get('actual') is not None:
                raise ValueError('Missing brief was promoted')
            reason = ('Transport unavailable; no completed response. Ask an operator.'
                      if outcome == 'error' else
                      'This case was not requested or completed. Ask an operator.')
            checked = abstention(public, reason, {}, outcome)
            if original is not None and original != checked:
                raise ValueError('Unavailable response was altered or promoted')
        safe.append({'model': model, 'case_id': case_id, 'case': public, 'expected': case['expected'],
                     'actual': checked['runbook_id'], 'outcome': outcome, 'brief': checked})
    if not origins or (require_live and (origins != {'live-nebius'} or report.get('complete') is not True
                                        or any(r['outcome'] == 'not-run' for r in safe))):
        raise ValueError('Real-run build requires completed brokered Nebius evidence; mocks cannot qualify')
    if report.get('split') in SPLITS or showcase:
        required_cases = fixture_cases() if showcase else SPLITS[report['split']]()
        required = {(m, c['id']) for m in models for c in required_cases}
        if seen != required or report.get('dataset_sha256') != digest(required_cases):
            raise ValueError('Held-out run is incomplete or changed')
    elif len({r['case_id'] for r in safe}) != 1:
        raise ValueError('Single-case replay has inconsistent case IDs')
    from .routing import claims, compare
    from .telemetry import telemetry_state
    for row in safe:
        row['telemetry'] = telemetry_state(row['case'])
        if not showcase:
            row['kind'] = fixtures[row['case_id']].get('kind', 'demo')
            row['why'] = fixtures[row['case_id']].get('why')
    groups = {}
    if not showcase:
        heldout_ids = {c['id'] for c in corpus('heldout')['cases']}
        hard_ids = {c['id'] for c in split_cases('hard')}
        for name, ids in (('heldout', heldout_ids), ('hard', hard_ids)):
            part = [r for r in safe if r['case_id'] in ids]
            if part:
                cases = [fixtures[i] for i in sorted({r['case_id'] for r in part})]
                groups[name] = {'cases': len(cases),
                                'metrics': {m: metrics([r for r in part if r['model'] == m]) for m in models},
                                'routing': {k: v for k, v in (compare(part, cases) or {}).items() if k != 'cases'} or None}
    routed = compare(safe, [fixtures[i] for i in sorted({r['case_id'] for r in safe})]) if not showcase else None
    return {'schema': 'signaldesk-static-replay-v1', 'synthetic_only': True, 'models': models,
            'claims': claims(safe), 'groups': groups, 'routing': routed,
            'split': report.get('split'),
            'origins': sorted(origins), 'live_recorded': origins == {'live-nebius'},
            'source_sha256': digest(report), 'dataset_sha256': report.get('dataset_sha256'),
            'metrics': {m: metrics([r for r in safe if r['model'] == m]) for m in models},
            'recorded_usage': {m: recorded_usage([r for r in safe if r['model'] == m and r['brief']['provenance']], m)
                               for m in models},
            'runbooks': dataset()['runbooks'], 'sources': dataset().get('sources', {}),
            'captured_cases': captured_cases(), 'rows': safe,
            'disclosure': 'Cached run records, not a new inference request. Requested models are not independently '
                          'attested. Same-author synthetic evaluation; no production accuracy claim.'}


def captured_cases():
    """Case IDs whose fixture says its readings came from a sanitized mhVTL capture."""
    from .telemetry import split_cases
    return sorted(c['id'] for c in corpus('heldout')['cases'] + split_cases('hard')
                  if str(c.get('capture', '')).startswith('mhvtl'))


def _heldout():
    return corpus('heldout')['cases']


def _hard():
    from .telemetry import split_cases
    return split_cases('hard')


SPLITS = {'heldout': _heldout, 'hard': _hard, 'heldout+hard': lambda: _heldout() + _hard()}


def merge_reports(reports):
    """Combine one complete held-out report and one complete hard report (separate budgets)."""
    by_split = {r.get('split'): r for r in reports}
    if len(reports) == 1:
        return reports[0]
    if set(by_split) != {'heldout', 'hard'} or len(reports) != 2:
        raise ValueError('Merge needs exactly one heldout and one hard report')
    a, b = by_split['heldout'], by_split['hard']
    if a.get('models') != b.get('models'):
        raise ValueError('Merged reports must request the same models')
    for r, name in ((a, 'heldout'), (b, 'hard')):
        if r.get('dataset_sha256') != digest(SPLITS[name]()):
            raise ValueError('Merged report fixture changed')
    return {'schema': a.get('schema'), 'synthetic_only': a.get('synthetic_only') and b.get('synthetic_only'),
            'split': 'heldout+hard', 'models': a['models'],
            'complete': a.get('complete') is True and b.get('complete') is True,
            'dataset_sha256': digest(SPLITS['heldout+hard']()), 'rows': a['rows'] + b['rows'],
            'request_options': [a.get('request_options'), b.get('request_options')]}


def build(report, output, require_live=False):
    data = sanitize_report(report, require_live)
    target = Path(output)
    try:
        target.mkdir(parents=True)
    except FileExistsError:
        if not target.is_dir():
            raise
    else:
        target.chmod(0o755)  # Only a directory this builder just created; never loosen an existing parent.
    packed = pack(data).decode().replace('<', '\\u003c')
    template = Path(__file__).parents[1].joinpath('web/replay-template.html').read_text()
    html = template.replace('__REPLAY_DATA__', packed)
    (target / 'index.html').write_text(html, encoding='utf-8')
    (target / 'index.html').chmod(0o644)
    atomic_json(target / 'replay.json', data, public=True)
    headers = ("/*\n"
               "  X-Content-Type-Options: nosniff\n"
               "  Referrer-Policy: no-referrer\n"
               "  X-Frame-Options: DENY\n"
               "  Permissions-Policy: camera=(), microphone=(), geolocation=()\n"
               "  Cache-Control: public, max-age=0, must-revalidate\n"
               "  Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'; "
               "style-src 'unsafe-inline'; img-src data:; connect-src 'none'; "
               "font-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'\n")
    (target / '_headers').write_text(headers, encoding='utf-8')
    (target / '_headers').chmod(0o644)
    atomic_json(target / 'manifest.json', {'schema': data['schema'], 'source_sha256': data['source_sha256'],
                'live_recorded': data['live_recorded'], 'files': {
                    'index.html': __import__('hashlib').sha256(html.encode()).hexdigest(),
                    '_headers': __import__('hashlib').sha256(headers.encode()).hexdigest(),
                    'replay.json': __import__('hashlib').sha256((target/'replay.json').read_bytes()).hexdigest()}}, public=True)
    return data


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', required=True, type=Path, action='append',
                   help='One report, or a heldout report plus a hard report (repeat the flag)')
    p.add_argument('--output', type=Path, default=Path('site'))
    p.add_argument('--require-live', action='store_true')
    args = p.parse_args(argv)
    try:
        report = merge_reports([parse(r.read_bytes(), max_bytes=2_000_000) for r in args.report])
        data = build(report, args.output, args.require_live)
        print('Static site built: %d rows; %s; zero runtime API calls' %
              (len(data['rows']), 'recorded Nebius run' if data['live_recorded'] else 'MOCK QA — real vendor run pending'))
        return 0
    except (ValueError, KeyError, TypeError, OSError, RecursionError):
        print('Replay build refused: source report failed independent validation', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
