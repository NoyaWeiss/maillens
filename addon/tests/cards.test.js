// Renders every card the add-on can produce, from REAL backend responses, through a strict
// CardService double enforcing Gmail's documented and observed render rules, plus the approved
// Phase 2 v3 design rules (structure, headings per verdict, Variant C isolation, no raw addresses).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const STYLE = { FILLED: 'FILLED', OUTLINED: 'OUTLINED', FILLED_TONAL: 'FILLED_TONAL', BORDERLESS: 'BORDERLESS' };
const LRI = '⁦', PDI = '⁩';

function strictCardService() {
  const errors = [];
  const fail = (m) => errors.push(m);
  const nonEmpty = (what, v) => { if (v === undefined || v === null || String(v).trim() === '') fail(`${what} is empty`); };
  const chain = (obj) => new Proxy(obj, { get: (t, k) => (k in t ? t[k] : () => chain(t)) });
  const strings = [];  // every string rendered anywhere, for the isolation check
  const record = (what, v) => { nonEmpty(what, v); strings.push(String(v)); };

  const widget = (kind) => {
    const w = { kind, buttons: [] };
    return chain(Object.assign(w, {
      setText(v) { record(`${kind}.text`, v); w.text = v; return this; },
      setTopLabel(v) { record(`${kind}.topLabel`, v); w.top = v; return this; },
      setBottomLabel(v) { record(`${kind}.bottomLabel`, v); w.bottom = v; return this; },
      setTitle(v) { record(`${kind}.title`, v); w.title = v; return this; },
      setSubtitle(v) { record(`${kind}.subtitle`, v); return this; },
      setStartIcon(i) { w.icon = i; return this; },
      setTextButtonStyle(s) { w.style = s; return this; },
      addButton(b) { w.buttons.push(b); return this; },
    }));
  };
  const built = [];
  const CardService = {
    TextButtonStyle: STYLE,
    newCardBuilder: () => {
      const card = { sections: [], header: null };
      return chain(Object.assign(card, {
        addSection(s) { card.sections.push(s); return this; },
        setHeader(h) { card.header = h; return this; },
        build() {
          if (!card.sections.length) fail('card has no sections');
          card.sections.forEach((s, i) => {
            if (!s.widgets.length) fail(`section ${i} ("${s.header || ''}") has no widgets`);
            if (s.collapsible && !(s.num >= 1)) fail(`collapsible section "${s.header}" hides every widget`);
            s.widgets.forEach((w) => {
              if (w.kind === 'DecoratedText' && !w.top && !w.bottom && !w.icon) fail('DecoratedText needs a label or an icon');
              if (w.kind === 'ButtonSet' && !w.buttons.length) fail('ButtonSet has no buttons');
            });
          });
          built.push(card);
          return card;
        },
      }));
    },
    newCardSection: () => {
      const s = { widgets: [], collapsible: false, header: '' };
      return chain(Object.assign(s, {
        addWidget(w) { s.widgets.push(w); return this; },
        setHeader(h) { record('section.header', h); s.header = h; return this; },
        setCollapsible(c) { s.collapsible = c; return this; },
        setNumUncollapsibleWidgets(n) { s.num = n; return this; },
      }));
    },
    newMaterialIcon: () => { const m = {}; return chain(Object.assign(m, { setName(n) { nonEmpty('MaterialIcon.name', n); return this; } })); },
    newIconImage: () => chain({}),
    newCardHeader: () => widget('header'),
    newDecoratedText: () => widget('DecoratedText'),
    newTextParagraph: () => widget('TextParagraph'),
    newTextButton: () => widget('TextButton'),
    newButtonSet: () => widget('ButtonSet'),
    newTextInput: () => widget('TextInput'),
    newAction: () => chain({}),
  };
  return { CardService, errors, built, strings };
}

const responses = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'responses.json'), 'utf8'));

