"""Super-VL stretch: only the hash-pinned bundled synthetic dashboard may be sent."""
import argparse
import base64
from contextlib import nullcontext
import hashlib
from pathlib import Path
import struct
import sys
from .budget import Budget, GuardError, VISION, PRICING
from .core import case_by_id
from .live import LiveProvider, public_case
from .live_eval import metrics, recorded_usage
from .providers import ProviderError
from .safeio import atomic_json, digest, parse

FIXTURES = Path(__file__).parents[1] / 'fixtures'
DASHBOARD_SHA256 = '5a341456dab61bcd86728a93f9769f92b3ccbaee3a91e12a08b0a96a60b00f54'


def screenshot():
    manifest = parse((FIXTURES/'dashboard.json').read_bytes())
    raw = (FIXTURES/'dashboard-clean.png').read_bytes()
    if (not 24 <= len(raw) <= 1_000_000 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR'
            or struct.unpack('>II', raw[16:24]) != (1280, 720)
            or manifest.get('sha256') != DASHBOARD_SHA256
            or hashlib.sha256(raw).hexdigest() != DASHBOARD_SHA256
            or manifest.get('case_id') != 'clean-demo' or manifest.get('synthetic_only') is not True):
        raise ProviderError('Bundled screenshot integrity failed; arbitrary images are not allowed')
    return 'data:image/png;base64,' + base64.b64encode(raw).decode(), manifest['sha256']


def vision_draft(provider):
    if provider.model != VISION or provider.docs:
        raise ProviderError('Screenshot triage requires Super-VL without web grounding')
    image, fingerprint = screenshot()
    case = public_case(case_by_id('clean-demo'))
    visible = public_case(case_by_id('clean-demo'))
    # Model must read the number from pixels. IDs are supplied to make references explicit.
    visible['evidence'] = [{'id': e['id'], 'metric': e['metric']} for e in case['evidence']]
    context = {'incident': visible, 'runbooks': provider.context(case_by_id('clean-demo'))['runbooks'],
               'public_docs': [], 'input_mode': 'bundled-dashboard-screenshot',
               'instruction': 'Read numeric observations from the screenshot. The incident evidence list '
                              'names allowed references but omits their values. If unreadable, abstain.'}
    result = provider._request(context, image=image, validation_case=case)
    result['provenance']['input_kind'] = 'bundled-dashboard-screenshot'
    result['provenance']['image_sha256'] = fingerprint
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--replay', action='store_true')
    p.add_argument('--output', type=Path, default=Path('runs/vision.json'))
    p.add_argument('--cache', type=Path, default=Path('cache/vision'))
    args = p.parse_args(argv)
    case = case_by_id('clean-demo')
    budget = Budget(max_calls=1, max_tokens=65000)
    row = {'model': VISION, 'case_id': case['id'], 'case': public_case(case),
           'expected': case['expected'], 'actual': None, 'outcome': 'error', 'brief': None}
    stopped, provider = None, None
    try:
        from .mock_server import mock_server
        with mock_server() if args.dry_run else nullcontext((None, [])) as (url, _):
            provider = LiveProvider(VISION, budget, args.cache, args.replay, url)
            result = vision_draft(provider)
            row.update(brief=result, actual=result['runbook_id'],
                       outcome='error' if result['validation'] == 'rejected-draft' else 'validated')
    except (ProviderError, GuardError, ValueError, OSError):
        stopped = 'Screenshot integrity, provider, cache or budget failure; no automatic retry'
    report = {'schema': 'signaldesk-live-eval-v1', 'synthetic_only': True, 'split': 'demo',
                  'dataset_sha256': digest([case]), 'models': [VISION],
                  'origins': [row['brief']['provenance']['origin']] if row['brief'] else [],
                  'complete': stopped is None, 'stop_reason': stopped,
                  'quality_gates_passed': row['actual'] == row['expected'] and row['outcome'] == 'validated',
                  'metrics': {VISION: metrics([row])}, 'rows': [row], 'budget': budget.summary(),
                  'recorded_usage': {VISION: recorded_usage([row], VISION)},
                  'cache_hits': provider.cache_hits if provider else 0,
                  'pricing': PRICING, 'note': 'Vision transport preview is mocked unless origin is live-nebius. '
                  'Only one bundled screenshot; no general OCR accuracy or arbitrary upload support.'}
    try:
        atomic_json(args.output, report)
    except OSError:
        print('Screenshot report could not be written; no body or credential logged', file=sys.stderr)
        return 2
    print('Screenshot triage: %s; complete=%s; USD reserved %.6f' %
          (report['origins'] or ['no completed response'], report['complete'], float(budget.reserved_usd)))
    return 2 if stopped else 0 if report['quality_gates_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
