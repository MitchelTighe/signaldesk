import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resources } from './resources.mjs';
import { createWorker, LiveQuota, reserve, configuration } from './index.mjs';
import { incidentInput, validateDraft, cascade, boundedText, payloadFor, LIMITS, LIGHTNING, SUPER } from './cascade.mjs';

const origin = 'https://mitcheltighe.github.io';
const input = (metric = 'load_wait_seconds', value = 120, ticket = 'Synthetic incident') =>
  ({ ticket, evidence: [{ id: 'E1', metric, value }] });
const draft = (id = 'RB-MOUNT', ids = ['E1']) => {
  if (id === null) return { runbook_id: null, evidence_ids: [], hypothesis: null, steps: [], web_citations: [] };
  const b = resources.runbooks.find(x => x.id === id);
  return { runbook_id: id, evidence_ids: ids, hypothesis: b.title,
    steps: [{ source: id, step: 1, text: b.steps[0] }], web_citations: [] };
};
const envelope = (d = draft(), extras = {}) => ({
  choices: [{ finish_reason: 'stop', message: { content: JSON.stringify(d) } }],
  usage: { prompt_tokens: 1500, completion_tokens: 100, total_tokens: 1600 }, ...extras
});
const mock = (responses = [envelope()]) => {
  const calls = [];
  const transport = async (url, init) => {
    calls.push({ url, ...init, payload: JSON.parse(init.body) });
    const next = responses[calls.length - 1];
    if (next instanceof Error) throw next;
    return next instanceof Response ? next : Response.json(next);
  };
  return { calls, transport };
};
// Serialize transactions like the durable authority; test racing requests against persisted state.
class Storage {
  value = undefined; tail = Promise.resolve();
  transaction(fn) {
    const result = this.tail.then(async () => {
      let pending = structuredClone(this.value);
      const result = await fn({ get: async () => structuredClone(pending), put: async (_, v) => { pending = structuredClone(v); } });
      this.value = pending;
      return result;
    });
    this.tail = result.catch(() => {}); return result;
  }
}
function fixture(overrides = {}, responses) {
  const storage = new Storage(), upstream = mock(responses);
  const env = { LIVE_ENABLED: 'true', NEBIUS_API_KEY: 'synthetic-fixture',
    ALLOWED_ORIGIN: origin, DAILY_RUN_CAP: '100', DAILY_SPEND_CENTS: '200', ...overrides };
  const quota = new LiveQuota({ storage }, env);
  env.LIVE_QUOTA = { idFromName: name => { assert.equal(name, 'signaldesk-live-global-v1'); return name; },
    get: () => ({ fetch: (url, init) => quota.fetch(new Request(url, init)) }) };
  return { storage, env, ...upstream, worker: createWorker(upstream.transport) };
}
function request(body = input(), { method = 'POST', headers = {}, path = '/api/live', raw } = {}) {
  return new Request('https://signaldesk-live.example' + path, { method,
    headers: { Origin: origin, 'CF-Connecting-IP': '192.0.2.1', 'Content-Type': 'application/json', ...headers },
    body: ['POST', 'PUT'].includes(method) ? (raw ?? JSON.stringify(body)) : undefined });
}
async function run(f, body, opts) {
  const response = await f.worker.fetch(request(body, opts), f.env);
  return { response, data: await response.json() };
}

test('accepts read-only draft and calls only exact Lightning with bounded payload', async () => {
  const f = fixture(), { response, data } = await run(f);
  assert.equal(response.status, 200); assert.equal(data.path, 'lightning');
  assert.equal(data.result.runbook_id, 'RB-MOUNT'); assert.equal(data.trace[0].validator, 'accept');
  assert.equal(data.actions_executed, 0); assert.deepEqual(data.trace[0].usage, envelope().usage);
  assert.equal(response.headers.get('access-control-allow-origin'), origin);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].url, 'https://api.tokenfactory.nebius.com/v1/chat/completions');
  assert.equal(f.calls[0].redirect, 'manual'); assert.equal(f.calls[0].payload.model, LIGHTNING); assert.equal(f.calls[0].payload.max_tokens, 500);
  assert.equal(f.calls[0].payload.chat_template_kwargs.enable_thinking, false);
});

