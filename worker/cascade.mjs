import { resources } from './resources.mjs';

export const LIGHTNING = 'nvidia/Nemotron-3_5-Lightning';
export const SUPER = 'nvidia/nemotron-3-super-120b-a12b';
export const LIMITS = Object.freeze({ body: 8192, prompt: 24000, output: 500, response: 65536, timeout: 20000 });
const books = resources.runbooks;
const physical = new Set(['RB-CLEAN', 'RB-INVENTORY', 'RB-MEDIA']);
const exactKeys = (v, keys) => v && typeof v === 'object' && !Array.isArray(v) &&
  Object.keys(v).sort().join(',') === [...keys].sort().join(',');
const uniqueStrings = v => Array.isArray(v) && v.every(x => typeof x === 'string') && new Set(v).size === v.length;
const corroborates = (e, b) => e.metric === b.metric && typeof e.value === 'number' &&
  Number.isFinite(e.value) && e.value >= b.minimum && (b.unit !== 'percent' || e.value <= 100);

export function incidentInput(input) {
  if (!exactKeys(input, ['ticket', 'evidence']) || typeof input.ticket !== 'string' ||
      input.ticket.length > 2000 || !Array.isArray(input.evidence) || input.evidence.length > 8) throw Error('input');
  const ids = new Set(), metrics = new Set();
  for (const e of input.evidence) {
    if (!exactKeys(e, ['id', 'metric', 'value']) || typeof e.id !== 'string' ||
        !/^[A-Za-z0-9_-]{1,64}$/.test(e.id) || !books.some(b => b.metric === e.metric) ||
        ids.has(e.id) || metrics.has(e.metric) || typeof e.value !== 'number' || !Number.isFinite(e.value)) throw Error('input');
    ids.add(e.id); metrics.add(e.metric);
  }
  return { id: 'live-input', title: 'User supplied synthetic incident', text: input.ticket, evidence: input.evidence };
}

export function telemetry(incident) {
  const abnormal = books.filter(b => incident.evidence.some(e => corroborates(e, b))).map(b => b.id);
  return { families: abnormal, state: abnormal.length > 1 ? 'conflict' : abnormal.length ? 'single' :
    incident.evidence.length ? 'healthy' : 'missing' };
}

export function validateDraft(draft, incident) {
  const reject = code => ({ verdict: 'veto', code, runbook_id: null, steps: [] });
  if (!exactKeys(draft, ['runbook_id', 'evidence_ids', 'hypothesis', 'steps', 'web_citations'])) return reject('draft-schema');
  const { evidence_ids: ids, steps, web_citations: web } = draft;
  if (!uniqueStrings(ids) || ids.some(id => !incident.evidence.some(e => e.id === id)) ||
      !Array.isArray(steps) || steps.length > 3 || !uniqueStrings(web) || web.length) return reject('draft-lists');
  if (draft.runbook_id === null) {
    if (draft.hypothesis !== null || ids.length || steps.length) return reject('abstention-shape');
    return { verdict: 'accept', code: 'abstained', runbook_id: null, hypothesis: null, steps: [] };
  }
  const book = books.find(b => b.id === draft.runbook_id);
  if (!book || draft.hypothesis !== book.title || !steps.length) return reject('runbook-content');
  const seen = new Set();
  for (const s of steps) {
    if (!exactKeys(s, ['source', 'step', 'text']) || s.source !== book.id || !Number.isInteger(s.step) ||
        s.step < 1 || s.step > book.steps.length || seen.has(s.step) || s.text !== book.steps[s.step - 1]) return reject('step-citation');
    seen.add(s.step);
  }
  const t = telemetry(incident), evidence = incident.evidence.filter(e => ids.includes(e.id) && corroborates(e, book));
  if (t.families.length > 1 || !evidence.length) return reject('telemetry-abstention');
  if (evidence.length !== ids.length) return reject('evidence-support');
  return { verdict: 'accept', code: 'backed', runbook_id: book.id, hypothesis: book.title,
    evidence, steps: steps.map(s => ({ source: book.id, step: s.step, text: book.steps[s.step - 1] })) };
}

