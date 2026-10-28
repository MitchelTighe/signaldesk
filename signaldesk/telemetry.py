"""Deterministic telemetry reading, the hard split and a rules-only baseline.

Kept outside core.py so the frozen baseline module stays byte-identical.
"""
from importlib.resources import files
import json
import math

from .core import corpus, dataset


def split_cases(split):
    if split == 'second-author':
        return json.loads(files('signaldesk').joinpath('second_author.json').read_text(encoding='utf-8'))['cases']
    if split == 'hard':
        return json.loads(files('signaldesk').joinpath('hard.json').read_text(encoding='utf-8'))['cases']
    return corpus(split)['cases']


def corroborates(e, book):
    value = e['value']
    return (e['metric'] == book['metric'] and type(value) in (int, float)
            and math.isfinite(value) and value >= book['minimum']
            and (book.get('unit') != 'percent' or value <= 100))


def telemetry_state(case, runbooks=None):
    """Read the readings alone, independent of any model.

    healthy  every reading is a numeric runbook metric below its gate (no incident)
    single   exactly one runbook family is abnormal
    conflict two or more families are abnormal (always a human handoff)
    missing  no runbook-metric reading at all (thin telemetry)
    invalid  a runbook-metric reading is not a finite number
    """
    runbooks = runbooks or dataset()['runbooks']
    metrics = {r['metric']: r for r in runbooks}
    abnormal = sorted({r['id'] for r in runbooks if any(corroborates(e, r) for e in case['evidence'])})
    relevant = [e for e in case['evidence'] if e['metric'] in metrics]
    invalid = [e['id'] for e in relevant
               if type(e['value']) not in (int, float) or not math.isfinite(e['value'])]
    if len(abnormal) > 1:
        state = 'conflict'
    elif abnormal:
        state = 'single'
    elif invalid:
        state = 'invalid'
    elif relevant:
        state = 'healthy'
    else:
        state = 'missing'
    readings = []
    for e in case['evidence']:
        book = metrics.get(e['metric'])
        readings.append({'id': e['id'], 'family': book['id'] if book else None,
                         'gate': book['minimum'] if book else None,
                         'abnormal': bool(book and corroborates(e, book)),
                         'numeric': type(e['value']) in (int, float)})
    return {'state': state, 'abnormal_families': abnormal, 'invalid_ids': invalid, 'readings': readings}


def rules_decision(case, runbooks=None):
    """Rules-only baseline: the single abnormal family, otherwise hand off. Reads no text."""
    t = telemetry_state(case, runbooks)
    return t['abnormal_families'][0] if t['state'] == 'single' else None
