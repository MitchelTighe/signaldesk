"""Offline axe + judge-tour acceptance inside a browser container."""
import argparse
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ENTRY = Path(__file__).parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--axe', type=Path, default=Path('/opt/axe.min.js'))
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results, checks, requests, errors = [], [], [], []
    def check(ok, name):
        assert ok, name
        checks.append(name)
    axe = args.axe.read_text()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, chromium_sandbox=True,
            args=['--disable-dev-shm-usage', '--disable-background-networking'])
        page = browser.new_page(viewport={'width':1280, 'height':900}, reduced_motion='reduce')
        page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('http:', 'https:', 'ws:', 'wss:')) else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.goto((ENTRY/'site/index.html').resolve().as_uri())
        for width in (1280, 390, 320):
            page.set_viewport_size({'width':width, 'height':900})
            for state in ('landing', 'supported', 'handoff', 'tour'):
                if state == 'supported': page.locator('#case').select_option('H05')
                if state == 'handoff': page.locator('#case').select_option('H35')
                if state == 'tour':
                    page.locator('#tour-start').click()
                    page.locator('#tour-pause').click()
                    page.locator('#source-link').click()
                    source = page.locator('#source').bounding_box()
                    tour = page.locator('#tour').bounding_box()
                    check(source['y'] >= -1 and tour['y'] + tour['height'] <= source['y'] + 1, f'{width}px tour source is not covered by controls')
                    page.locator('#tour').evaluate("e=>e.scrollIntoView({block:'start'})")
                check(not page.evaluate('document.documentElement.scrollWidth > innerWidth'), f'{width}px {state}: no horizontal overflow')
                print('AUDIT', width, state, flush=True)
                page.evaluate(axe)
                result = page.evaluate("async () => await Promise.race([axe.run(document, {runOnly: {type:'tag', values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}), new Promise((_, reject)=>setTimeout(()=>reject(new Error('axe audit exceeded 30 seconds')),30000))])")
                results.append({'width':width, 'state':state, 'violations':result['violations'],
                                'incomplete':result['incomplete'], 'passes':len(result['passes'])})
                page.screenshot(path=str(args.output/f'{width}-{state}.png'), full_page=True)
                if state == 'tour': page.locator('#tour-stop').click()
        axe_version = page.evaluate('axe.version')
        page.close()
        page = browser.new_page(viewport={'width':1280,'height':900}, reduced_motion='reduce')
        page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('http:', 'https:', 'ws:', 'wss:')) else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.clock.install()  # Before page code runs; axe uses a separate page with real timers.
        page.goto((ENTRY/'site/index.html').resolve().as_uri())
        page.locator('#tour-start').focus()
        page.keyboard.press('Enter')
        check(page.locator('#case').input_value() == 'H05', 'keyboard start opens supported scene')
        check(page.locator('#tour-pause').evaluate('e=>e===document.activeElement'), 'start places focus on pause')
        page.clock.fast_forward(6000)
        check(page.locator('#case').input_value() == 'X06', 'automatic scene two shows the veto')
        page.locator('#tour-pause').click()
        page.clock.fast_forward(14000)
        check(page.locator('#case').input_value() == 'X06', 'pause stops scene changes')
        page.locator('#tour-pause').click()
        page.clock.fast_forward(6000)
        check(page.locator('#case').input_value() == 'X02', 'resume shows the caveat handoff')
        page.clock.fast_forward(6000)
        check(page.locator('#case').input_value() == 'H35', 'scene four shows the conflicting capture')
        page.clock.fast_forward(6000)
        check(page.locator('#case').input_value() == 'X01' and 'NO INCIDENT' in page.locator('#status').inner_text().upper(), 'scene five shows a quiet library')
        page.clock.fast_forward(6000)
        check('Walkthrough complete' in page.locator('#tour-text').inner_text(), 'five six-second scenes complete within 30 seconds')
        page.locator('#tour-stop').click()
        check(page.locator('#tour-start').evaluate('e=>e===document.activeElement'), 'exit restores focus')
        check(page.locator('aside').is_visible(), 'exit restores full controls')
        page.locator('#tour-start').click()
        page.locator('#tour-next').click()
        check(page.locator('#case').input_value()=='X06', 'manual next works')
        page.locator('#tour-stop').click()
        page.keyboard.press('Tab')
        check(page.locator('#model').evaluate('e=>e===document.activeElement'), 'keyboard reaches model control')
        check(requests == [], 'zero external page requests')
        check(errors == [], 'zero console/page errors')
        report = {'browser':browser.version, 'axe_version':axe_version,
                  'axe_sha256':hashlib.sha256(axe.encode()).hexdigest(), 'checks':checks,
                  'audits':results, 'external_requests':requests, 'errors':errors,
                  'violations_total':sum(len(r['violations']) for r in results),
                  'scope':'WCAG A/AA automated checks; not full conformance or a screen-reader/user study'}
        (args.output/'a11y-results.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='audits'}, indent=2))
        browser.close()
        assert report['violations_total'] == 0, 'axe violations; see a11y-results.json'

if __name__ == '__main__': main()
