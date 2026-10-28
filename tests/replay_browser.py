"""Playwright acceptance in the pinned browser container; file surface, no internet.
Usage: python tests/replay_browser.py --output /out/screenshots --dashboard /out/fixtures
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright

ENTRY = Path(__file__).parents[1]


def check_reasoning_labels(page, check, model, expected, label):
    page.locator('#model').select_option(model)
    page.locator('#case').select_option('H05')
    answered = page.locator('#answered').text_content()
    index = json.loads(page.locator('#replay-data').text_content())['models'].index(model)
    trace = page.locator('#trace tr').nth(index).locator('td').first.text_content()
    for surface, text in [('answer', answered), ('trace', trace)]:
        if expected is None:
            check('reasoning on' not in text and 'reasoning off' not in text,
                  '%s has no asserted reasoning label in %s' % (label, surface))
        else:
            other = 'off' if expected == 'on' else 'on'
            check('reasoning '+expected in text and 'reasoning '+other not in text,
                  '%s shows reasoning %s in %s' % (label, expected, surface))


def check_unknown_reasoning(browser, data, check, external, errors):
    """Exercise the real template with test-only copies; saved reports stay unchanged."""
    before = deepcopy(data)
    template = (ENTRY/'web/replay-template.html').read_text()
    variants = [('missing',), ('null', None), ('zero', 0), ('one', 1),
                ('string-false', 'false'), ('string-true', 'true'),
                ('empty-string', ''), ('list', []), ('object', {'enabled': True})]
    probe = browser.new_page()
    probe.on('request', lambda request: external.append(request.url) if request.url.startswith(('http:','https:','ws:','wss:')) else None)
    probe.on('pageerror', lambda error: errors.append(str(error)))
    probe.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
    try:
        with tempfile.TemporaryDirectory(prefix='signaldesk-reasoning-test-') as tmp:
            target = Path(tmp)/'unknown-reasoning.html'
            for variant in variants:
                fixture = deepcopy(data)
                for row in fixture['rows']:
                    provenance = (row.get('brief') or {}).get('provenance')
                    if provenance:
                        provenance.pop('thinking', None)
                        if len(variant) == 2:
                            provenance['thinking'] = variant[1]
                packed = json.dumps(fixture).replace('<', '\\u003c')
                target.write_text(template.replace('__REPLAY_DATA__', packed))
                probe.goto(target.resolve().as_uri())
                for model in fixture['models']:
                    check_reasoning_labels(probe, check, model, None,
                                           'test-only %s reasoning for %s' % (variant[0], model))
        check(data == before, 'unknown reasoning browser probes leave original replay data unchanged')
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dashboard', type=Path)
    parser.add_argument('--site', type=Path, default=ENTRY/'site/index.html')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks, external, errors = [], [], []
    def check(value, label):
        if not value: raise AssertionError(label)
        checks.append(label); print('PASS', label, flush=True)
    with sync_playwright() as p:
        # The browser sandbox stays enabled. No --no-sandbox/host install workaround.
        browser = p.chromium.launch(headless=True, chromium_sandbox=True,
                                    args=['--disable-dev-shm-usage','--disable-background-networking'])
        page = browser.new_page(viewport={'width':1280,'height':960}, reduced_motion='reduce', accept_downloads=True)
        page.on('request', lambda request: external.append(request.url) if request.url.startswith(('http:','https:','ws:','wss:')) else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.goto(args.site.resolve().as_uri())
        check(page.title() == 'SignalDesk · Tape incident desk', 'static judge build opens from file')
        data = json.loads(page.locator('#replay-data').text_content())
        live = data['live_recorded']
        check(('RECORDED NEBIUS RUN' if live else 'LOCAL MOCK PREVIEW') in page.locator('#notice').inner_text(),
              'run provenance is prominent and honest')
        check('NVIDIA Nemotron on Nebius Token Factory' in page.locator('header').inner_text(), 'model attribution on screen')
        expected_cases = len({r['case_id'] for r in data['rows']})
        check(page.locator('#case option').count()==expected_cases, 'complete incident set present')
        routed = bool(data.get('routing'))
        check(page.locator('#model option').count()==len(data['models'])+int(routed), 'route plus per-model views available')
        page.locator('#case').select_option('H05')
        check('Drive requests cleaning' in page.locator('#hypothesis').inner_text(), 'supported cleaning hypothesis rendered first')
        check(page.locator('#decision').bounding_box()['y'] < page.locator('#ticket-text').bounding_box()['y'], 'what to do comes before the evidence')
        check(page.locator('#steps li').count()==3, 'three cited runbook steps rendered')
        check('Nebius Token Factory' in page.locator('#answered').inner_text(), 'answering model and platform named on the action')
        page.locator('#why summary').click()
        check('Abnormal' in page.locator('#evidence').inner_text(), 'readings and gates one click down')
        selected_view = page.locator('#model').input_value()
        if live:
            lightning = next(model for model in data['models'] if 'lightning' in model.lower())
            check_reasoning_labels(page, check, lightning, 'off', 'recorded Lightning')
            check_reasoning_labels(page, check, 'nvidia/nemotron-3-super-120b-a12b', 'on', 'recorded Super')
        else:
            for model in data['models']:
                row = next(row for row in data['rows'] if row['model'] == model and row['case_id'] == 'H05')
                thinking = (row.get('brief') or {}).get('provenance', {}).get('thinking')
                expected = 'off' if thinking is False else 'on' if thinking is True else None
                check_reasoning_labels(page, check, model, expected, 'mock '+model)
        check_unknown_reasoning(browser, data, check, external, errors)
        page.locator('#model').select_option(selected_view)
        page.locator('#source-link').click()
        check(page.url.endswith('#source') and 'RB-CLEAN' in page.locator('#source-title').inner_text(), 'citation navigates to source')
        check('does not prove' in page.locator('#caveat').inner_text(), 'source caveat retained')
        check(page.locator('#source-steps li').count()==3, 'complete authored source steps are inspectable')
        page.locator('#steps li:last-child a').click()
        check(page.url.endswith('#source-step-3') and 'cleaning flags have cleared' in page.locator('#source-step-3').inner_text(), 'step citation targets its exact source paragraph')
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(args.output/'replay-1280-supported.png'), full_page=True)
        with page.expect_download() as note:
            page.locator('#export').click()
        text = Path(note.value.path()).read_text()
        check(text.startswith('# SignalDesk incident note: H05') and 'Actions executed by SignalDesk: 0' in text, 'incident note exports locally')
        page.locator('#model').select_option('nvidia/nemotron-3-super-120b-a12b')
        check(page.locator('#case').input_value()=='H05', 'model switch preserves incident comparison')
        check('120b' in page.locator('#provenance-model').text_content(), 'provenance follows model choice')
        page.locator('#case').select_option('H35')
        check('HAND OFF' in page.locator('#status').inner_text().upper(), 'conflicting evidence visibly hands off')
        check(page.locator('#steps li').count()==0 and page.locator('#handoff').is_visible(), 'handoff has empty steps')
        page.screenshot(path=str(args.output/'replay-1280-abstention.png'), full_page=True)
        if routed:
            page.locator('#model').select_option('routed')
            page.locator('#case').select_option('X06')
            check('Validator veto' in page.locator('#vetoes').inner_text() and 'Suspect cartridge' in page.locator('#hypothesis').inner_text(),
                  'veto of a Nemotron claim is shown next to the backed answer')
            page.locator('#case').select_option('X01')
            check('NO INCIDENT' in page.locator('#status').inner_text().upper(), 'quiet telemetry yields no incident')
            page.screenshot(path=str(args.output/'replay-1280-quiet.png'), full_page=True)
            check(page.locator('#eval-tables table').count()==2, 'run receipt compares policies on both sets')
        page.locator('#case').select_option('H39')
        check('Not a number' in page.locator('#evidence').inner_text(), 'invalid telemetry stays explicitly labeled')
        page.locator('#case').select_option('H05')
        for width in [1280,768,390,320]:
            page.set_viewport_size({'width':width,'height':844})
            check(not page.evaluate('document.documentElement.scrollWidth>innerWidth'), 'no horizontal overflow at %dpx'%width)
            if width==390:
                check(page.locator('#case').bounding_box()['height']>=44, '390px selector has a touch-sized target')
                page.screenshot(path=str(args.output/'replay-390-supported.png'), full_page=True)
                page.locator('#case').select_option('H35')
                page.screenshot(path=str(args.output/'replay-390-abstention.png'), full_page=True)
                page.locator('#case').select_option('H05')
        page.set_viewport_size({'width':1280,'height':960})
        page.locator('body').click(position={'x':2,'y':2}); page.keyboard.press('/')
        check(page.locator('#search').evaluate('(e)=>e===document.activeElement'), 'slash keyboard shortcut focuses search')
        page.locator('#search').fill('no-such-fictional-ticket')
        check(page.locator('#empty').is_visible() and not page.locator('#brief').is_visible(), 'empty search hides stale brief')
        page.locator('#search').fill('')
        page.locator('#filter').select_option('handoff')
        check(0 < page.locator('#case option').count() < expected_cases, 'decision filter narrows cases')
        page.locator('#filter').select_option('all'); page.locator('#case').select_option('H01')
        page.locator('#next').click(); check(page.locator('#case').input_value()=='H02', 'next control advances incident')
        page.locator('#previous').click(); check(page.locator('#case').input_value()=='H01', 'previous control returns incident')
        check(page.locator('meta[http-equiv="Content-Security-Policy"]').get_attribute('content').find("connect-src 'none'")>=0, 'CSP forbids API connections')
        check(page.locator('#download-evidence').get_attribute('href').startswith('blob:'), 'download uses embedded sanitized replay data')
        with page.expect_download() as pending:
            page.locator('#download-evidence').click()
        downloaded = json.loads(Path(pending.value.path()).read_text())
        check(downloaded['schema']=='signaldesk-static-replay-v1' and len(downloaded['rows'])==len(data['rows']),
              'browser downloads the complete local replay evidence without an API call')
        check(not page.evaluate('localStorage.length || sessionStorage.length'), 'no browser credential storage')
        page.set_viewport_size({'width':1280,'height':720})
        page.goto((ENTRY/'fixtures/dashboard.html').resolve().as_uri())
        check(page.locator('body').inner_text().find('E-C1 · tapealert_cleaning_flags = 1')>=0, 'vision dashboard visibly contains trusted synthetic observation')
        if args.dashboard:
            args.dashboard.mkdir(parents=True, exist_ok=True)
            target=args.dashboard/'dashboard-clean.png'; page.screenshot(path=str(target))
            (args.dashboard/'dashboard.json').write_text(json.dumps({'case_id':'clean-demo',
                'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'width':1280,'height':720,
                'source':'fixtures/dashboard.html','synthetic_only':True},indent=2)+'\n')
        check(external==[], 'zero external page requests observed')
        check(errors==[], 'zero browser console errors')
        report={'checks_passed':len(checks),'checks':checks,'external_requests':external,'console_errors':errors,
                'browser':browser.version,'playwright':importlib.metadata.version('playwright'),
                'surface':'local file static judge build; sandboxed Chromium; see run report for host isolation',
                'screenshots':sorted(p.name for p in args.output.glob('*.png'))}
        (args.output/'browser-results.json').write_text(json.dumps(report,indent=2)+'\n')
        print('%d replay browser checks passed; Chromium %s; Playwright %s'%(len(checks),browser.version,report['playwright']))
        browser.close()


if __name__=='__main__':main()
