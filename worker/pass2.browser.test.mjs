import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { chromium as playwright } from 'playwright';
import chromium from '@sparticuz/chromium';
import { resources } from './resources.mjs';

const documentURL = 'https://signaldesk.test/signaldesk/';
const endpoint = 'https://proxy.signaldesk.test/api/live';
const original = await readFile(new URL('../site/index.html', import.meta.url), 'utf8');
const data = JSON.parse(await readFile(new URL('../site/replay.json', import.meta.url), 'utf8'));
const text = (page, selector) => page.locator(selector).textContent();
const select = (page, id) => page.locator('#case').selectOption(id);

// Chromium's executablePath is asynchronous; resolve it before passing launch options.
async function browser() {
  return playwright.launch({ executablePath: await chromium.executablePath(),
    args: chromium.args.filter(arg => !['--disable-web-security', '--allow-running-insecure-content', '--disable-site-isolation-trials'].includes(arg)), headless: true });
}

test('recorded cascade, scoreboard and examples follow evidence at desktop and mobile widths', async () => {
  const b = await browser();
  try {
    const page = await b.newPage({ viewport: { width: 1280, height: 960 }, reducedMotion: 'reduce', colorScheme: 'dark' });
    const errors = [], requests = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/*', route => { requests.push(route.request().url()); return route.fulfill({ contentType: 'text/html', body: original }); });
    await page.goto(documentURL);
    assert.equal(await page.locator('#case').inputValue(), 'X06');
    assert.deepEqual(await page.locator('#case-flow h3').allTextContents(), [
      'Ticket in · X06', 'Nemotron 3.5 Lightning', 'Deterministic validator',
      'Nemotron 3 Super · second reader', 'Deterministic validator', 'Final incident note'
    ]);
    assert.match(await text(page, '#case-flow li:nth-child(2)'), /Drive requests cleaning/);
    assert.equal(await page.locator('#case-flow li:nth-child(3)').getAttribute('data-state'), 'veto');
    assert.match(await text(page, '#case-flow li:nth-child(3)'), /VETO.*lacks corroborating telemetry/s);
    assert.match(await text(page, '#case-flow li:nth-child(4)'), /Suspect cartridge/);
    for (const [index, model] of data.models.entries()) {
      const provenance = data.rows.find(r => r.case_id === 'X06' && r.model === model).brief.provenance;
      const metrics = await text(page, `#case-flow li:nth-child(${index === 0 ? 2 : 4}) .stage-metrics`);
      assert.ok(metrics.includes(provenance.elapsed_ms.toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' ms'));
      assert.ok(metrics.includes(provenance.usage.prompt_tokens.toLocaleString('en-US') + ' in'));
      assert.ok(metrics.includes(provenance.usage.completion_tokens.toLocaleString('en-US') + ' out'));
    }
    assert.equal(await text(page, '#r-actions'), '0');
    assert.equal(await text(page, '#r-vetoed'), String(Object.values(data.claims).reduce((sum, c) => sum + c.vetoed, 0)));
    assert.equal(await text(page, '#r-cost'), '$' + data.routing.routed.usd.toFixed(3));
    assert.equal(await text(page, '#r-accuracy'), `${data.routing.routed.correct}/${data.routing.routed.total}`);
    assert.match(await text(page, '#r-actions-note'), /2 to 0 unsafe recommendations/);
    assert.match(await text(page, '#r-accuracy-note'), /50\/54 to 53\/54/);
    for (const title of await page.locator('.score').evaluateAll(nodes => nodes.map(n => n.title))) assert.match(title, /site\/replay.json/);
    assert.equal(await page.locator('#whats-next #limits').count(), 1);
    assert.match(await text(page, '#whats-next'), /Second-author synthetic check:.*4\/10.*8\/10.*Quality gates failed/);

    const screenshotDir = process.env.PASS2_SCREENSHOTS;
    if (screenshotDir) await mkdir(screenshotDir, { recursive: true });
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: width === 1280 ? 960 : 844 });
      await page.locator('#why-link').click();
      assert.equal(await page.locator('#why').evaluate(node => node.open), true);
      for (const theme of ['dark', 'light']) {
        await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${width}px ${theme} overflow`);
        assert.deepEqual(await page.locator('table').evaluateAll(tables => tables.flatMap(table => {
          const labels = [...table.querySelectorAll('thead th')].map(th => th.textContent);
          return [...table.querySelectorAll('tbody td')].flatMap((cell, i) => {
            const rect = cell.getBoundingClientRect();
            return cell.dataset.label !== labels[i % labels.length] || rect.right > innerWidth || cell.scrollWidth > cell.clientWidth
              ? [cell.textContent] : [];
          });
        })), [], `${width}px ${theme}: labeled cells fit without internal clipping`);
        if (width === 390) {
          assert.equal(await page.locator('#trace td').first().evaluate(cell => getComputedStyle(cell).display), 'block');
          assert.ok((await page.locator('#trace td').first().boundingBox()).width > 250, 'model name has a full card width');
          assert.ok((await page.locator('#trace td[data-label="Draft"]').first().boundingBox()).width > 250, 'runbook ID has a full card width');
          assert.ok((await page.locator('#eval-tables td[data-label="Cost"]').first().boundingBox()).width > 250, 'cost has a full card width');
        }
      }
      await page.evaluate(() => document.documentElement.dataset.theme = 'dark');
      if (screenshotDir) {
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: `${screenshotDir}/replay-${width}.png`, fullPage: true });
        await page.screenshot({ path: `${screenshotDir}/intro-${width}.png` });
        await page.locator('#cascade-panel').scrollIntoViewIfNeeded();
        await page.screenshot({ path: `${screenshotDir}/cascade-${width}.png` });
      }
    }
    await select(page, 'X02');
    assert.equal(await page.locator('#case-flow [data-state="veto"]').count(), 0);
    assert.match(await text(page, '#case-flow li:nth-child(3)'), /PASS.*second reader/is);
    assert.match(await text(page, '#case-flow li:last-child'), /HAND OFF/);
    for (const id of ['X01', 'H35']) {
      await select(page, id);
      assert.equal(await page.locator('#case-flow > li').count(), 3);
      assert.match(await text(page, '#case-flow'), /pre-triage.*No model call/is);
      assert.equal(await page.locator('#case-flow .stage-metrics').count(), 1);
    }
    await select(page, 'H08');
    assert.match(await text(page, '#case-flow'), /VETO.*Model draft rejected/s);
    assert.match(await text(page, '#case-flow li:last-child'), /HAND OFF/);
    const direct = data.routing.cases.find(c => c.path === 'lightning');
    await select(page, direct.case_id);
    assert.equal(await page.locator('#case-flow > li').count(), 4);
    assert.doesNotMatch(await text(page, '#case-flow'), /Nemotron 3 Super/);
    await page.locator('#model').selectOption(data.models[1]);
    assert.doesNotMatch(await text(page, '#case-flow'), /Nemotron 3.5 Lightning/);
    assert.match(await text(page, '#cascade-context'), /only · comparison view/);

    await page.locator('#live-open').click();
    assert.equal(await page.locator('#ticket-examples button').count(), 3);
    for (const index of [0, 1, 2]) {
      await page.locator('#ticket-examples button').nth(index).click();
      assert.ok((await page.locator('#live-ticket').inputValue()).length > 100);
      assert.equal(await page.locator('#ticket-examples button').nth(index).getAttribute('aria-pressed'), 'true');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    }
    await page.locator('#ticket-examples button').first().click();
    if(screenshotDir)for(const width of [1280,390]){
      await page.setViewportSize({width,height:width===1280?960:844});
      await page.locator('#try-readings').evaluate(node=>scrollTo(0,node.getBoundingClientRect().top+scrollY-16));
      await page.screenshot({path:`${screenshotDir}/ticket-${width}.png`});
    }
    assert.equal(await page.locator('#try-tapealert_cleaning_flags').inputValue(), '0');
    assert.equal(await page.locator('#try-tapealert_media_flags').inputValue(), '1');
    await page.locator('#live-run').click();
    assert.match(await text(page, '#live-result'), /not deployed.*custom input has no live answer/);
    assert.equal(await page.locator('#live-cascade').isVisible(), false);
    assert.deepEqual(requests, [documentURL]);
    assert.deepEqual(errors, []);
  } finally { await b.close(); }
});

test('tour cancels pending live output and manual Next holds each scene until the next click', async () => {
  const b = await browser();
  try {
    const page = await b.newPage({ reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let release;
    const gate = new Promise(resolve => release = resolve);
    let received;
    const pending = new Promise(resolve => received = resolve);
    await page.route('**/*', async route => {
      if (route.request().url() === documentURL) return route.fulfill({ contentType: 'text/html', body: original
        .replace('name="signaldesk-live-endpoint" content=""', `name="signaldesk-live-endpoint" content="${endpoint}"`)
        .replace("connect-src 'none'", 'connect-src https://proxy.signaldesk.test') });
      assert.equal(route.request().url(), endpoint);
      const headers = { 'Access-Control-Allow-Origin': 'https://signaldesk.test', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST' };
      if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
      received();
      await gate;
      return route.fulfill({ status: 429, headers, contentType: 'application/json', body: JSON.stringify({ mode: 'replay', reason: 'ip-limit' }) });
    });
    await page.clock.install();
    await page.goto(documentURL);
    const initialLiveText = await text(page, '#live-result');
    await page.locator('#live-open').click();
    await page.locator('#ticket-examples button').first().click();
    await page.locator('#live-run').click();
    await pending;
    assert.equal(await page.locator('#live-result').getAttribute('data-state'), 'pending');
    await page.locator('#tour-start').click();
    release();
    await page.clock.runFor(100);
    assert.equal(await page.locator('#try-readings').evaluate(node => node.open), false);
    assert.equal(await text(page, '#live-result'), initialLiveText);
    assert.equal(await page.locator('#live-result').getAttribute('data-state'), null);
    assert.equal(await page.locator('#live-cascade').isVisible(), false);
    assert.equal(await page.locator('#live-run').isEnabled(), true);
    assert.equal(await text(page, '#live-status'), 'Recorded replay');
    for (const id of ['X06', 'X02', 'H35', 'X01']) {
      await page.locator('#tour-next').click();
      assert.equal(await page.locator('#case').inputValue(), id);
      await page.clock.fastForward(60000);
      assert.equal(await page.locator('#case').inputValue(), id, `${id} stays put during narration`);
      assert.equal(await text(page, '#tour-pause'), 'Resume');
    }
    await page.locator('#tour-stop').click();
    await page.locator('#tour-start').click();
    await page.clock.fastForward(6000);
    assert.equal(await page.locator('#case').inputValue(), 'X06', 'a fresh tour retains automatic playback');
    assert.equal(await text(page, '#live-result'), initialLiveText, 'late failure cannot restore the cleared output');
    assert.deepEqual(errors, []);
  } finally { await b.close(); }
});

