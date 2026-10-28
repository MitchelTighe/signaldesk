"""Ten frozen finish scenarios: local validator behavior, never model accuracy."""
import hashlib
import json
from pathlib import Path
import sys

from .live import validate_draft
from .core import LocalClassifier, brief as baseline_brief, dataset
from .challenge import confined as is_confined
from .safeio import parse

FROZEN_SHA256 = '83a15f6dd8f592077fea41e2450847f1e9861b9191676610326baee00da3524d'
LABELS_SHA256 = '5b975e2ade4a9d948d379888b796710bd4e6e43d5078e9cd141de94b96997a5b'


def finish_cases():
    raw = Path(__file__).with_name('finish_cases.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA256:
        raise ValueError('Frozen finish cases checksum mismatch')
    return parse(raw, max_bytes=200_000)['cases']


def evaluate_finish():
    raw_labels = Path(__file__).with_name('finish_labels.json').read_bytes()
    if hashlib.sha256(raw_labels).hexdigest() != LABELS_SHA256:
        raise ValueError('Frozen finish baseline labels checksum mismatch')
    labels = parse(raw_labels)['labels']
    books = {r['id']: r for r in dataset()['runbooks']}
    model = LocalClassifier(list(books.values()))
    rows = []
    for fixture in finish_cases():
        try:
            brief = validate_draft(fixture['draft'], fixture['case'])
            outcome = brief['status']
            confined = (brief['actions_executed'] == 0 and
                        (brief['runbook_id'] is not None or not brief['steps']))
        except ValueError:
            outcome, confined = 'rejected-draft', True
        # Programming errors must escape; an exception is not a successful handoff.
        baseline = baseline_brief(fixture['case'], model)
        baseline_confined = is_confined(baseline, fixture['case'], books)
        rows.append({'id': fixture['id'], 'scenario': fixture['scenario'],
                     'judging_criteria': fixture['judging_criteria'],
                     'input_characters': len(fixture['case']['text']),
                     'expected_outcome': fixture['expected_outcome'],
                     'actual_outcome': outcome, 'output_confined': confined,
                     'baseline_expected': labels[fixture['id']],
                     'baseline_actual': baseline['runbook_id'],
                     'baseline_label_match': baseline['runbook_id'] == labels[fixture['id']],
                     'baseline_output_confined': baseline_confined,
                     'passed': outcome == fixture['expected_outcome'] and confined})
    return {'schema': 'signaldesk-finish-eval-v1', 'synthetic_only': True,
            'backend': 'deterministic-validator-with-authored-drafts',
            'dataset_sha256': FROZEN_SHA256, 'total': len(rows),
            'baseline_labels_sha256': LABELS_SHA256,
            'baseline_backend': model.name,
            'baseline_label_matches': sum(r['baseline_label_match'] for r in rows),
            'baseline_misses': [r['id'] for r in rows if not r['baseline_label_match']],
            'passed': sum(r['passed'] for r in rows),
            'quality_gates_passed': len(rows) == 10 and all(r['passed'] and r['baseline_output_confined'] for r in rows),
            'limits': 'Local validator checks, not NVIDIA inference, model injection resistance, '
                      'product usability or production accuracy. CPU labels are reported without tuning '
                      'or an accuracy floor; exit gates cover validator outcomes and source confinement only. '
                      'Long inputs bypass no live allowlist.',
            'cases': rows}


def main():
    result = evaluate_finish()
    print(json.dumps(result, indent=2))
    return 0 if result['quality_gates_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
