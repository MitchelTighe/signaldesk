import { boundedText, cascade, incidentInput, LIMITS, payloadFor, telemetry, LIGHTNING, SUPER } from './cascade.mjs';

const fallback = (reason, extra = {}) => ({ mode: 'replay', reason, actions_executed: 0,
  message: 'Live run unavailable. Showing the recorded replay; your custom input has no live answer.', ...extra });
const json = (value, status = 200, headers = {}) => Response.json(value, { status,
  headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...headers } });

export function configuration(env) {
  const daily = Number(env.DAILY_RUN_CAP), cents = Number(env.DAILY_SPEND_CENTS);
  let origin;
  try { origin = new URL(env.ALLOWED_ORIGIN); } catch { return null; }
  if (origin.protocol !== 'https:' || origin.origin !== env.ALLOWED_ORIGIN ||
      !Number.isSafeInteger(daily) || daily < 1 || daily > 1000 ||
      !Number.isSafeInteger(cents) || cents < 2 || cents > 200) return null;
  return { daily, cents, origin: origin.origin };
}

export async function reserve(storage, ipHash, config, now = Date.now()) {
  return storage.transaction(async tx => {
    const day = Math.floor(now / 86400000);
    let state = await tx.get('quota');
    if (!state) state = { day, runs: 0, cents: 0, clients: {} };
    // A UTC rollover must not reset the rolling one-hour IP window.
    for (const [key, times] of Object.entries(state.clients)) {
      const recent = times.filter(t => t > now - 3600000);
      if (recent.length) state.clients[key] = recent;
      else delete state.clients[key];
    }
    if (state.day !== day) { state.day = day; state.runs = 0; state.cents = 0; state.dailyClients = {}; }
    state.dailyClients ||= {};
    const times = state.clients[ipHash] || [];
    if (times.length >= 20 || (state.dailyClients[ipHash] || 0) >= 40) return 'ip-limit';
    if (state.runs >= config.daily) return 'daily-limit';
    // Two cents covers two Lightning calls plus Super at the checked-in prices.
    if (state.cents + 2 > config.cents) return 'spend-limit';
    state.runs++; state.cents += 2; state.clients[ipHash] = [...times, now];
    state.dailyClients[ipHash] = (state.dailyClients[ipHash] || 0) + 1;
    await tx.put('quota', state);
    return null;
  });
}

export class LiveQuota {
  constructor(ctx, env) { this.storage = ctx.storage; this.env = env; }
  async fetch(request) {
    try {
      const config = configuration(this.env);
      if (!config || this.env.LIVE_ENABLED !== 'true') return json({ reason: 'disabled' }, 503);
      const { ipHash } = await request.json();
      if (typeof ipHash !== 'string' || !/^[a-f0-9]{64}$/.test(ipHash)) return json({ reason: 'input' }, 400);
      const reason = await reserve(this.storage, ipHash, config);
      return json({ reason }, reason ? 429 : 200);
    } catch { return json({ reason: 'quota-unavailable' }, 503); }
  }
}

export function createWorker(transport = fetch) {
  return { async fetch(request, env) {
    const url = new URL(request.url), config = configuration(env);
    const origin = request.headers.get('Origin');
    const cors = config && origin === config.origin ? { 'Access-Control-Allow-Origin': origin,
      Vary: 'Origin', 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type' } : {};
    const reply = (data, status) => json(data, status, cors);
    if (url.pathname !== '/api/live' || url.search) return reply(fallback('not-found'), 404);
    if (!config || origin !== config.origin) return reply(fallback('origin-denied'), 403);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    if (request.method !== 'POST') return reply(fallback('method-denied'), 405);
    if (env.LIVE_ENABLED !== 'true' || !env.NEBIUS_API_KEY || !env.IP_HASH_SECRET || !env.LIVE_QUOTA) return reply(fallback('disabled'), 503);
    if (request.headers.get('Content-Type')?.split(';')[0].trim() !== 'application/json') return reply(fallback('invalid-input'), 415);
    if (request.headers.get('Content-Encoding') && request.headers.get('Content-Encoding') !== 'identity') return reply(fallback('invalid-input'), 415);
    const ip = request.headers.get('CF-Connecting-IP');
    if (!ip) return reply(fallback('client-unavailable'), 503);
    if (Number(request.headers.get('Content-Length') || 0) > LIMITS.body) return reply(fallback('input-too-large'), 413);
    let incident;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      try { incident = incidentInput(JSON.parse(await boundedText(request.body, LIMITS.body, controller.signal))); }
      finally { clearTimeout(timer); }
      payloadFor(LIGHTNING, incident); payloadFor(SUPER, incident);
    } catch { return reply(fallback('invalid-input'), 400); }
    if (telemetry(incident).state !== 'single') return reply(await cascade(incident, env, transport), 200);
    try {
      const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(env.IP_HASH_SECRET), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      const digest = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(ip));
      const ipHash = [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
      // Every edge isolate uses this one durable authority; never create an object per IP.
      const stub = env.LIVE_QUOTA.get(env.LIVE_QUOTA.idFromName('signaldesk-live-global-v1'));
      const reservation = await stub.fetch('https://quota.internal/reserve', { method: 'POST',
        body: JSON.stringify({ ipHash }) });
      const quota = await reservation.json();
      if (!reservation.ok || quota.reason !== null) return reply(fallback(
        ['ip-limit', 'daily-limit', 'spend-limit'].includes(quota.reason) ? quota.reason : 'quota-unavailable'), reservation.status === 429 ? 429 : 503);
      const result = await cascade(incident, env, transport);
      if (result.mode === 'replay') return reply(fallback(result.reason, {
        trace: result.trace, escalation: result.escalation, latency_ms: result.latency_ms }), 503);
      return reply(result, 200);
    } catch { return reply(fallback('service-unavailable'), 503); }
  } };
}

export default createWorker();
