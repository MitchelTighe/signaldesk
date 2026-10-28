"""Real Chromium controls, gallery and axe audits of the generated showcase."""
import argparse
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ENTRY = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--axe', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    contract = json.loads((ENTRY/'fixtures/walkthrough.json').read_text())
    data = json.loads((ENTRY/'site/showcase/replay.json').read_text())
    checks, audits, errors, requests = [], [], [], []
    def check(ok, label):
        assert ok, label
        checks.append(label)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, chromium_sandbox=True,
                                   args=['--disable-dev-shm-usage', '--disable-background-networking'])
        context = browser.new_context(viewport={'width':1280, 'height':900},
                                      color_scheme='dark', reduced_motion='reduce')
        # Enforce rather than merely observe: the app must work without network.
        context.route('**/*', lambda route: route.abort()
                      if route.request.url.startswith(('http:', 'https:')) else route.continue_())
        page = context.new_page()
        page.on('request', lambda r: requests.append(r.url)
                if r.url.startswith(('http:', 'https:', 'ws:', 'wss:')) else None)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.goto((ENTRY/'site/showcase/index.html').as_uri())
        for model in data['models']:
            page.locator('#model').select_option(model)
            for step in contract['steps']:
                page.locator('#case').select_option(step['case_id'])
                check(page.locator('#case-id').inner_text() == step['case_id'],
                      model.split('/')[1] + ': ' + step['id'])
                label = page.locator('#status').inner_text().lower()
                check(label.startswith('do this') if step['status'] == 'supported-hypothesis'
                      else label in ('hand off to a person', 'no incident'), step['id']+' status')
                if step['status'] == 'needs-human':
                    check(page.locator('#steps li').count() == 0, step['id']+' zero steps')
                if step['outcome'] in ('error', 'not-run'):
                    check(('ERROR' if step['outcome'] == 'error' else 'NOT RUN')
                          in page.locator('#outcome').inner_text(), step['id']+' explicit degraded label')
        page.locator('#model').select_option(data['models'][0])
        check(page.locator('#errors').inner_text() == '2 / 1', 'error and not-run counts stay visible')
        page.locator('#filter').select_option('handoff')
        check(0 < page.locator('#case option').count() < len({r['case_id'] for r in data['rows']}), 'handoff filter')
        page.locator('#filter').select_option('all')
        page.locator('#search').fill('D15')
        check(page.locator('#case option').count() == 1, 'search resolves Unicode fixture')
        page.locator('#search').fill('no-such-ticket')
        check(page.locator('#empty').is_visible() and page.locator('#brief').is_hidden(),
              'empty search hides stale brief')
        check(page.locator('#empty').get_attribute('role') == 'status', 'empty result announcement')
        page.locator('#search').fill('')
        page.locator('#case').select_option('D01')
        page.locator('#next').click()
        check(page.locator('#case').input_value() == 'D02', 'next')
        page.locator('#previous').click()
        check(page.locator('#case').input_value() == 'D01', 'previous')
        page.locator('#case').select_option('H05')
        page.locator('#source-link').click()
        check(page.locator('#source').is_visible(), 'source visible')
        page.locator('#steps a').first.click()
        check(page.evaluate('location.hash') == '#source-step-1', 'step anchor resolves')
        with page.expect_download() as event:
            page.locator('#download-evidence').click()
        download = event.value
        download.save_as(args.output/'download.json')
        check(json.loads((args.output/'download.json').read_text()) == data, 'download equals revalidated dataset')
        page.locator('#decision').click()
        page.keyboard.press('/')
        check(page.locator('#search').evaluate('e=>e===document.activeElement'), 'slash focuses search')
        page.goto((ENTRY/'site/showcase/index.html').as_uri())
        page.keyboard.press('Tab')
        check(page.locator('.skip').evaluate('e=>e===document.activeElement'), 'skip link first')
        page.keyboard.press('Enter')
        check(page.evaluate('location.hash') == '#decision', 'skip link reaches brief')
        check(page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"),
              'reduced motion preference enabled')
        axe = args.axe.read_text()
        for theme in ('dark', 'light'):
            if page.evaluate('document.documentElement.dataset.theme') != theme:
                page.locator('#theme').click()
            check(page.evaluate('document.documentElement.dataset.theme') == theme, theme+' control')
            for width in (1280, 390, 320):
                page.set_viewport_size({'width':width, 'height':900})
                for state, cid in [('supported','H05'), ('handoff','H35'), ('error','D16'),
                                   ('long-text','D15'), ('empty','')]:
                    page.locator('#search').fill('')
                    if cid:
                        page.locator('#case').select_option(cid)
                    else:
                        page.locator('#search').fill('no-such-ticket')
                    check(not page.evaluate('document.documentElement.scrollWidth > innerWidth'),
                          f'{theme}/{width}/{state}: no overflow')
                    page.evaluate(axe)
                    audit = page.evaluate("""async()=>await axe.run(document,{
                        runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})""")
                    audits.append({'theme':theme,'width':width,'state':state,
                                   'violations':audit['violations'],'incomplete':audit['incomplete'],
                                   'passes':len(audit['passes'])})
                    if width in (1280, 390) and state in ('supported','handoff','error'):
                        page.locator('#search').evaluate('e=>e.blur()')
                        page.screenshot(path=str(args.output/f'{theme}-{width}-{state}.png'), full_page=True)
                        if width == 390:
                            page.locator('#decision').evaluate("e=>e.scrollIntoView({block:'start'})")
                        else:
                            page.evaluate('window.scrollTo(0,0)')
                        page.screenshot(path=str(args.output/f'gallery-{theme}-{width}-{state}.png'))
                    print(f'AUDIT {theme} {width} {state}: {len(audit["violations"])} violations', flush=True)
        # 200% layout equivalent: halve a 1280px CSS viewport.
        page.locator('#search').fill('')
        page.locator('#case').select_option('D15')
        page.set_viewport_size({'width':640, 'height':450})
        check(not page.evaluate('document.documentElement.scrollWidth > innerWidth'),
              '200% equivalent CSS reflow; long text')
        check(requests == [], 'zero external page requests')
        check(errors == [], 'zero console/page errors')
        report = {'browser':browser.version, 'checks':checks, 'audits':audits,
                  'axe_sha256':hashlib.sha256(axe.encode()).hexdigest(),
                  'violations_total':sum(len(a['violations']) for a in audits),
                  'external_requests':requests, 'errors':errors,
                  'limits':'Automated checks only; no physical device or screen-reader user study.'}
        (args.output/'showcase-results.json').write_text(json.dumps(report, indent=2)+'\n')
        browser.close()
        assert report['violations_total'] == 0, 'axe violations; inspect report'
        print(f'{len(checks)} checks; {len(audits)} audits; zero violations')


if __name__ == '__main__':
    main()