test('wrong telemetry proposal is vetoed and routed to exact Super', async () => {
  const f = fixture({}, [envelope(draft('RB-CLEAN')), envelope()]);
  const { data } = await run(f);
  assert.equal(data.path, 'escalated-to-super'); assert.equal(data.trace[0].code, 'telemetry-abstention');
  assert.equal(data.trace[0].validator, 'veto'); assert.equal(data.result.runbook_id, 'RB-MOUNT');
  assert.deepEqual(f.calls.map(c => c.payload.model), [LIGHTNING, SUPER]);
});

test('physical proposals always need Super; valid Super abstention stays empty', async () => {
  const f = fixture({}, [envelope(draft('RB-CLEAN')), envelope(draft(null))]);
  const { data } = await run(f, input('tapealert_cleaning_flags', 1, 'Cleaning already failed twice.'));
  assert.equal(data.escalation, 'physical-action-second-reader'); assert.equal(data.result.runbook_id, null);
  assert.deepEqual(data.result.steps, []);
});

test('Lightning abstention escalates even with single abnormal family', async () => {
  const f = fixture({}, [envelope(draft(null)), envelope()]);
  assert.equal((await run(f)).data.escalation, 'lightning-abstained');
});

test('Super veto returns human handoff and never a third request', async () => {
  const f = fixture({}, [envelope(draft('RB-CLEAN')), envelope(draft('RB-CLEAN'))]);
  const { data } = await run(f);
  assert.equal(data.result.status, 'needs-human'); assert.equal(data.result.runbook_id, null);
  assert.deepEqual(data.result.steps, []); assert.equal(f.calls.length, 2);
});

test('malformed, unfinished and injected model drafts escalate without rendering prose', async t => {
  for (const choice of [
    { finish_reason: 'length', message: { content: JSON.stringify(draft()) } },
    { finish_reason: 'stop', message: { content: 'untrusted provider text' } },
    { finish_reason: 'stop', message: { content: JSON.stringify({ ...draft(), hypothesis: '<script>attack</script>' }) } }
  ]) await t.test(choice.finish_reason + choice.message.content.slice(0, 10), async () => {
    const f = fixture({}, [envelope(null, { choices: [choice] }), envelope()]);
    const { data } = await run(f);
    assert.equal(data.trace[0].validator, 'veto'); assert.equal(data.result.runbook_id, 'RB-MOUNT');
    assert.ok(!JSON.stringify(data).includes('attack')); assert.ok(!JSON.stringify(data).includes('untrusted provider text'));
  });
});

test('pre-triage makes zero upstream calls for missing, healthy and conflicting readings', async () => {
  for (const data of [{ ticket: '', evidence: [] }, input('load_wait_seconds', 119.9),
    { ticket: '', evidence: [...input().evidence, { id: 'E2', metric: 'tapealert_media_flags', value: 1 }] }]) {
    const f = fixture(); assert.equal((await run(f, data)).data.path, 'pre-triage'); assert.equal(f.calls.length, 0);
  }
});

test('validator rejects forged citations, duplicates, edited text, extra fields and nonempty abstention', () => {
  const c = incidentInput(input());
  for (const d of [draft('RB-MOUNT', ['foreign']), draft('RB-MOUNT', ['E1', 'E1']),
    { ...draft(), extra: true }, { ...draft(), hypothesis: 'invented' },
    { ...draft(), web_citations: ['WEB-made-up'] }, { ...draft(null), steps: draft().steps },
    { ...draft(), steps: [{ ...draft().steps[0], step: true }] },
    { ...draft(), steps: [{ ...draft().steps[0], text: 'invented' }] },
    { ...draft(), steps: [...draft().steps, ...draft().steps] }]) assert.equal(validateDraft(d, c).verdict, 'veto');
  const extraEvidence = { ...c, evidence: [...c.evidence, { id: 'E2', metric: 'tapealert_media_flags', value: 0 }] };
  assert.equal(validateDraft(draft('RB-MOUNT', ['E1', 'E2']), extraEvidence).code, 'evidence-support');
});

