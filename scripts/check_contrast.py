#!/usr/bin/env python3
"""Supplement axe's gradient-incomplete checks with conservative palette bounds."""
import json
from pathlib import Path
import re

ENTRY = Path(__file__).resolve().parents[1]


def luminance(value):
    if len(value) == 4:
        value = '#' + ''.join(c*2 for c in value[1:])
    parts = [int(value[i:i+2],16)/255 for i in (1,3,5)]
    linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in parts]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))


def ratio(a,b):
    values = sorted((luminance(a),luminance(b)))
    return (values[1]+.05)/(values[0]+.05)


def main():
    css = (ENTRY/'web/replay-template.html').read_text()
    dark = dict(re.findall(r'--(bg|panel|muted|ink|green|amber):(#[0-9a-f]{3,6})',
                           re.search(r':root\{([^}]+)',css).group(1)))
    light = dict(re.findall(r'--(bg|panel|muted|ink|green|amber):(#[0-9a-f]{3,6})',
                            re.search(r':root\[data-theme="light"\]\{([^}]+)',css).group(1)))
    checks = []
    # Include all gradient endpoints. Interpolation stays bounded here because
    # every endpoint is darker than every foreground (vice versa for light).
    for theme, palette, backgrounds in [
        ('dark',dark,['#1b3335','#243a29','#142421','#352d20','#23241e','#2d281e']),
        ('light',light,['#eaf5e9','#fff4df']),
    ]:
        for bg in [palette['bg'],palette['panel']]+backgrounds:
            assert bg in css
            for role in ('ink','muted','green','amber'):
                fg = palette[role]
                value = ratio(fg,bg)
                checks.append({'theme':theme,'role':role,'foreground':fg,'background':bg,
                               'ratio':round(value,4)})
    for fg,bg in [('#1a2b13',dark['green']),('#362b15',dark['amber']),
                  ('#ffffff',light['green']),('#ffffff',light['amber'])]:
        checks.append({'theme':'status labels','foreground':fg,'background':bg,
                       'ratio':round(ratio(fg,bg),4)})
    result = {'pairs':checks,'minimum_ratio':min(r['ratio'] for r in checks),
              'normal_text_threshold':4.5,
              'scope':'Conservative palette/gradient endpoint bounds; excludes disabled controls. '
                      'Complements axe incomplete entries, not full WCAG certification.'}
    print(json.dumps(result,indent=2))
    return 0 if result['minimum_ratio'] >= 4.5 else 1


if __name__ == '__main__':
    raise SystemExit(main())
