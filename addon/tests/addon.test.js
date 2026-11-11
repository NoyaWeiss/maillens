// Unit tests for the add-on's pure functions. Run: node --test addon/tests
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ctx = {};
vm.createContext(ctx);
for (const f of ['Extract.js', 'Relationship.js', 'Cards.js', 'Api.js', 'Auth.js', 'Headers.js', 'Body.js']) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx, { filename: f });
}

test('escapeHtml_ neutralizes markup from email content', () => {
  assert.strictEqual(ctx.escapeHtml_('<img src=x onerror="a()">&\''),
    '&lt;img src=x onerror=&quot;a()&quot;&gt;&amp;&#39;');
});

test('parseAddressList_ handles quoted commas and bare addresses', () => {
  const r = ctx.parseAddressList_('"Cohen, Dana" <Dana@North.example>, bob@x.example, Eve <eve@y.example>');
  assert.deepStrictEqual(JSON.parse(JSON.stringify(r)), [
    { name: 'Cohen, Dana', address: 'dana@north.example' },
    { name: '', address: 'bob@x.example' },
    { name: 'Eve', address: 'eve@y.example' }]);
});

test('parseRawHeaders_ keeps order, unfolds, stops at body', () => {
  const raw = 'Authentication-Results: mx.google.com;\r\n dkim=pass\r\nAuthentication-Results: evil; x\r\n\r\nX-Body: no';
  const h = ctx.parseRawHeaders_(raw);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.allHeaders_(h, 'authentication-results'))), ['mx.google.com; dkim=pass', 'evil; x']);
  assert.strictEqual(ctx.firstHeader_(h, 'x-body'), null);
});

test('normalizeName_ is case/space/quote insensitive', () => {
  assert.strictEqual(ctx.normalizeName_('  "Dana   COHEN" '), 'dana cohen');
});

test('validateResponse_ rejects malformed backend responses', () => {
  assert.throws(() => ctx.validateResponse_({ verdict: 'SAFE' }));
  assert.throws(() => ctx.validateResponse_({ verdict: 'LOW', headline: 'x', request_id: 'r', vector: 'v' }));
});

test('apiHeaders_ keeps order and lowercases names', () => {
  const hs = ctx.apiHeaders_({ payload: { headers: [{ name: 'Authentication-Results', value: 'mx.google.com; a' },
    { name: 'Authentication-Results', value: 'evil; b' }] } });
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.allHeaders_(hs, 'authentication-results'))),
    ['mx.google.com; a', 'evil; b']);
});