test('per-IP rolling-hour limit is 20 with no extra upstream call', async () => {
  const f = fixture({}, Array.from({ length: 20 }, () => envelope()));
  for (let i = 0; i < 20; i++) assert.equal((await run(f)).response.status, 200);
  assert.equal((await run(f)).data.reason, 'ip-limit'); assert.equal(f.calls.length, 20);
});

test('daily and spend limits hold across IPs, object restarts and concurrent reservations', async () => {
  for (const [overrides, expected] of [[{ DAILY_RUN_CAP: '1' }, 'daily-limit'], [{ DAILY_SPEND_CENTS: '2' }, 'spend-limit']]) {
    const f = fixture(overrides); assert.equal((await run(f)).data.mode, 'live');
    assert.equal((await run(f, undefined, { headers: { 'CF-Connecting-IP': '192.0.2.2' } })).data.reason, expected);
    const restarted = new LiveQuota({ storage: f.storage }, f.env);
    const r = await restarted.fetch(new Request('https://quota.internal', { method: 'POST', body: JSON.stringify({ ipHash: 'a'.repeat(64) }) }));
    assert.equal((await r.json()).reason, expected); assert.equal(f.calls.length, 1);
  }
  const s = new Storage(), config = { daily: 10, cents: 200 };
  const answers = await Promise.all(Array.from({ length: 50 }, (_, i) => reserve(s, String(i), config, 1000)));
  assert.equal(answers.filter(x => x === null).length, 10); assert.equal(s.value.runs, 10);
});

test('UTC day resets global cap but retains per-IP rolling window', async () => {
  const s = new Storage(), config = { daily: 100, cents: 200 };
  const before = 86400000 - 100;
  for (let i = 0; i < 20; i++) assert.equal(await reserve(s, 'same', config, before), null);
  assert.equal(await reserve(s, 'same', config, before + 200), 'ip-limit');
  assert.equal(await reserve(s, 'same', config, before + 3600001), null);
  assert.equal(s.value.runs, 1);
});

test('upstream and quota failures fail closed; failed requests retain reservations', async () => {
  for (const failure of [new Response(null, { status: 302, headers: { Location: 'https://untrusted.example' } }), new Error('untrusted error'), new Response('untrusted provider error', { status: 429 }),
    new Response('untrusted provider error', { status: 500 }), Response.json(envelope(draft(), { usage: null })),
    Response.json(envelope(draft(), { usage: { prompt_tokens: 1500, completion_tokens: 501, total_tokens: 2001 } })),
    new Response('x'.repeat(LIMITS.response + 1))]) {
    const f = fixture({}, [failure]), { response, data } = await run(f);
    assert.equal(response.status, 503); assert.equal(data.mode, 'replay'); assert.equal(f.calls.length, 1);
    assert.equal(f.storage.value.cents, 2); assert.ok(!JSON.stringify(data).includes('untrusted'));
    assert.match(data.message, /custom input has no live answer/);
  }
  const f = fixture(); f.env.LIVE_QUOTA.get = () => { throw Error('storage offline'); };
  assert.equal((await run(f)).data.mode, 'replay'); assert.equal(f.calls.length, 0);
});

test('a Super transport failure preserves Lightning trace and shows replay', async () => {
  const f = fixture({}, [envelope(draft('RB-CLEAN')), new Error('offline')]);
  const { data } = await run(f); assert.equal(data.mode, 'replay'); assert.equal(data.trace.length, 2);
  assert.equal(data.trace[0].validator, 'veto'); assert.equal(f.storage.value.cents, 2);
});

