// Failure paths: the add-on must turn every backend/Gmail failure into a clear "no verdict" state.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function load(fetchImpl, cacheGet = () => null) {
  const ctx = { console, UrlFetchApp: { fetch: fetchImpl }, CacheService: { getUserCache: () => ({ get: cacheGet, put() {} }) },
    CardService: { newActionResponseBuilder: () => ({ setNotification(n) { this.n = n; return this; }, build() { return { notification: this.n }; } }),
      newNotification: () => ({ setText(t) { this.text = t; return this; } }) } };
  vm.createContext(ctx);
  for (const f of ['Api.js', 'Dashboard.js', 'Body.js', 'Main.js', 'Settings.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx, { filename: f });
  }
  return ctx;
}
const resp = (code, body = '{}') => () => ({ getResponseCode: () => code, getContentText: () => body });
const S = { url: 'https://svc.example', apiKey: 'k' };

test('invalid API key, rate limit, server errors and unreachable backend give clear messages', () => {
  assert.throws(() => load(resp(401)).callAnalyze_(S, {}), /rejected the API key/);
  assert.throws(() => load(resp(429)).callAnalyze_(S, {}), /rate-limiting/);
  for (const code of [500, 502, 503, 530, 404]) assert.throws(() => load(resp(code)).callAnalyze_(S, {}), /unavailable/);
  assert.throws(() => load(() => { throw new Error('Address unavailable: https://svc.example'); }).callAnalyze_(S, {}), /unreachable/);
});

test('malformed or tampered 200 responses never render as a verdict', () => {
  for (const body of ['not json', '{"verdict":"SAFE"}', '{"verdict":"LOW","headline":"x"}', '[]']) {
    assert.throws(() => load(resp(200, body)).callAnalyze_(S, {}));
  }
});

test('Re-analyze without a cached message token asks the user to reopen the email', () => {
  const out = load(resp(200)).onReanalyze({ parameters: { messageId: 'm1' } });
  assert.match(out.notification.text, /reopen the email/);
});
