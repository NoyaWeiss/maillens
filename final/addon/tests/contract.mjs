// Contract test: the add-on's real buildPayload_ (mocked Gmail) must be accepted by the running
// backend, on BOTH permission paths. In the metadata path, any RAW read throws, exactly like Gmail
// proving headers come only from format=metadata when a mailbox grant exists. Usage: node addon/tests/contract.mjs <baseUrl> <apiKey>
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const dir = path.dirname(fileURLToPath(import.meta.url));
const [base, key] = process.argv.slice(2);

const H = (name, value) => ({ name, value });
const AUTH = 'mx.google.com; dkim=pass header.i=@acmesupply.example; spf=pass smtp.mailfrom=acmesupply.example; ' +
  'dmarc=pass (p=REJECT) header.from=acmesupply.example';
const earlierHeaders = [H('Authentication-Results', AUTH), H('From', 'Acme Supply Billing <billing@acmesupply.example>'),
  H('To', 'me@example.com'), H('Subject', 'Re: PO 4471')];
const currentHeaders = [H('Authentication-Results', AUTH), H('From', 'Acme Supply Billing <billing@acmesupply.example>'),
  H('Reply-To', 'Acme Accounts <acme.supply.accounts@gmail.com>'), H('Subject', 'Re: PO 4471'), H('In-Reply-To', '<h4@x>')];
const BODY_HTML = '<p>Our bank details have changed, kindly wire the payment to our new account.</p>';
const toRaw = (hs) => hs.map((h) => `${h.name}: ${h.value}`).join('\r\n') + '\r\n\r\nbody';

function run(mailboxGranted) {
  const rawBlocked = () => { throw new Error("Metadata scope doesn't allow format RAW"); };

  const mk = (id, hs) => ({
    getId: () => id, getRawContent: mailboxGranted ? rawBlocked : () => toRaw(hs),
    getBody: () => BODY_HTML,
    getPlainBody: () => 'Our bank details have changed.', getAttachments: () => [],
    getThread: () => ({ getId: () => 't1', getMessages: () => [earlier, msg] }),
  });
  const earlier = mk('m1', earlierHeaders);
  const msg = mk('m2', currentHeaders);
  const Gmail = { Users: {
    Messages: { get: (_, id) => ({ id, payload: { headers: id === 'm2' ? currentHeaders : earlierHeaders } }) },
    Threads: { get: () => ({ messages: [{ id: 'm1', payload: { headers: earlierHeaders } },
                                        { id: 'm2', payload: { headers: currentHeaders } }] }) },
  } };
  const profile = { addrs: { 'billing@acmesupply.example': 2 }, byName: { 'acme supply billing': ['billing@acmesupply.example'] } };
  const ctx = { console, Gmail, CacheService: { getUserCache: () => ({ get: () => JSON.stringify(profile), put() {} }) } };
  vm.createContext(ctx);
  for (const f of ['Extract.js', 'Headers.js', 'Body.js', 'Relationship.js', 'Auth.js']) {
    vm.runInContext(fs.readFileSync(path.join(dir, '..', f), 'utf8'), ctx, { filename: f });
  }
  const granted = ['gmail.addons.current.message.readonly'].concat(mailboxGranted ? ['gmail.readonly'] : []);
  return ctx.buildPayload_(msg, granted);
}

let failed = false;
for (const mailboxGranted of [true, false]) {
  const payload = run(mailboxGranted);
  const resp = await fetch(base + '/v1/analyze', {
    method: 'POST', headers: { 'content-type': 'application/json', 'X-API-Key': key }, body: JSON.stringify(payload),
  });
  const body = await resp.json();
  const label = mailboxGranted ? 'gmail.readonly (headers via format=metadata, RAW never used)' : 'no mailbox scope (raw headers via message token)';
  if (resp.status !== 200 || body.verdict !== 'HIGH' || payload.message.auth_results.length !== 1 || payload.thread.length !== 1 || !payload.message.html_body) {
    failed = true;
    console.error('FAIL', label, resp.status, JSON.stringify(body).slice(0, 300));
  } else {
    console.log('OK  ', label, body.verdict, body.gate, body.vector, '| auth headers:', payload.message.auth_results.length,
      '| thread entries:', payload.thread.length, '| relationship:', payload.relationship ? 'sent' : 'null');
  }
}
process.exit(failed ? 1 : 0);
