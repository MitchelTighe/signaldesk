"""Build a portable, entirely offline demo from actual Python inference results."""
import json
from pathlib import Path
from .core import brief, corpus, dataset, evaluate, LocalClassifier
from .challenge import challenge_cases, evaluate_challenge


def render():
    data = dataset()
    provider = LocalClassifier(data['runbooks'])
    cases = data['cases'] + corpus('training')['cases'] + corpus('heldout')['cases'] + challenge_cases()
    payload = {'tickets': [{'case': {k:v for k,v in c.items() if k != 'expected'},
                            'split': ('demo' if c in data['cases'] else 'challenge' if c['id'].startswith('P')
                                      else 'heldout' if c['id'].startswith('H') else 'training'),
                            'brief': brief(c, provider)} for c in cases],
               'runbooks': data['runbooks'], 'evaluation': evaluate(), 'challenge': evaluate_challenge(),
               'training_count': len(corpus('training')['cases'])}
    # Escaping '<' prevents a fixture from closing the inert JSON script element.
    packed = json.dumps(payload, separators=(',', ':'), ensure_ascii=True).replace('<', '\\u003c')
    template = Path(__file__).resolve().parents[1] / 'web' / 'template.html'
    return template.read_text(encoding='utf-8').replace('__SIGNALDESK_DATA__', packed)


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / 'web' / 'index.html'
    target.write_text(render(), encoding='utf-8')
    print('Built web/index.html from Python inference; no network, no model call')