export async function boundedText(stream, max, signal) {
  if (!stream) return '';
  const reader = stream.getReader();
  const chunks = []; let bytes = 0;
  const abort = () => { reader.cancel().catch(() => {}); };
  signal?.addEventListener('abort', abort, { once: true });
  try {
    if (signal?.aborted) throw Error('timeout');
    while (true) {
      const { done, value } = await reader.read();
      if (signal?.aborted) throw Error('timeout');
      if (done) break;
      bytes += value.byteLength;
      if (bytes > max) { await reader.cancel(); throw Error('size'); }
      chunks.push(value);
    }
    const result = new Uint8Array(bytes); let offset = 0;
    for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
    return new TextDecoder('utf-8', { fatal: true }).decode(result);
  } finally {
    signal?.removeEventListener('abort', abort);
    reader.releaseLock();
  }
}

export function payloadFor(model, incident) {
  if (![LIGHTNING, SUPER].includes(model)) throw Error('model');
  const payload = { model, temperature: 0, max_tokens: LIMITS.output,
    response_format: { type: 'json_object' }, chat_template_kwargs: { enable_thinking: false },
    messages: [{ role: 'system', content: resources.system },
      { role: 'user', content: JSON.stringify({ incident, runbooks: books, public_docs: [] }) }] };
  if (new TextEncoder().encode(JSON.stringify(payload.messages)).length + 4096 > LIMITS.prompt) throw Error('prompt');
  return payload;
}

async function draftCall(model, incident, env, transport) {
  const payload = payloadFor(model, incident), started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), LIMITS.timeout);
  const trace = { model, latency_ms: 0, usage: null, validator: 'unavailable', code: 'upstream-unavailable' };
  try {
    const response = await transport('https://api.tokenfactory.nebius.com/v1/chat/completions', {
      method: 'POST', redirect: 'manual', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${env.NEBIUS_API_KEY}` },
      body: JSON.stringify(payload)
    });
    if (!response.ok) { await response.body?.cancel(); throw Error('upstream'); }
    const envelope = JSON.parse(await boundedText(response.body, LIMITS.response, controller.signal));
    const u = envelope.usage;
    if (!u || ![u.prompt_tokens, u.completion_tokens, u.total_tokens].every(Number.isSafeInteger) ||
        u.prompt_tokens < 0 || u.completion_tokens < 0 || u.prompt_tokens > LIMITS.prompt ||
        u.completion_tokens > LIMITS.output || u.total_tokens !== u.prompt_tokens + u.completion_tokens) throw Error('usage');
    trace.usage = { prompt_tokens: u.prompt_tokens, completion_tokens: u.completion_tokens, total_tokens: u.total_tokens };
    const choice = envelope.choices?.[0];
    let result;
    if (choice?.finish_reason !== 'stop') result = { verdict: 'veto', code: 'unfinished-response', runbook_id: null, steps: [] };
    else {
      try {
        const draft = JSON.parse(choice.message.content);
        trace.proposal = books.some(b => b.id === draft?.runbook_id) ? draft.runbook_id : null;
        result = validateDraft(draft, incident);
      }
      catch { result = { verdict: 'veto', code: 'invalid-json', runbook_id: null, steps: [] }; }
    }
    trace.validator = result.verdict; trace.code = result.code;
    return { trace, result };
  } catch {
    return { trace, result: null };
  } finally {
    clearTimeout(timer); trace.latency_ms = Date.now() - started;
  }
}

export async function cascade(incident, env, transport = fetch) {
  const started = Date.now(), t = telemetry(incident), trace = [];
  const base = { mode: 'live', actions_executed: 0, telemetry: t, trace };
  if (t.state !== 'single') return { ...base, path: 'pre-triage', latency_ms: 0,
    result: { runbook_id: null, steps: [], status: t.state === 'healthy' ? 'no-incident' : 'needs-human' } };
  const light = await draftCall(LIGHTNING, incident, env, transport); trace.push(light.trace);
  if (!light.result) return { ...base, mode: 'replay', reason: 'upstream-unavailable', latency_ms: Date.now() - started };
  if (light.result.verdict === 'accept' && light.result.runbook_id && !physical.has(light.result.runbook_id)) {
    return { ...base, path: 'lightning', result: light.result, latency_ms: Date.now() - started };
  }
  const reason = light.result.verdict === 'veto' ? light.result.code :
    light.result.runbook_id ? 'physical-action-second-reader' : 'lightning-abstained';
  const sup = await draftCall(SUPER, incident, env, transport); trace.push(sup.trace);
  if (!sup.result) return { ...base, mode: 'replay', reason: 'upstream-unavailable', latency_ms: Date.now() - started };
  return { ...base, path: 'escalated-to-super', escalation: reason,
    result: sup.result.verdict === 'accept' ? sup.result : { runbook_id: null, steps: [], status: 'needs-human', code: sup.result.code },
    latency_ms: Date.now() - started };
}