function load(cs, dev) {
  const ctx = { CardService: cs, CacheService: { getUserCache: () => ({ put() {}, get: () => null }) },
    PropertiesService: { getUserProperties: () => ({ getProperty: () => '' }) }, console };
  if (dev) ctx.DEV_DEFAULTS = { url: 'https://x', apiKey: 'k', dev: true };
  vm.createContext(ctx);
  for (const f of ['Cards.js', 'Auth.js', 'Extract.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx, { filename: f });
  }
  return ctx;
}

const plain = (s) => String(s).replace(/<[^>]+>/g, '')
  .replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
/** Every <br>-separated line must be one isolate: starts with LRI, ends with PDI (tags ignored). */
function assertIsolated(strings, where) {
  for (const s of strings) {
    for (const line of String(s).split('<br>')) {
      const p = plain(line);
      if (!p.trim()) continue;
      assert.ok(p.startsWith(LRI) && p.endsWith(PDI), `${where}: line not isolated: ${JSON.stringify(p)}`);
    }
  }
}
const firstText = (section) => plain(section.widgets[0].text || '').replace(/[⁦⁩]/g, '');
const mainText = (card) => card.sections.flatMap((s) => s.widgets.flatMap((w) => [w.text, w.top, w.bottom])).filter(Boolean)
  .map(plain).join('\n').replace(/[⁦⁩]/g, '');

const HEADINGS = {
  HIGH: ['Risk assessment', 'Why this email is suspicious', 'What could happen?', 'What should you do?'],
  SUSPICIOUS: ['Risk assessment', 'Why this needs a second look', 'What could happen?', 'What should you do?'],
  INCONCLUSIVE: ['Risk assessment', "Why we can't be sure", 'What could happen?', 'What should you do?'],
};

for (const [name, r] of Object.entries(responses)) {
  for (const granted of [['gmail.readonly'], []]) {
    for (const dev of [false, true]) {
      test(`v3 cards: ${name} (${granted.length ? 'mailbox' : 'no mailbox'}, ${dev ? 'dev' : 'prod'})`, () => {
        const { CardService, errors, built, strings } = strictCardService();
        const ctx = load(CardService, dev);
        ctx.buildResultCard_(r, 'msg1', granted);
        ctx.buildTechnicalCard_(r, 'msg1');
        assert.deepStrictEqual(errors, []);
        assertIsolated(strings, name);

        const [main, tech] = built;
        assert.strictEqual(main.header, null, 'no duplicate MailLens header on the main card');
        const headings = main.sections.map(firstText);
        const expected = r.verdict === 'LOW'
          ? ['Risk assessment'].concat(r.actions.length ? ['Before you act'] : [])
          : HEADINGS[r.verdict];
        assert.deepStrictEqual(headings.filter((h) => expected.includes(h) || /^Risk|^Why|^What|^Before/.test(h)), expected);
        const last = main.sections[main.sections.length - 1].widgets[0];
        assert.strictEqual(last.kind, 'ButtonSet');
        assert.strictEqual(last.buttons[0].style, 'FILLED_TONAL');
        assert.strictEqual(last.buttons[1].style, 'BORDERLESS');
        assert.ok(!/@|https?:\/\/|hxxp/.test(mainText(main)), `${name}: raw address or URL on main card`);

        const techHeaders = tech.sections.map((s) => plain(s.header).replace(/[⁦⁩]/g, ''));
        for (const h of ['How the verdict was reached', 'Evidence', 'Coverage and confidence', 'Limits and assumptions']) {
          assert.ok(techHeaders.includes(h), `${name}: technical view lacks "${h}"`);
        }
        assert.strictEqual(techHeaders.includes('Developer'), dev, 'developer tools only in dev builds');
        assert.ok(!techHeaders.includes('Attack story'), 'attack story no longer duplicated');
      });
    }
  }
}

test('owner refinements visible on the cards', () => {
  const { CardService, built } = strictCardService();
  const ctx = load(CardService, false);
  ctx.buildResultCard_(responses.t5, 'm', ['gmail.readonly']);
  const t5 = mainText(built[0]);
  assert.match(t5, /Possible vendor impersonation/);
  assert.match(t5, /Risk index 75\/100/);
  assert.match(t5, /may be difficult to recover/);
  ctx.buildResultCard_(responses.t9, 'm', ['gmail.readonly']);
  assert.match(mainText(built[1]), /Risk index not available/);
  assert.ok(!mainText(built[1]).includes('▰'));
});

test('error and settings cards are valid and isolated', () => {
  for (const dev of [false, true]) {
    const { CardService, errors, strings } = strictCardService();
    const ctx = load(CardService, dev);
    ctx.buildErrorCard_(new Error('The MailLens backend is unreachable. No verdict was produced.'), 'm', 'call backend', []);
    ctx.buildErrorCard_(new Error("Metadata scope doesn't allow format FULL"), 'm', 'read open-message body', null);
    ctx.buildErrorCard_(new Error('weird <script> internal'), 'm', 'render', ['gmail.readonly']);
    assert.deepStrictEqual(errors, []);
    assertIsolated(strings, 'error card');
  }
});

test('production error card hides raw runtime text', () => {
  const { CardService, built } = strictCardService();
  load(CardService, false).buildErrorCard_(new Error('Exception: internal detail XYZ'), 'm', 'render', []);
  assert.ok(!mainText(built[0]).includes('XYZ'));
});

test('technical addresses get their own isolate', () => {
  const ctx = load(strictCardService().CardService, false);
  const out = ctx.escapeTokens_('Replies go to acme.supply.accounts@gmail.example now');
  assert.ok(out.includes(LRI + 'acme.supply.accounts@gmail.example' + PDI));
});