test('disabled/missing/invalid configuration never calls upstream', async () => {
  for (const overrides of [{ LIVE_ENABLED: 'false' }, { NEBIUS_API_KEY: '' }, { DAILY_RUN_CAP: '1001' },
    { DAILY_SPEND_CENTS: '201' }, { DAILY_RUN_CAP: 'NaN' }, { ALLOWED_ORIGIN: '*' }]) {
    const f = fixture(overrides); assert.equal((await run(f)).data.mode, 'replay'); assert.equal(f.calls.length, 0);
  }
  assert.equal(configuration({}), null);
});

test('CORS preflight, disallowed origins, methods, paths, and missing trusted IP', async () => {
  const f = fixture();
  const preflight = await f.worker.fetch(request(undefined, { method: 'OPTIONS' }), f.env);
  assert.equal(preflight.status, 204); assert.equal(preflight.headers.get('access-control-allow-origin'), origin);
  for (const opts of [{ method: 'GET' }, { method: 'PUT' }, { path: '/other' }, { path: '/api/live?model=other' },
    { headers: { Origin: 'https://evil.example' } }, { headers: { Origin: 'null' } }, { headers: { 'CF-Connecting-IP': '' } }]) {
    const { response, data } = await run(f, undefined, opts); assert.equal(data.mode, 'replay');
    if (opts.headers?.Origin) assert.equal(response.headers.get('access-control-allow-origin'), null);
  }
  assert.equal(f.calls.length, 0); assert.equal(f.storage.value, undefined);
});

test('schema and byte caps reject caller model/prompt/URL overrides before quota or transport', async () => {
  const invalid = [ { ...input(), model: SUPER }, { ...input(), max_tokens: 9999 },
    { ...input(), ticket: 'x'.repeat(2001) }, { ticket: '', evidence: [{ id: 'E1', metric: 'unknown', value: 1 }] },
    input('load_wait_seconds', true), input('load_wait_seconds', '120'),
    { ticket: '', evidence: [...input().evidence, ...input().evidence] } ];
  for (const body of invalid) {
    const f = fixture(); assert.equal((await run(f, body)).response.status, 400);
    assert.equal(f.calls.length, 0); assert.equal(f.storage.value, undefined);
  }
  for (const opts of [{ raw: '{invalid' }, { raw: ' '.repeat(8193) }, { headers: { 'Content-Length': '8193' } },
    { headers: { 'Content-Type': 'text/plain' } }, { headers: { 'Content-Encoding': 'gzip' } }]) {
    const f = fixture(); assert.equal((await run(f, undefined, opts)).data.mode, 'replay'); assert.equal(f.calls.length, 0);
  }
});

test('stream reader enforces size without Content-Length and cancellation', async () => {
  await assert.rejects(boundedText(new Response('x'.repeat(100)).body, 10));
  const controller = new AbortController(); let cancelled = false;
  const stream = new ReadableStream({ cancel() { cancelled = true; } });
  const result = boundedText(stream, 10, controller.signal); controller.abort();
  await assert.rejects(result); assert.equal(cancelled, true);
});

test('prompt resources match canonical authored runbooks; two-cent reservation covers both calls at 2x rates', () => {
  const canonical = JSON.parse(readFileSync(new URL('../signaldesk/data.json', import.meta.url)));
  assert.deepEqual(resources.runbooks, canonical.runbooks.map(({ training, ...book }) => book));
  assert.throws(() => payloadFor('arbitrary-model', incidentInput(input())));
  const cost = 2 * ((24000 * .06 + 500 * .24) + (24000 * .30 + 500 * .90)) / 1e6;
  assert.ok(cost < .02);
  const p = payloadFor(SUPER, incidentInput(input('load_wait_seconds', 120, 'x'.repeat(2000))));
  assert.ok(new TextEncoder().encode(JSON.stringify(p.messages)).length + 4096 <= LIMITS.prompt);
});
