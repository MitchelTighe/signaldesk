import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { chromium as playwright } from 'playwright';
import chromium from '@sparticuz/chromium';
import { resources } from './resources.mjs';

const documentURL = 'https://signaldesk.test/signaldesk/';
const endpoint = 'https://proxy.signaldesk.test/api/live';
const original = await readFile(new URL('../site/index.html', import.meta.url), 'utf8');

test('browser keeps cached cases instant, sends only explicit live input, and labels fallback', async () => {
  const browser = await playwright.launch({ executablePath: await chromium.executablePath(), args: chromium.args.filter(arg => !['--disable-web-security', '--allow-running-insecure-content', '--disable-site-isolation-trials'].includes(arg)), headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [], requests = [], submissions = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => requests.push(r.url()));
    let limited = false;
    await page.route('**/*', async route => {
      const request = route.request();
      if (request.url() === documentURL) return route.fulfill({ contentType: 'text/html', body: original
        .replace('name="signaldesk-live-endpoint" content=""', `name="signaldesk-live-endpoint" content="${endpoint}"`)
        .replace("connect-src 'none'", 'connect-src https://proxy.signaldesk.test') });
      if (request.url() !== endpoint) throw Error('Unexpected external request: ' + request.url());
      const cors = { 'Access-Control-Allow-Origin': 'https://signaldesk.test',
        'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST' };
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
      submissions.push(request.postDataJSON());
      if (limited) return route.fulfill({ status: 429, headers: cors, contentType: 'application/json',
        body: JSON.stringify({ mode: 'replay', reason: 'ip-limit' }) });
      const book = resources.runbooks.find(b => b.id === 'RB-MOUNT');
      return route.fulfill({ status: 200, headers: cors, contentType: 'application/json', body: JSON.stringify({
        mode: 'live', path: 'escalated-to-super', escalation: 'telemetry-abstention', latency_ms: 42,
        result: { runbook_id: book.id, steps: [{ source: book.id, step: 1, text: book.steps[0] }] },
        trace: [{ model: 'nvidia/Nemotron-3_5-Lightning', validator: 'veto', code: 'telemetry-abstention',
          latency_ms: 20, usage: { prompt_tokens: 1000, completion_tokens: 80 } },
          { model: 'nvidia/nemotron-3-super-120b-a12b', validator: 'accept', code: 'backed',
            latency_ms: 22, usage: { prompt_tokens: 1000, completion_tokens: 90 } }]
      }) });
    });
    await page.goto(documentURL);
    const initialLiveText = await page.locator('#live-result').textContent();
    const cached = await page.locator('#hypothesis').textContent();
    const evidence = await page.locator('#replay-data').textContent();
    assert.equal(submissions.length, 0);
    assert.equal(requests.filter(x => x === endpoint).length, 0);
    await page.locator('#live-open').click();
    assert.equal(await page.locator('#try-readings').getAttribute('open'), '');
    await page.locator('#try-load_wait_seconds').fill('120');
    await page.locator('#live-ticket').fill('Synthetic loading incident; no actions tried.');
    await page.locator('#live-run').click();
    await page.waitForFunction(() => document.querySelector('#live-result').dataset.state === 'live');
    assert.equal(submissions.length, 1);
    assert.deepEqual(submissions[0], { ticket: 'Synthetic loading incident; no actions tried.',
      evidence: [{ id: 'try-load_wait_seconds', metric: 'load_wait_seconds', value: 120 }] });
    assert.match(await page.locator('#live-result').textContent(), /LIVE NEBIUS RESULT/);
    assert.match(await page.locator('#live-trace').textContent(), /veto.*1000 in \/ 80 out/);
    assert.match(await page.locator('#live-trace').textContent(), /Super|super/);
    assert.equal(await page.locator('#hypothesis').textContent(), cached);
    assert.equal(await page.locator('#replay-data').textContent(), evidence);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.locator('#why-link').click();
    assert.equal(await page.locator('#why').evaluate(node => node.open), true);
    assert.equal(await page.locator('#evidence').isVisible(), true);
    assert.ok(page.url().endsWith('#why'));
    await page.locator('#tour-start').click();
    assert.equal(await page.locator('#case').inputValue(), 'H05');
    assert.equal(await page.locator('#try-readings').evaluate(node => node.open), false);
    assert.equal(await page.locator('#why').evaluate(node => node.open), false);
    assert.equal(await page.locator('#live-result').textContent(), initialLiveText);
    assert.equal(await page.locator('#live-result').getAttribute('data-state'), null);
    assert.equal(await page.locator('#live-cascade').isVisible(), false);
    assert.equal(await page.locator('#live-flow li').count(), 0);
    assert.equal(await page.locator('#live-trace').textContent(), '');
    assert.equal(await page.locator('#live-export').isVisible(), false);
    assert.equal(await page.locator('#live-status').textContent(), 'Recorded replay');
    await page.locator('#tour-stop').click();
    await page.locator('#live-open').click();
    limited = true;
    await page.locator('#live-run').click();
    await page.waitForFunction(() => document.querySelector('#live-result').dataset.state === 'replay');
    assert.match(await page.locator('#live-result').textContent(), /ip-limit.*recorded replay.*no live answer/);
    assert.equal(await page.locator('#hypothesis').textContent(), cached);
    assert.equal(await page.locator('#live-run').isEnabled(), true);
    assert.deepEqual(errors, []);
    await page.unroute('**/*');
    requests.length = 0;
    await page.route('**/*', route => route.fulfill({ contentType: 'text/html', body: original }));
    await page.goto(documentURL);
    await page.locator('#live-open').click(); await page.locator('#live-run').click();
    assert.match(await page.locator('#live-result').textContent(), /not deployed.*recorded replay/);
    assert.deepEqual(requests, [documentURL]);

  } finally { await browser.close(); }
});
