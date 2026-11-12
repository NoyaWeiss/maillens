// Inbox scan: the Gmail API adapter must expose exactly what buildPayload_ reads, from real API shapes.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const b64 = (s) => Buffer.from(s, 'utf8').toString('base64').replace(/\+/g, '-').replace(/\//g, '_');
const ctx = {
  Utilities: {
    base64DecodeWebSafe: (d) => { if (!/^[A-Za-z0-9_=-]*$/.test(d)) throw new Error('Could not decode string.'); return [...Buffer.from(d.replace(/-/g, '+').replace(/_/g, '/'), 'base64')]; },
    newBlob: (bytes) => ({ getDataAsString: (cs) => Buffer.from(bytes.map((b) => (b + 256) % 256)).toString(cs && /8859-1|latin1/i.test(cs) ? 'latin1' : 'utf8') }),
  },
};
// What Apps Script's ADVANCED Gmail service really returns for body.data: signed Java bytes, not base64 text.
const javaBytes = (str, enc = 'utf8') => [...Buffer.from(str, enc)].map((b) => (b > 127 ? b - 256 : b));
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'Scan.js'), 'utf8'), ctx);

test('adapter decodes nested html/text parts and lists attachments without content', () => {
  const m = ctx.apiMessageAdapter_({ id: '18c3f2a9b7d41e05', threadId: '18c3f2a9b7d40000', payload: {
    mimeType: 'multipart/mixed', parts: [
      { mimeType: 'multipart/alternative', parts: [
        { mimeType: 'text/plain', body: { data: b64('Pay the invoice today – thanks') } },
        { mimeType: 'text/html', body: { data: b64('<p>Pay the invoice <b>today</b> – thanks</p>') } }] },
      { mimeType: 'application/pdf', filename: 'Invoice.pdf', body: { attachmentId: 'ANGj', size: 52311 } }] } });
  assert.strictEqual(m.getId(), '18c3f2a9b7d41e05');
  assert.strictEqual(m.getThread().getId(), '18c3f2a9b7d40000');
  assert.strictEqual(m.getBody(), '<p>Pay the invoice <b>today</b> – thanks</p>');
  assert.strictEqual(m.getPlainBody(), 'Pay the invoice today – thanks');
  const a = m.getAttachments();
  assert.deepStrictEqual([a.length, a[0].getName(), a[0].getContentType(), a[0].getSize()], [1, 'Invoice.pdf', 'application/pdf', 52311]);
});

test('plain-text-only message falls back to text for the body; invalid tickets render an inert page', () => {
  const m = ctx.apiMessageAdapter_({ id: 'abc123', threadId: 't1', payload: { mimeType: 'text/plain', body: { data: b64('hello') } } });
  assert.strictEqual(m.getBody(), 'hello');
  const page = ctx.scanPageHtml_('');
  assert.ok(page.includes('var T="";') && !/<script[^>]*src=/.test(page));
  assert.ok(ctx.SCAN_TICKET_RE.test('a'.repeat(32)) && !ctx.SCAN_TICKET_RE.test('x"</script><script>alert(1)//aaaaaaaaaaaa'));
});

test('doGet uses only real HtmlService options (regression: "argument cannot be empty: mode")', () => {
  const calls = [];
  const out = { setTitle(t) { calls.push(['title', t]); return out; },
    setXFrameOptionsMode(m) { if (m === undefined || m === null) throw new Error('The argument cannot be empty: mode'); calls.push(['xfo', m]); return out; } };
  ctx.HtmlService = { createHtmlOutput: (h) => { calls.push(['html', h.length > 0]); return out; },
    XFrameOptionsMode: { ALLOWALL: 'ALLOWALL', DEFAULT: 'DEFAULT' } };  // the real enum has no DENY
  assert.strictEqual(ctx.doGet({ parameter: { t: 'a'.repeat(32) } }), out);
  assert.ok(calls.some((c) => c[0] === 'xfo' && c[1] === 'ALLOWALL'), 'frameable so the dashboard can run it inline');
  assert.strictEqual(ctx.doGet({}), out);  // missing ticket renders the inert error page, never throws
});

test('scan batch skips messages received before the selected range (exact received-time cutoff)', () => {
  const analyzed = [];
  const cutoff = Date.UTC(2026, 10, 5, 12, 0, 0);
  ctx.getSettings_ = () => ({ url: 'https://b.example', apiKey: 'k' });
  ctx.getGrantedScopes_ = () => ['gmail.readonly'];
  ctx.accountKey_ = () => 'k'.repeat(64);
  ctx.UrlFetchApp = { fetch: () => ({ getResponseCode: () => 200, getContentText: () => '{}' }) };
  ctx.newTimer_ = () => ({});
  ctx.buildPayload_ = (m) => ({ id: m.getId() });
  ctx.callAnalyze_ = (s, p, t, id, received) => analyzed.push([id, received]);
  const msgs = { aaaaaa01: cutoff - 1000, aaaaaa02: cutoff, aaaaaa03: cutoff + 3600e3 };
  ctx.Gmail = { Users: { Messages: { get: (_, id) => ({ id, threadId: 't', internalDate: String(msgs[id]), payload: { mimeType: 'text/plain', body: {} } }) } } };
  const totals = ctx.scanBatch('t'.repeat(32), Object.keys(msgs), { state: 'running', total: 3, done: 0, skipped: 0, failed: 0, afterMs: cutoff });
  assert.deepStrictEqual([totals.done, totals.skipped, totals.failed], [2, 1, 0]);
  assert.strictEqual(JSON.stringify(analyzed), JSON.stringify([['aaaaaa02', cutoff], ['aaaaaa03', cutoff + 3600e3]]));  // boundary inclusive; Gmail time passed on
});

test('ROOT CAUSE regression: advanced-service byte-array bodies decode (they used to throw for every message)', () => {
  const m = ctx.apiMessageAdapter_({ id: 'abc12345', threadId: 't', payload: { mimeType: 'multipart/alternative', parts: [
    { mimeType: 'text/plain', headers: [{ name: 'Content-Type', value: 'text/plain; charset="UTF-8"' }], body: { data: javaBytes('Café – pay today') } },
    { mimeType: 'text/html', headers: [{ name: 'Content-Type', value: 'text/html; charset=ISO-8859-1' }], body: { data: javaBytes('<p>Caf\u00e9</p>', 'latin1') } }] } });
  assert.strictEqual(m.getPlainBody(), 'Café – pay today');
  assert.strictEqual(m.getBody(), '<p>Café</p>');
  assert.throws(() => ctx.Utilities.base64DecodeWebSafe(String(javaBytes('<p>x</p>'))), /Could not decode/);  // the old code path
});

test('failures are counted and the first real error is reported (no email content)', () => {
  let reported = null;
  ctx.UrlFetchApp = { fetch: (url, o) => { if (url.endsWith('/v1/scan/progress')) reported = JSON.parse(o.payload); return { getResponseCode: () => 200, getContentText: () => '{}' }; } };
  ctx.Gmail = { Users: { Messages: { get: () => { throw new Error('API call to gmail.users.messages.get failed with error: Backend Error'); } } } };
  const t = ctx.scanBatch('t'.repeat(32), ['bbbbbb01', 'bbbbbb02'], { state: 'running', total: 2, done: 0, skipped: 0, failed: 0, afterMs: 0 });
  assert.deepStrictEqual([t.done, t.failed], [0, 2]);
  assert.match(reported.error, /messages\.get failed/);
  assert.strictEqual(reported.failed, 2);
});
