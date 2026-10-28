"""Cost/latency-aware routing, computed from recorded per-case calls of BOTH models.

Policy v2 (fixed on 2026-10-21 after a first hard-split run showed that neither model with
reasoning off, nor the rules-only baseline, applies a runbook caveat; the 40 held-out cases
were re-run afterwards as the check):

1. Deterministic pre-triage reads the readings alone. A conflict (two abnormal families),
   missing or non-numeric telemetry is a human handoff, and an all-normal window is
   "no incident". No model is called: the validator would overrule any proposal anyway.
2. Exactly one abnormal family: Nemotron Lightning (reasoning off) drafts. A
   validated draft for a read-only runbook is final.
3. Nemotron Super (reasoning on) reads the same incident, and its validated
   output is final, when Lightning abstains, is vetoed by the validator, has its draft rejected,
   or proposes a runbook whose steps physically move media or the robot (PHYSICAL below). A
   second, stronger reader is required before anyone is told to move a cartridge.

Cost and latency are summed from the recorded rows (Lightning, plus Super for escalated
cases; pre-triaged cases cost zero). This is a replay of recorded calls, not a separate
cascade run, and it is labelled that way everywhere it is shown.
"""
from decimal import Decimal

from .budget import LIGHTNING, PRICING, SUPER
from .telemetry import rules_decision, telemetry_state

POLICY = 'routing-policy-v2'
PHYSICAL = {'RB-CLEAN': 'loads a cleaning cartridge', 'RB-INVENTORY': 'robot inventory rescan',
            'RB-MEDIA': 'moves the cartridge to a second drive'}
SHORT_CIRCUIT = {'conflict': 'handoff', 'missing': 'handoff', 'invalid': 'handoff', 'healthy': 'no-incident'}


def row_cost(row):
    p = (row.get('brief') or {}).get('provenance') or {}
    usage = p.get('usage')
    if not usage:
        return Decimal(0), 0.0
    rates = PRICING['models'][row['model']]
    usd = (Decimal(str(rates['input'])) * usage['prompt_tokens']
           + Decimal(str(rates['output'])) * usage['completion_tokens']) / 1_000_000
    return usd, float(p.get('elapsed_ms') or 0)


def escalation_reason(row):
    b = row.get('brief') or {}
    if row['outcome'] != 'validated':
        return 'Lightning draft rejected or unavailable'
    if b.get('validation') == 'telemetry-abstention':
        return 'validator vetoed the Lightning proposal'
    if b.get('runbook_id') is None:
        return 'Lightning declined although one family is abnormal'
    if b['runbook_id'] in PHYSICAL:
        return 'physical action (%s) needs a second reader' % PHYSICAL[b['runbook_id']]
    return None


def route(rows, case):
    """Return the routed decision for one case from the recorded per-model rows."""
    by_model = {r['model']: r for r in rows if r['case_id'] == case['id']}
    t = telemetry_state(case)
    if t['state'] in SHORT_CIRCUIT:
        return {'case_id': case['id'], 'path': 'pre-triage', 'telemetry': t['state'],
                'decision': None, 'reason': 'Deterministic pre-triage: ' + SHORT_CIRCUIT[t['state']],
                'usd': 0.0, 'latency_ms': 0.0, 'models_called': []}
    light, sup = by_model.get(LIGHTNING), by_model.get(SUPER)
    if light is None or sup is None:
        raise ValueError('Routing needs recorded rows for both models')
    usd, ms = row_cost(light)
    why = escalation_reason(light)
    if why is None:
        return {'case_id': case['id'], 'path': 'lightning', 'telemetry': t['state'],
                'decision': light['actual'], 'reason': 'Lightning draft backed by the validator',
                'usd': float(usd), 'latency_ms': ms, 'models_called': [LIGHTNING]}
    usd2, ms2 = row_cost(sup)
    return {'case_id': case['id'], 'path': 'escalated-to-super', 'telemetry': t['state'],
            'decision': sup['actual'] if sup['outcome'] == 'validated' else None,
            'reason': 'Escalated: ' + why, 'usd': float(usd + usd2), 'latency_ms': ms + ms2,
            'models_called': [LIGHTNING, SUPER]}


def _summary(decisions, cases, invalid_ids=()):
    expected = {c['id']: c['expected'] for c in cases}
    usd = sum(Decimal(str(d['usd'])) for d in decisions)
    lat = sorted(d['latency_ms'] for d in decisions)
    return {'correct': sum(d['case_id'] not in invalid_ids
                           and d['decision'] == expected[d['case_id']] for d in decisions),
            'total': len(decisions), 'usd': float(usd),
            'latency_p50_ms': lat[(len(lat) - 1) // 2] if lat else None,
            'latency_mean_ms': round(sum(lat) / len(lat), 1) if lat else None,
            'model_calls': sum(len(d.get('models_called', [])) for d in decisions),
            'unsafe_accepts': sum(d['decision'] is not None and expected[d['case_id']] is None
                                  for d in decisions)}


def compare(rows, cases):
    """Routed policy vs each single model vs a rules-only baseline, on the same recorded rows."""
    if {LIGHTNING, SUPER} - {r['model'] for r in rows}:
        return None
    routed = [route(rows, c) for c in cases]
    outcomes = {(r['model'], r['case_id']): r['outcome'] for r in rows}
    invalid_routed = {d['case_id'] for d in routed if d['path'] != 'pre-triage'
                      and outcomes[(LIGHTNING if d['path'] == 'lightning' else SUPER,
                                    d['case_id'])] != 'validated'}
    single = {}
    for model in (LIGHTNING, SUPER):
        decisions = []
        for c in cases:
            r = next(x for x in rows if x['model'] == model and x['case_id'] == c['id'])
            usd, ms = row_cost(r)
            decisions.append({'case_id': c['id'], 'decision': r['actual'], 'usd': float(usd),
                              'latency_ms': ms, 'models_called': [model]})
        invalid = {r['case_id'] for r in rows if r['model'] == model and r['outcome'] != 'validated'}
        single[model] = _summary(decisions, cases, invalid)
    rules = _summary([{'case_id': c['id'], 'decision': rules_decision(c), 'usd': 0.0, 'latency_ms': 0.0,
                       'models_called': []} for c in cases], cases)
    return {'policy': POLICY, 'note': 'Computed from recorded per-case calls of both models; '
            'not a separate cascade run. Latency is the sum of sequential calls.',
            'routed': _summary(routed, cases, invalid_routed), 'lightning_only': single[LIGHTNING],
            'super_only': single[SUPER], 'rules_only': rules,
            'paths': {p: sum(d['path'] == p for d in routed)
                      for p in ('pre-triage', 'lightning', 'escalated-to-super')},
            'cases': routed}


def claims(rows):
    """Per model: runbooks Nemotron proposed, how many the validator backed, how many it vetoed."""
    out = {}
    for model in sorted({r['model'] for r in rows}):
        mine = [r for r in rows if r['model'] == model and r.get('brief')]
        backed = sum(r['brief']['status'] == 'supported-hypothesis' for r in mine)
        vetoed = sum(r['brief'].get('validation') == 'telemetry-abstention' for r in mine)
        rejected = sum(r['brief'].get('validation') == 'rejected-draft' for r in mine)
        out[model] = {'proposed': backed + vetoed, 'backed': backed, 'vetoed': vetoed,
                      'rejected_drafts': rejected,
                      'vetoed_cases': [r['case_id'] for r in mine
                                       if r['brief'].get('validation') == 'telemetry-abstention']}
    return out
