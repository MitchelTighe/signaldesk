"""Deterministic presentation fixtures. Never admitted to the live provider."""
from copy import deepcopy

from .budget import LIGHTNING, SUPER
from .core import corpus, dataset
from .live import abstention, runbooks, validate_draft
from .mock_server import mock_draft
from .safeio import digest

STAMP = '2026-10-21T12:00:00+00:00'  # Synthetic scenario clock, not a vendor timestamp.
SPLIT = 'synthetic-tape-showcase-v1'


def fixture_cases():
    """Forty unchanged held-out cases plus eighteen presentation-only cases."""
    cases = deepcopy(corpus('heldout')['cases'])
    titles = [
        'Drive 2 asks for a cleaning cartridge', 'One cartridge raises the media flag',
        'Drive 5 reports a hardware fault', 'Restore waits on a slow cartridge load',
        'Library inventory disagrees with the catalog', 'LTFS volume refuses to mount',
        'Tape path keeps resetting', 'Scratch cartridge rejects writes',
    ]
    for index, (book, title) in enumerate(zip(dataset()['runbooks'], titles), 1):
        cid = f'D{index:02d}'
        value = book['minimum'] * 2 if book['unit'] == 'seconds' else book['minimum'] + (2 if book['id'] == 'RB-PATH' else 0)
        cases.append({
            'id': cid, 'title': title,
            'text': f'Synthetic tape library A, 12:00–12:05 UTC. {title}. '
                    'A read-only snapshot of sg_logs, mtx status and sense data is attached. The operator '
                    'has not changed anything. Correlate observations before proposing a diagnosis.',
            'evidence': [
                {'id': cid+'-E1', 'metric': book['metric'], 'value': value},
                {'id': cid+'-E2', 'metric': 'mounts_observed', 'value': 12 + index * 3},
                {'id': cid+'-E3', 'metric': 'snapshot_age_seconds', 'value': 20},
            ],
            'expected': book['id'], 'kind': 'presentation-only',
        })
    edges = [
        ('Exactly at the cleaning threshold (one flag)', 1, 'RB-CLEAN'),
        ('Just below the cleaning threshold (no flags)', 0, None),
        ('Cleaning flag count is negative', -1, None),
        ('Collector returned a string instead of a number', '1', None),
        ('TapeAlert page attachment is empty', None, None),
        ('Cleaning and hardware flags overlap', 1, None),
        ('Bibliothèque — café / 東京 / reduced-motion review', 1, 'RB-CLEAN'),
        ('Provider unavailable — simulated transport failure', 1, 'RB-CLEAN'),
        ('Draft contains an invented source — rejected', 1, 'RB-CLEAN'),
        ('Budget exhausted — case not requested', 1, 'RB-CLEAN'),
    ]
    for index, (title, value, expected) in enumerate(edges, 9):
        cid = f'D{index:02d}'
        evidence = [] if value is None else [
            {'id': cid+'-E1', 'metric': 'tapealert_cleaning_flags', 'value': value}]
        if index == 14:
            evidence.append({'id': cid+'-E2', 'metric': 'tapealert_hardware_flags', 'value': 1})
        text = 'Synthetic drive ticket. Read the attached TapeAlert snapshot; no action has been taken.'
        if index == 15:
            text += ' ' + ('A long synthetic observation stays readable on a narrow screen. ' * 18)
        cases.append({'id': cid, 'title': title, 'text': text, 'evidence': evidence,
                      'expected': expected, 'kind': 'presentation-only'})
    return cases


def generate_report():
    rows = []
    for model in (LIGHTNING, SUPER):
        for case in fixture_cases():
            public = {k: deepcopy(case[k]) for k in ('id', 'title', 'text', 'evidence')}
            context = {'incident': public, 'runbooks': runbooks(), 'public_docs': []}
            provenance = {
                'origin': 'local-mock', 'model': model, 'observed_at': STAMP,
                'elapsed_ms': 0, 'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
                'request_sha256': digest({'synthetic_generator': SPLIT, 'model': model, 'case': public}),
                'replayed': True,
            }
            outcome = 'validated'
            brief = validate_draft(mock_draft(context), public, provenance=provenance)
            if case['id'] == 'D16':
                outcome, brief = 'error', None
            elif case['id'] == 'D17':
                bad = mock_draft(context)
                bad['steps'][0]['source'] = 'RB-INVENTED'
                try:
                    validate_draft(bad, public, provenance=provenance)
                except ValueError:
                    brief = abstention(public, 'Draft rejected', provenance, 'rejected-draft')
                    outcome = 'error'
                else:
                    raise AssertionError('Invalid source unexpectedly accepted')
            elif case['id'] == 'D18':
                outcome, brief = 'not-run', None
            rows.append({'model': model, 'case_id': case['id'], 'case': public,
                         'expected': case['expected'], 'actual': brief['runbook_id'] if brief else None,
                         'outcome': outcome, 'brief': brief})
    return {
        'schema': 'signaldesk-live-eval-v1', 'synthetic_only': True,
        'split': SPLIT, 'complete': False, 'models': [LIGHTNING, SUPER],
        'dataset_sha256': digest(fixture_cases()), 'rows': rows,
    }


def walkthrough():
    return {
        'schema': 'signaldesk-walkthrough-v1', 'split': SPLIT,
        'disclosure': 'Deterministic mocks; synthetic timestamp; zero token usage. Not a benchmark.',
        'steps': [
            {'id': 'supported', 'case_id': 'H05', 'status': 'supported-hypothesis', 'outcome': 'validated'},
            {'id': 'conflict', 'case_id': 'H35', 'status': 'needs-human', 'outcome': 'validated'},
            {'id': 'missing', 'case_id': 'H36', 'status': 'needs-human', 'outcome': 'validated'},
            *[{'id': f'family-{i}', 'case_id': f'D{i:02d}', 'status': 'supported-hypothesis',
               'outcome': 'validated'} for i in range(1, 9)],
            *[{'id': name, 'case_id': f'D{i:02d}', 'status': status, 'outcome': outcome}
              for i, name, status, outcome in [
                  (9, 'threshold', 'supported-hypothesis', 'validated'),
                  (10, 'below-threshold', 'needs-human', 'validated'),
                  (11, 'invalid-count', 'needs-human', 'validated'),
                  (12, 'wrong-type', 'needs-human', 'validated'),
                  (13, 'empty-telemetry', 'needs-human', 'validated'),
                  (14, 'multiple-faults', 'needs-human', 'validated'),
                  (15, 'unicode-long-text', 'supported-hypothesis', 'validated'),
                  (16, 'transport-error', 'needs-human', 'error'),
                  (17, 'rejected-source', 'needs-human', 'error'),
                  (18, 'budget-stop', 'needs-human', 'not-run'),
              ]],
        ],
        'interaction_paths': ['source-link', 'step-link', 'model-switch', 'search',
                              'empty-search', 'decision-filter', 'previous-next', 'download',
                              'tour-pause-resume', 'keyboard', 'reduced-motion', 'light-dark'],
    }
