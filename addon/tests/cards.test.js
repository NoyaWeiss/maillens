// Renders every card the add-on can produce, from REAL backend responses, through a strict
// CardService double that enforces Gmail's render-time rules. Gmail rejects violations AFTER
// our code returns ("Unable to load content"), so they must be caught here.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function strictCardService() {
  const errors = [];
  const fail = (m) => errors.push(m);
  const nonEmpty = (what, v) => { if (v === undefined || v === null || String(v).trim() === '') fail(`${what} is empty`); };
  const chain = (obj) => new Proxy(obj, { get: (t, k) => (k in t ? t[k] : () => chain(t)) });
  const widget = (kind) => {
    const w = { kind, text: undefined };
    return chain(Object.assign(w, {
      setText(v) { nonEmpty(`${kind}.text`, v); w.text = v; return this; },
      setTopLabel(v) { nonEmpty(`${kind}.topLabel`, v); return this; },
      setBottomLabel(v) { nonEmpty(`${kind}.bottomLabel`, v); return this; },
      setTitle(v) { nonEmpty(`${kind}.title`, v); return this; },
    }));
  };
  const sections = [];
  const CardService = {
    newCardBuilder: () => {
      const card = { sections: [] };
      return chain(Object.assign(card, {
        addSection(s) { card.sections.push(s); return this; },
        build() {
          if (!card.sections.length) fail('card has no sections');
          card.sections.forEach((s, i) => {
            if (!s.widgets.length) fail(`section ${i} ("${s.header || ''}") has no widgets`);
            if (s.collapsible && !(s.num >= 1)) fail(`collapsible section "${s.header}" hides every widget`);
          });
          return card;
        },
      }));
    },
    newCardSection: () => {
      const s = { widgets: [], collapsible: false, num: undefined, header: '' };
      sections.push(s);
      return chain(Object.assign(s, {
        addWidget(w) { s.widgets.push(w); return this; },
        setHeader(h) { nonEmpty('section.header', h); s.header = h; return this; },
        setCollapsible(c) { s.collapsible = c; return this; },
        setNumUncollapsibleWidgets(n) { s.num = n; return this; },
      }));
    },
    newCardHeader: () => widget('header'),
    newDecoratedText: () => widget('DecoratedText'),
    newTextParagraph: () => widget('TextParagraph'),
    newTextButton: () => widget('TextButton'),
    newTextInput: () => widget('TextInput'),
    newAction: () => chain({}),
  };
  return { CardService, errors };
}

const responses = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'responses.json'), 'utf8'));

function load(cs) {
  const ctx = { CardService: cs, CacheService: { getUserCache: () => ({ put() {}, get: () => null }) },
    PropertiesService: { getUserProperties: () => ({ getProperty: () => '' }) }, console };
  vm.createContext(ctx);
  for (const f of ['Cards.js', 'Auth.js', 'Settings.js', 'Extract.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx, { filename: f });
  }
  return ctx;
}

for (const [name, r] of Object.entries(responses)) {
  for (const granted of [['gmail.readonly'], []]) {
    test(`result + technical cards are valid: ${name} (${granted.length ? 'mailbox' : 'no mailbox'} grant)`, () => {
      const { CardService, errors } = strictCardService();
      const ctx = load(CardService);
      ctx.buildResultCard_(r, 'msg1', granted);
      ctx.buildTechnicalCard_(r, 'msg1');
      assert.deepStrictEqual(errors, []);
    });
  }
}

test('error and settings cards are valid', () => {
  const { CardService, errors } = strictCardService();
  const ctx = load(CardService);
  ctx.buildErrorCard_(new Error('The MailLens backend is unreachable.'), 'm', 'call backend', []);
  ctx.buildErrorCard_(new Error("Metadata scope doesn't allow format FULL"), 'm', 'read open-message body', null);
  ctx.buildSettingsCard_('Backend not configured yet.');
  ctx.buildSettingsCard_();
  assert.deepStrictEqual(errors, []);
});

test('regression: T1 (level-1 request, no findings) has no empty Claim vs. Reality section', () => {
  assert.strictEqual(responses.t1.findings.length, 0);
  assert.strictEqual(responses.t1.request.level, 1);
});
