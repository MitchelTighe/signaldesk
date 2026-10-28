"""Exercise editable readings against the real Python validator, entirely offline.

Run only in the pinned, sandbox-capable browser container:
    python tests/readings_browser.py --output /out/readings --site site/index.html
No inference provider is imported or called. Numeric fixtures pair browser strings
with explicit Python values; there is deliberately no second input parser oracle.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import traceback

from playwright.sync_api import sync_playwright

ENTRY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENTRY))
from signaldesk.core import dataset, validate_selection
from signaldesk.telemetry import telemetry_state


# Literal boundary pairs keep parsing expectations independent of the browser's
# implementation. Family IDs, metrics, thresholds and authored steps are checked
# against the actual dataset below, rather than a browser-generated answer.
BOUNDARIES = [
    ('RB-CLEAN', 'tapealert_cleaning_flags', [('0', 0), ('1', 1), ('2', 2)]),
    ('RB-MEDIA', 'tapealert_media_flags', [('0', 0), ('1', 1), ('2', 2)]),
    ('RB-HWFAULT', 'tapealert_hardware_flags', [('0', 0), ('1', 1), ('2', 2)]),
    ('RB-MOUNT', 'load_wait_seconds', [('119.999', 119.999), ('120', 120), ('120.001', 120.001)]),
    ('RB-INVENTORY', 'inventory_mismatch_count', [('0', 0), ('1', 1), ('2', 2)]),
    ('RB-LTFS', 'ltfs_mount_errors', [('0', 0), ('1', 1), ('2', 2)]),
    ('RB-PATH', 'scsi_unit_attention_count', [('2', 2), ('3', 3), ('4', 4)]),
    ('RB-WRITEPROT', 'write_protect_rejections', [('0', 0), ('1', 1), ('2', 2)]),
]
CLEAN = 'tapealert_cleaning_flags'
MOUNT = 'load_wait_seconds'
MEDIA = 'tapealert_media_flags'


def matrix(metrics):
    """Values are (text typed into the input, actual Python evidence value)."""
    rows = [
        ('missing', {}),
        ('whitespace omitted', {CLEAN: (' \t ', None), MOUNT: ('  ', None)}),
        ('one zero is healthy', {CLEAN: ('0', 0)}),
        ('all zero is healthy', {metric: ('0', 0) for metric in metrics}),
    ]
    for family, metric, pairs in BOUNDARIES:
        for position, pair in zip(('below', 'exact', 'above'), pairs):
            rows.append((family + ' ' + position, {metric: pair}))
    rows += [
        ('decimal below load gate', {MOUNT: ('119.9990', 119.999)}),
        ('decimal exact load gate', {MOUNT: ('120.0', 120.0)}),
        ('scientific exact load gate', {MOUNT: ('1.2e2', 120.0)}),
        ('scientific small healthy', {MOUNT: ('1e-2', 0.01)}),
        ('scientific uppercase signed', {MOUNT: ('+1.2E+2', 120.0)}),
        ('padded finite number', {CLEAN: (' 1 ', 1)}),
        ('leading decimal', {CLEAN: ('.5', 0.5)}),
        ('trailing decimal', {CLEAN: ('1.', 1.0)}),
        ('negative count follows canonical healthy', {CLEAN: ('-1', -1)}),
        ('negative zero', {CLEAN: ('-0', 0)}),
        ('two abnormal families', {CLEAN: ('1', 1), MOUNT: ('120', 120)}),
        ('three abnormal families', {CLEAN: ('1', 1), MOUNT: ('120', 120), MEDIA: ('1', 1)}),
        ('single outranks invalid', {CLEAN: ('1', 1), MOUNT: ('NaN', 'NaN')}),
        ('conflict outranks invalid', {CLEAN: ('1', 1), MOUNT: ('120', 120), MEDIA: ('bad', 'bad')}),
        ('invalid outranks healthy', {CLEAN: ('bad', 'bad'), MOUNT: ('0', 0)}),
        ('invalid IDs retain metric order', {CLEAN: ('bad', 'bad'), MOUNT: ('NaN', 'NaN')}),
    ]
    for raw in ['NaN', 'Infinity', '-Infinity', 'not a number', '0x78',
                '120seconds', '1e', '1e309', '0b11', '0o10', '1_000']:
        rows.append(('invalid literal ' + raw, {MOUNT: (raw, raw)}))
    return rows


def make_case(values, metrics):
    return {'id': 'browser-readings', 'title': 'Synthetic browser test', 'text': '',
            'evidence': [{'id': 'try-' + metric, 'metric': metric, 'value': values[metric][1]}
                         for metric in metrics
                         if metric in values and values[metric][1] is not None]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--site', type=Path, default=ENTRY / 'site/index.html')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    books = dataset()['runbooks']
    by_id = {book['id']: book for book in books}
    metrics = [book['metric'] for book in books]
    checks, external, errors, storage_calls, cases = [], [], [], [], []
    browser_version = None
    failure = None

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
        print('PASS', label, flush=True)

    def source_manifest():
        paths = ['tests/readings_browser.py', 'signaldesk/core.py', 'signaldesk/telemetry.py',
                 'signaldesk/data.json', 'web/replay-template.html']
        manifest = {name: hashlib.sha256((ENTRY / name).read_bytes()).hexdigest()
                    for name in paths}
        manifest['site_under_test'] = hashlib.sha256(args.site.read_bytes()).hexdigest()
        return manifest

    manifest = source_manifest()
    try:
        with sync_playwright() as playwright:
            # Match replay_browser.py: the browser sandbox remains enabled.
            browser = playwright.chromium.launch(headless=True, chromium_sandbox=True,
                args=['--disable-dev-shm-usage', '--disable-background-networking'])
            browser_version = browser.version
            context = browser.new_context(viewport={'width': 1280, 'height': 960}, reduced_motion='reduce')
            context.add_init_script("""(() => {
                window.__readingsStorageCalls = [];
                for (const method of ['setItem', 'removeItem', 'clear']) {
                    const original = Storage.prototype[method];
                    Storage.prototype[method] = function(...args) {
                        window.__readingsStorageCalls.push('Storage.' + method);
                        return original.apply(this, args);
                    };
                }
                for (const method of ['open', 'deleteDatabase']) {
                    const original = IDBFactory.prototype[method];
                    IDBFactory.prototype[method] = function(...args) {
                        window.__readingsStorageCalls.push('indexedDB.' + method);
                        return original.apply(this, args);
                    };
                }
            })();""")

            def request_route(route):
                url = route.request.url
                if not url.startswith(('file:', 'data:', 'blob:')):
                    external.append(url)
                    route.abort()
                else:
                    route.continue_()

            context.route('**/*', request_route)
            page = context.new_page()
            page.set_default_timeout(5000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
            page.on('websocket', lambda socket: external.append(socket.url))
            try:
                page.goto(args.site.resolve().as_uri())
                check(page.locator('details#try-readings').count() == 1,
                      'editable readings panel exists: details#try-readings (required acceptance surface)')
                page.locator('#try-readings > summary').click()
                panel = page.locator('#try-readings')
                check(panel.get_attribute('open') is not None, 'readings summary opens the actual editor')
                check(page.locator('#try-readings input[data-metric]').count() == 8,
                      'eight editable metric inputs are present')
                actual_metrics = page.locator('#try-readings input[data-metric]').evaluate_all(
                    '(nodes) => nodes.map(n => n.dataset.metric)')
                check(actual_metrics == metrics, 'editor metric order matches original Python dataset')
                for metric in metrics:
                    field = page.locator('input[data-metric="' + metric + '"]')
                    check(field.get_attribute('type') == 'text' and field.is_editable(),
                          metric + ' accepts editable text including invalid numeric literals')
                check(json.loads(page.locator('#replay-data').text_content())['runbooks'] == books,
                      'embedded authored runbooks match Python dataset exactly')
                data_before = page.locator('#replay-data').text_content()
                rows_before = json.loads(data_before)['rows']
                hypothesis_before = page.locator('#hypothesis').text_content()
                options = page.locator('#try-book option').evaluate_all('(nodes) => nodes.map(n => n.value)')
                check(options == [''] + [book['id'] for book in books], 'proposal selector has empty default and eight real runbooks')
                check(page.locator('#try-book').input_value() == '', 'no proposed runbook is selected by default')
                check(page.locator('#try-step-text').is_editable(), 'proposed instruction is editable')
                disclosure = panel.inner_text().lower()
                check('validator only' in disclosure and 'no model call' in disclosure,
                      'editor explicitly discloses validator only and no model call')
                check(('0 actions' in disclosure or 'zero actions' in disclosure)
                      and ('limit' in disclosure or 'caveat' in disclosure),
                      'editor discloses limitations and zero actions')

                previous = {}

                def fill_values(values):
                    for metric in metrics:
                        raw = values.get(metric, ('', None))[0]
                        if previous.get(metric) != raw:
                            page.locator('input[data-metric="' + metric + '"]').fill(raw)
                            previous[metric] = raw

                def compare(values, family, step_number, text, label):
                    case = make_case(values, metrics)
                    expected = telemetry_state(case, books)
                    page.locator('#try-check').click()
                    actual = page.locator('#try-result').evaluate('(n) => ({state:n.dataset.state, families:n.dataset.families, invalidIds:n.dataset.invalidIds})')
                    check(actual['state'] == expected['state'], label + ': state agrees with Python telemetry_state')
                    check(json.loads(actual['families']) == expected['abnormal_families'], label + ': abnormal families agree with Python')
                    check(json.loads(actual['invalidIds']) == expected['invalid_ids'], label + ': invalid evidence IDs agree with Python')
                    if family:
                        accepted, _ = validate_selection({'runbook_id': family,
                            'evidence_ids': [e['id'] for e in case['evidence']]}, case, books)
                        exact_step = 1 <= step_number <= len(by_id[family]['steps']) and text == by_id[family]['steps'][step_number - 1]
                        proposal = 'backed' if accepted and exact_step else 'vetoed'
                    else:
                        proposal = 'no-proposal'
                    check(page.locator('#try-proposal').get_attribute('data-state') == proposal,
                          label + ': proposal agrees with core.validate_selection and exact authored step')
                    cases.append({'label': label, 'state': expected['state'],
                                  'families': expected['abnormal_families'],
                                  'invalid_ids': expected['invalid_ids'], 'proposal': proposal})

                fill_values({})
                compare({}, None, 1, '', 'initial missing readings without a proposal')
                for label, values in matrix(metrics):
                    fill_values(values)
                    expected = telemetry_state(make_case(values, metrics), books)
                    family = (expected['abnormal_families'] or [books[0]['id']])[0]
                    page.locator('#try-book').select_option(family)
                    page.locator('#try-step-number').select_option('1')
                    text = by_id[family]['steps'][0]
                    page.locator('#try-step-text').fill(text)
                    compare(values, family, 1, text, label)

                clean_values = {CLEAN: ('1', 1)}
                fill_values(clean_values)
                for book in books:
                    page.locator('#try-book').select_option(book['id'])
                    step_options = page.locator('#try-step-number option').evaluate_all('(nodes) => nodes.map(n => n.value)')
                    check(step_options == [str(i) for i in range(1, len(book['steps']) + 1)],
                          book['id'] + ': actual authored steps use one-based proposal numbering')
                    page.locator('#try-step-number').select_option('1')
                    page.locator('#try-step-text').fill(book['steps'][0])
                    compare(clean_values, book['id'], 1, book['steps'][0], 'correct or wrong book ' + book['id'])

                clean_book = by_id['RB-CLEAN']
                page.locator('#try-book').select_option(clean_book['id'])
                for number, text in enumerate(clean_book['steps'], 1):
                    page.locator('#try-step-number').select_option(str(number))
                    check(text in page.locator('#try-reference').text_content(),
                          'reference shows authored cleaning step ' + str(number) + ' as literal text')
                    page.locator('#try-step-text').fill('edited before copying')
                    page.locator('#try-use-step').click()
                    check(page.locator('#try-step-text').input_value() == text,
                          'copy reference inserts exact authored step ' + str(number))
                    compare(clean_values, 'RB-CLEAN', number, text, 'copied exact step ' + str(number))
                page.locator('#try-step-number').select_option('1')
                original = clean_book['steps'][0]
                for label, text in [('blank step', ''), ('edited step', original + ' edited'),
                                    ('trailing whitespace step', original + ' '),
                                    ('wrong numbered step', clean_book['steps'][1]),
                                    ('injected markup step', '<img src="https://invalid.example/pixel" onerror="window.__readingsInjected=true">')]:
                    page.locator('#try-step-text').fill(text)
                    compare(clean_values, 'RB-CLEAN', 1, text, label)
                check(page.evaluate('window.__readingsInjected === undefined'), 'typed markup remains inert')
                check(page.locator('#try-readings img').count() == 0, 'proposed instruction is never rendered as HTML')
                page.locator('#try-step-text').fill(original)
                compare(clean_values, 'RB-CLEAN', 1, original, 'manually typed exact authored step accepted')
                fill_values({CLEAN: ('0', 0)})
                compare({CLEAN: ('0', 0)}, 'RB-CLEAN', 1, original, 'check recomputes edited readings and removes stale backing')
                page.locator('#try-book').select_option('')
                compare({CLEAN: ('0', 0)}, None, 1, original, 'empty selection explicitly has no proposal')
                page.locator('#try-reset').click()
                previous.clear()
                check(all(page.locator('input[data-metric="' + metric + '"]').input_value() == '' for metric in metrics),
                      'reset clears every reading input')
                check(page.locator('#try-book').input_value() == '' and page.locator('#try-step-text').input_value() == '',
                      'reset clears proposed runbook and text')
                check(page.locator('#try-result').get_attribute('data-state') == 'missing'
                      and page.locator('#try-proposal').get_attribute('data-state') == 'no-proposal',
                      'reset clears old telemetry and backed status immediately')
                compare({}, None, 1, '', 'reset result remains missing on check')

                fill_values(clean_values)
                page.locator('#try-book').select_option('RB-CLEAN')
                page.locator('#try-step-number').select_option('1')
                page.locator('#try-use-step').click()
                compare(clean_values, 'RB-CLEAN', 1, original, 'responsive backed example')
                for width in [1280, 768, 390, 320]:
                    page.set_viewport_size({'width': width, 'height': 844})
                    check(not page.evaluate('document.documentElement.scrollWidth > innerWidth'),
                          'no page horizontal overflow with open readings at %dpx' % width)
                    check(not panel.evaluate('(n) => n.scrollWidth > n.clientWidth'),
                          'no readings panel horizontal overflow at %dpx' % width)
                    if width in [390, 320]:
                        controls = panel.locator('summary, input, select, textarea, button')
                        for index in range(controls.count()):
                            control = controls.nth(index)
                            if control.is_visible():
                                box = control.bounding_box()
                                check(box['height'] >= 44 and box['width'] >= 44,
                                      '%dpx touch target %s is at least 44px' % (width, control.get_attribute('id') or control.get_attribute('data-metric') or 'summary'))
                check(page.locator('#replay-data').text_content() == data_before
                      and json.loads(page.locator('#replay-data').text_content())['rows'] == rows_before,
                      'editable tools leave embedded recorded replay rows byte-unchanged')
                check(page.locator('#hypothesis').text_content() == hypothesis_before,
                      'editable tools leave the recorded incident hypothesis unchanged')
                check(not page.evaluate('localStorage.length || sessionStorage.length'), 'no local or session storage entries')
                check(context.cookies() == [], 'no cookies created')
                storage_calls.extend(page.evaluate('window.__readingsStorageCalls'))
                check(storage_calls == [], 'no browser storage writes or IndexedDB opens')
                check(external == [], 'zero external page requests or WebSockets')
                check(errors == [], 'zero browser console errors')
            finally:
                # Save both review surfaces even on a meaningful missing-panel red.
                for width in [1280, 390]:
                    page.set_viewport_size({'width': width, 'height': 844})
                    page.screenshot(path=str(args.output / ('readings-%d.png' % width)), full_page=True)
                browser.close()
    except Exception:
        failure = traceback.format_exc()
        raise
    finally:
        report = {'status': 'failed' if failure else 'passed', 'failure': failure,
                  'checks_passed': len(checks), 'checks': checks, 'cases': cases,
                  'external_requests': external, 'console_errors': errors, 'storage_calls': storage_calls,
                  'browser': browser_version, 'playwright': importlib.metadata.version('playwright'),
                  'source_sha256': manifest,
                  'surface': 'local file; sandboxed Chromium; Python telemetry_state and core.validate_selection oracles',
                  'screenshots': sorted(path.name for path in args.output.glob('readings-*.png'))}
        (args.output / 'readings-browser-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('%d readings browser checks passed' % len(checks))


if __name__ == '__main__':
    main()