test('animation reveals ordered steps and cancels stale playback when the case changes', async () => {
  const b = await browser();
  try {
    const page = await b.newPage({ reducedMotion: 'no-preference' });
    await page.route('**/*', route => route.fulfill({ contentType: 'text/html', body: original }));
    await page.goto(documentURL);
    await page.locator('#cascade-replay').click();
    assert.equal(await page.locator('#case-flow li').first().getAttribute('data-state'), 'active');
    assert.equal(await page.locator('#case-flow li').nth(1).getAttribute('data-state'), 'pending');
    assert.equal(await page.locator('#case-flow li').nth(1).locator('.stage-body').isVisible(), false);
    await page.waitForFunction(() => document.querySelector('#case-flow li:nth-child(2)').dataset.state === 'active');
    assert.equal(await page.locator('#case-flow li').first().getAttribute('data-state'), 'complete');
    await select(page, 'X01');
    await page.waitForFunction(() => document.querySelector('#case-flow').dataset.complete === 'true');
    assert.equal(await page.locator('#case-flow > li').count(), 3);
    assert.match(await text(page, '#case-flow'), /Ticket in · X01/);
    assert.doesNotMatch(await text(page, '#case-flow'), /X06|Suspect cartridge/);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await select(page, 'X06');
    assert.equal(await page.locator('#case-flow').getAttribute('data-complete'), 'true');
    assert.equal(await page.locator('#case-flow [data-state="active"]').count(), 0);
  } finally { await b.close(); }
});

