import test from 'node:test';
import assert from 'node:assert/strict';
import { Miniflare, Response as RuntimeResponse } from 'miniflare';
import { fileURLToPath } from 'node:url';

const origin = 'https://mitcheltighe.github.io';
const modules = ['index.mjs', 'cascade.mjs', 'resources.mjs'].map(name => ({
  type: 'ESModule', path: fileURLToPath(new URL(name, import.meta.url))
}));
const headers = { Origin: origin, 'Content-Type': 'application/json', 'CF-Connecting-IP': '192.0.2.1' };
const body = JSON.stringify({ ticket: 'Synthetic missing-telemetry test', evidence: [] });

test('real workerd SQLite Durable Object shares quota across requests and rejects races', async () => {
  const mf = new Miniflare({ modules, modulesRoot: fileURLToPath(new URL('.', import.meta.url)),
    compatibilityDate: '2025-10-01', port: 0, inspectorPort: 0,
    bindings: { LIVE_ENABLED: 'true', NEBIUS_API_KEY: 'synthetic-fixture', ALLOWED_ORIGIN: origin,
      DAILY_RUN_CAP: '3', DAILY_SPEND_CENTS: '200' },
    durableObjects: { LIVE_QUOTA: { className: 'LiveQuota', useSQLite: true } },
    outboundService: () => { throw Error('No live upstream requests allowed in runtime tests'); }
  });
  try {
    const results = await Promise.all(Array.from({ length: 12 }, () =>
      mf.dispatchFetch('https://signaldesk-live.example/api/live', { method: 'POST', headers, body })));
    assert.equal(results.filter(r => r.status === 200).length, 3);
    assert.equal(results.filter(r => r.status === 429).length, 9);
    for (const r of results) {
      const data = await r.json();
      if (r.status === 200) { assert.equal(data.path, 'pre-triage'); assert.deepEqual(data.trace, []); }
      else assert.equal(data.reason, 'daily-limit');
    }
    const namespace = await mf.getDurableObjectNamespace('LIVE_QUOTA');
    const quota = namespace.get(namespace.idFromName('signaldesk-live-global-v1'));
    const r = await quota.fetch('https://quota.internal/reserve', { method: 'POST',
      body: JSON.stringify({ ipHash: 'a'.repeat(64) }) });
    assert.equal(r.status, 429); assert.equal((await r.json()).reason, 'daily-limit');
  } finally { await mf.dispose(); }
});

test('real workerd executes Lightning veto → Super through a mocked Nebius upstream', async () => {
  const { resources } = await import('./resources.mjs');
  const calls = [];
  const mf = new Miniflare({ modules, modulesRoot: fileURLToPath(new URL('.', import.meta.url)),
    compatibilityDate: '2025-10-01', port: 0, inspectorPort: 0,
    bindings: { LIVE_ENABLED: 'true', NEBIUS_API_KEY: 'synthetic-fixture', ALLOWED_ORIGIN: origin,
      DAILY_RUN_CAP: '100', DAILY_SPEND_CENTS: '200' },
    durableObjects: { LIVE_QUOTA: { className: 'LiveQuota', useSQLite: true } },
    outboundService: async request => {
      assert.equal(request.url, 'https://api.tokenfactory.nebius.com/v1/chat/completions');
      const payload = await request.json(); calls.push(payload.model);
      const book = resources.runbooks.find(b => b.id === (calls.length === 1 ? 'RB-CLEAN' : 'RB-MOUNT'));
      return RuntimeResponse.json({ choices: [{ finish_reason: 'stop', message: { content: JSON.stringify({
        runbook_id: book.id, hypothesis: book.title, evidence_ids: ['E1'], web_citations: [],
        steps: [{ source: book.id, step: 1, text: book.steps[0] }]
      }) } }], usage: { prompt_tokens: 1000, completion_tokens: 100, total_tokens: 1100 } });
    }
  });
  try {
    const r = await mf.dispatchFetch('https://signaldesk-live.example/api/live', { method: 'POST', headers,
      body: JSON.stringify({ ticket: 'Synthetic loading incident', evidence: [{ id: 'E1', metric: 'load_wait_seconds', value: 120 }] }) });
    const data = await r.json();
    assert.equal(r.status, 200, JSON.stringify({data,calls}));
    assert.equal(data.path, 'escalated-to-super'); assert.equal(data.result.runbook_id, 'RB-MOUNT');
    assert.deepEqual(data.trace.map(row => row.validator), ['veto', 'accept']);
    assert.deepEqual(calls, ['nvidia/Nemotron-3_5-Lightning', 'nvidia/nemotron-3-super-120b-a12b']);
  } finally { await mf.dispose(); }
});
