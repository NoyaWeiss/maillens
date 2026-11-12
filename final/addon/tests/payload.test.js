// Payload builder under realistic extremes (mocked Gmail; the shapes match GmailApp / Gmail API).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function ctxWith(threadSize, body = '') {
  const H = (n, v) => ({ name: n, value: v });
  const headers = (i) => [H('From', `Person ${i} <p${i}@corp.example>`), H('To', 'me@example.com'),
    H('Authentication-Results', 'mx.google.com; dkim=pass header.i=@corp.example')];
  const msgs = Array.from({ length: threadSize }, (_, i) => ({ id: 'm' + i, payload: { headers: headers(i) } }));
  const current = {
    getId: () => 'm' + (threadSize - 1), getThread: () => ({ getId: () => 't', getMessages: () => [] }),
    getBody: () => body, getPlainBody: () => body, getAttachments: () => [],
  };
  const ctx = { console, Gmail: { Users: { Messages: { get: (_, id) => msgs.find((m) => m.id === id) },
    Threads: { get: () => ({ messages: msgs }) } } }, CacheService: { getUserCache: () => ({ get: () => null, put() {} }) } };
  vm.createContext(ctx);
  for (const f of ['Extract.js', 'Headers.js', 'Body.js', 'Relationship.js', 'Auth.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx, { filename: f });
  }
  return { ctx, current };
}

test('long thread: digest is capped at the 5 most recent earlier messages, count is real', () => {
  const { ctx, current } = ctxWith(60);
  const d = ctx.readThreadDigest_(current, ['gmail.readonly']);
  assert.strictEqual(d.count, 60);
  assert.strictEqual(d.entries.length, 5);
  assert.match(d.entries[4].from_header, /p58@/);  // the message right before the open one
});

test('empty email produces a valid, bounded payload', () => {
  const { ctx, current } = ctxWith(1, '');
  ctx.relationshipFacts_ = () => null;
  const p = ctx.buildPayload_(current, ['gmail.readonly']);
  assert.strictEqual(p.message.html_body, '');
  assert.strictEqual(p.thread.length, 0);
  assert.ok(JSON.stringify(p).length < 5000);
});

test('oversized body is truncated to the backend field limits', () => {
  const { ctx, current } = ctxWith(1, 'x'.repeat(500000));
  ctx.relationshipFacts_ = () => null;
  const p = ctx.buildPayload_(current, ['gmail.readonly']);
  assert.strictEqual(p.message.html_body.length, 200000);
  assert.strictEqual(p.message.text_body.length, 100000);
});