test('custom live trace uses observed metrics, exports submitted input, and clears stale answers on failure', async () => {
  const b = await browser();
  try {
    const page = await b.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', acceptDownloads: true });
    const errors = [], submissions = [];
    page.on('pageerror', e => errors.push(e.message));
    let mode = 'veto', release;
    const gate = new Promise(resolve => release = resolve);
    const book = resources.runbooks.find(b => b.id === 'RB-MEDIA');
    await page.route('**/*', async route => {
      const request = route.request();
      if (request.url() === documentURL) return route.fulfill({ contentType: 'text/html', body: original
        .replace('name="signaldesk-live-endpoint" content=""', `name="signaldesk-live-endpoint" content="${endpoint}"`)
        .replace("connect-src 'none'", 'connect-src https://proxy.signaldesk.test') });
      assert.equal(request.url(), endpoint);
      const headers = { 'Access-Control-Allow-Origin': 'https://signaldesk.test', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'POST' };
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
      submissions.push(request.postDataJSON());
      if (mode === 'limited') return route.fulfill({ status: 429, headers, contentType: 'application/json', body: JSON.stringify({ mode: 'replay', reason: 'ip-limit' }) });
      let answer = { mode: 'live', actions_executed: 0, path: 'escalated-to-super', escalation: 'telemetry-abstention', latency_ms: 127,
        result: { runbook_id: book.id, steps: [{ source: book.id, step: 1, text: book.steps[0] }] },
        trace: [{ model: data.models[0], proposal: 'RB-CLEAN', validator: 'veto', code: 'telemetry-abstention', latency_ms: 52, usage: { prompt_tokens: 1234, completion_tokens: 56 } },
          { model: data.models[1], proposal: book.id, validator: 'accept', code: 'backed', latency_ms: 75, usage: null }] };
      if (mode === 'veto') await gate;
      if (mode.startsWith('retry-')) {
        const timeout = { model: data.models[0], validator: 'unavailable', code: 'upstream-timeout', latency_ms: 8000, usage: null };
        answer = { ...answer, escalation: 'lightning-unavailable-escalated', latency_ms: 16075,
          trace: [{ ...timeout }, { ...timeout }, answer.trace[1]] };
        if (mode === 'retry-success') answer = { ...answer, path: 'lightning', escalation: undefined, latency_ms: 8075,
          trace: [{ ...timeout }, { ...answer.trace[2], model: data.models[0] }] };
        if (mode === 'retry-replay') answer = { ...answer, mode: 'replay', reason: 'upstream-unavailable', result: undefined,
          trace: [...answer.trace.slice(0, 2), { ...timeout, model: data.models[1], latency_ms: 13000 }], latency_ms: 29000 };
      }
      if (mode === 'upstream') answer = { ...answer, mode: 'replay', reason: 'upstream-unavailable', result: undefined, trace: [answer.trace[0], { model: data.models[1], validator: 'unavailable', code: 'upstream-unavailable', latency_ms: 8, usage: null }] };
      if (mode === 'invalid') answer.result.steps[0].text = '<img src=x onerror=alert(1)>';
      if (mode === 'pre') answer = { mode: 'live', path: 'pre-triage', latency_ms: 0, telemetry: { state: 'healthy' }, result: { runbook_id: null, status: 'no-incident', steps: [] }, trace: [] };
      return route.fulfill({ status: 200, headers, contentType: 'application/json', body: JSON.stringify(answer) });
    });
    await page.goto(documentURL);
    const evidence = await text(page, '#replay-data');
    await page.locator('#live-open').click();
    await page.locator('#ticket-examples button').first().click();
    await page.locator('#live-ticket').fill('Synthetic ticket <img src=x onerror=alert(1)>');
    const submitted = await page.locator('#live-ticket').inputValue();
    await page.locator('#live-run').click();
    await page.waitForFunction(() => document.querySelector('#live-result').dataset.state === 'pending');
    assert.equal(await page.locator('#live-run').isEnabled(), false);
    assert.match(await text(page, '#live-cascade-mode'), /waiting for response/);
    await page.locator('#live-ticket').fill('Edited after submission; must not change the exported response.');
    release();
    await page.waitForFunction(() => document.querySelector('#live-result').dataset.state === 'live');
    assert.equal(submissions[0].ticket, submitted);
    assert.equal(await text(page, '#live-flow li:first-child .stage-body'), submitted);
    assert.equal(await page.locator('#live-flow li:first-child .stage-body').isVisible(), true);
    assert.equal(await page.locator('#live-flow li:last-child .stage-body').isVisible(), true);
    assert.equal(await page.locator('#live-flow img').count(), 0);
    assert.equal(await text(page, '#live-status'), 'Live on Nebius');
    if (process.env.POLISH_SCREENSHOTS) {
      await mkdir(process.env.POLISH_SCREENSHOTS, { recursive: true });
      for (const width of [1280, 390]) {
        await page.setViewportSize({width, height: width === 1280 ? 960 : 844});
        await page.locator('#live-cascade').scrollIntoViewIfNeeded();
        await page.screenshot({path: `${process.env.POLISH_SCREENSHOTS}/live-${width}.png`, fullPage: true});
      }
    }
    assert.match(await text(page, '#live-flow li:nth-child(2)'), /52 ms · 1,234 in \/ 56 out tokens/);
    assert.match(await text(page, '#live-flow li:nth-child(3)'), /VETO/);
    assert.match(await text(page, '#live-flow li:nth-child(4)'), /75 ms · Tokens unavailable/);
    assert.match(await text(page, '#live-flow li:last-child'), /Suspect cartridge.*0 actions executed/s);
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#live-export').click();
    const note = await readFile(await (await downloadPromise).path(), 'utf8');
    assert.ok(note.includes(submitted));
    assert.doesNotMatch(note, /Edited after submission/);
    assert.equal(await text(page, '#replay-data'), evidence);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    for (const retryMode of ['retry-success', 'retry-super', 'retry-replay']) {
      mode = retryMode;
      await page.locator('#live-run').click();
      await page.waitForFunction(() => ['live', 'replay'].includes(document.querySelector('#live-result').dataset.state));
      assert.match(await text(page, '#live-flow li:nth-child(3)'), /UNAVAILABLE.*Model timed out\. Retrying Lightning\./s);
      if (mode === 'retry-success') {
        assert.equal(await page.locator('#live-flow > li').count(), 6);
        assert.doesNotMatch(await text(page, '#live-flow'), /Super/);
      } else {
        assert.match(await text(page, '#live-flow li:nth-child(5)'), /Model timed out\. Escalated to Super\./);
        assert.equal(await page.locator('#live-flow > li').count(), 8);
      }
      if (mode === 'retry-replay') {
        assert.match(await text(page, '#live-flow'), /Super.*UNAVAILABLE.*No live incident note/s);
        assert.match(await text(page, '#live-result'), /recorded replay.*custom input has no live answer/);
        assert.equal(await page.locator('#live-export').isVisible(), false);
      } else assert.equal(await page.locator('#live-export').isVisible(), true);
      assert.equal(await text(page, '#replay-data'), evidence);
    }
    mode = 'invalid';
    await page.locator('#live-run').click();
    await page.waitForFunction(() => document.querySelector('#live-result').dataset.state === 'replay');
    assert.equal(await page.locator('#live-export').isVisible(), false);
    assert.equal(await page.locator('#live-cascade').isVisible(), false);
    assert.equal(await page.locator('#live-flow img').count(), 0);
    mode = 'upstream';
    await page.locator('#live-run').click();
    await page.waitForFunction(() => document.querySelector('#live-cascade-mode').textContent.includes('Incomplete'));
    assert.match(await text(page,'#live-flow'), /VETO.*Super.*UNAVAILABLE.*No live incident note/s);
    assert.equal(await page.locator('#live-export').isVisible(),false);
    assert.match(await text(page,'#live-result'),/custom input has no live answer/);
    mode = 'pre';
    await page.locator('#live-run').click();
    await page.waitForFunction(() => document.querySelector('#live-result').dataset.state === 'live');
    assert.equal(await page.locator('#live-flow > li').count(), 3);
    assert.match(await text(page, '#live-flow'), /No model call: healthy/);
    mode = 'limited';
    await page.locator('#live-run').click();
    await page.waitForFunction(() => document.querySelector('#live-result').dataset.state === 'replay');
    assert.match(await text(page, '#live-result'), /ip-limit.*no live answer/);
    assert.equal(await text(page, '#live-status'), 'Live limit · replay available');
    assert.equal(await page.locator('#live-cascade').isVisible(), false);
    assert.equal(await page.locator('#live-run').isEnabled(), true);
    assert.deepEqual(errors, []);
  } finally { await b.close(); }
});
