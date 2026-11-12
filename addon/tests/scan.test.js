// Inbox scan: the Gmail API adapter must expose exactly what buildPayload_ reads, from real API shapes.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const b64 = (s) => Buffer.from(s, 'utf8').toString('base64').replace(/\+/g, '-').replace(/\//g, '_');
const ctx = {
  Utilities: {
    base64DecodeWebSafe: (d) => Buffer.from(d.replace(/-/g, '+').replace(/_/g, '/'), 'base64'),
    newBlob: (bytes) => ({ getDataAsString: () => Buffer.from(bytes).toString('utf8') }),
  },
};
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
  assert.ok(!calls.some((c) => c[0] === 'xfo' && c[1] === 'ALLOWALL'), 'page must stay non-frameable (DEFAULT)');
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
