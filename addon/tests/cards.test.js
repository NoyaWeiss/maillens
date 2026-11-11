// Renders every card the add-on can produce, from REAL backend responses, through a strict
// CardService double that enforces Gmail's documented and observed render rules. Gmail rejects
// violations AFTER our code returns ("Unable to load content"), so they must be caught here.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const STYLE = { FILLED: 'FILLED', OUTLINED: 'OUTLINED', FILLED_TONAL: 'FILLED_TONAL', BORDERLESS: 'BORDERLESS' };

function strictCardService() {
  const errors = [];
  const fail = (m) => errors.push(m);
  const nonEmpty = (what, v) => { if (v === undefined || v === null || String(v).trim() === '') fail(`${what} is empty`); };
  const chain = (obj) => new Proxy(obj, { get: (t, k) => (k in t ? t[k] : () => chain(t)) });

  const widget = (kind) => {
    const w = { kind, text: undefined, top: undefined, bottom: undefined, icon: undefined, buttons: [] };
    return chain(Object.assign(w, {
      setText(v) { nonEmpty(`${kind}.text`, v); w.text = v; return this; },
      setTopLabel(v) { nonEmpty(`${kind}.topLabel`, v); w.top = v; return this; },
      setBottomLabel(v) { nonEmpty(`${kind}.bottomLabel`, v); w.bottom = v; return this; },
      setTitle(v) { nonEmpty(`${kind}.title`, v); w.title = v; return this; },
      setStartIcon(i) { w.icon = i; return this; },
      setTextButtonStyle(s) { w.style = s; return this; },
      addButton(b) { w.buttons.push(b); return this; },
    }));
  };
  const validateWidget = (w, where) => {
    if (w.kind === 'DecoratedText') {
      nonEmpty(`${where} DecoratedText.text`, w.text);
      if (!w.top && !w.bottom && !w.icon) fail(`${where} DecoratedText needs a label or an icon`);
    }
    if (w.kind === 'TextParagraph') nonEmpty(`${where} TextParagraph.text`, w.text);
    if (w.kind === 'ButtonSet' && !w.buttons.length) fail(`${where} ButtonSet has no buttons`);
  };

  const built = [];
  const CardService = {
    TextButtonStyle: STYLE,
    newCardBuilder: () => {
      const card = { sections: [], footer: null };
      return chain(Object.assign(card, {
        addSection(s) { card.sections.push(s); return this; },
        setFixedFooter(f) { card.footer = f; return this; },
        build() {
          if (!card.sections.length) fail('card has no sections');
          card.sections.forEach((s, i) => {
            if (!s.widgets.length) fail(`section ${i} ("${s.header || ''}") has no widgets`);
            if (s.collapsible && !(s.num >= 1)) fail(`collapsible section "${s.header}" hides every widget`);
            s.widgets.forEach((w) => validateWidget(w, `section ${i}`));
          });
          if (card.footer) {
            if (!card.footer.primary) fail('fixed footer without a primary button');
            else if (card.footer.primary.style !== STYLE.FILLED) fail('footer primary button must be FILLED');
            if (card.footer.secondary && card.footer.secondary.style !== STYLE.OUTLINED) fail('footer secondary must be OUTLINED');
          }
          built.push(card);
          return card;
        },
      }));
    },
    newCardSection: () => {
      const s = { widgets: [], collapsible: false, num: undefined, header: '' };
      return chain(Object.assign(s, {
        addWidget(w) { s.widgets.push(w); return this; },
        setHeader(h) { nonEmpty('section.header', h); s.header = h; return this; },
        setCollapsible(c) { s.collapsible = c; return this; },
        setNumUncollapsibleWidgets(n) { s.num = n; return this; },
      }));
    },
    newFixedFooter: () => {
      const f = { primary: null, secondary: null };
      return chain(Object.assign(f, {
        setPrimaryButton(b) { f.primary = b; return this; },
        setSecondaryButton(b) { if (!f.primary) fail('secondary footer button set before primary'); f.secondary = b; return this; },
      }));
    },
    newMaterialIcon: () => {
      const m = {};
      return chain(Object.assign(m, { setName(n) { nonEmpty('MaterialIcon.name', n); m.name = n; return this; } }));
    },
    newIconImage: () => chain({}),
    newCardHeader: () => widget('header'),
    newDecoratedText: () => widget('DecoratedText'),
    newTextParagraph: () => widget('TextParagraph'),
    newTextButton: () => widget('TextButton'),
    newButtonSet: () => widget('ButtonSet'),
    newTextInput: () => widget('TextInput'),
    newAction: () => chain({}),
  };
  return { CardService, errors, built };
}

const responses = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'responses.json'), 'utf8'));

function load(cs, dev) {
  const ctx = { CardService: cs, CacheService: { getUserCache: () => ({ put() {}, get: () => null }) },
    PropertiesService: { getUserProperties: () => ({ getProperty: () => '' }) }, console };
  if (dev) ctx.DEV_DEFAULTS = { url: 'https://x', apiKey: 'k', dev: true };
  vm.createContext(ctx);
  for (const f of ['Cards.js', 'Auth.js', 'Settings.js', 'Extract.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', f), 'utf8'), ctx, { filename: f });
  }
  return ctx;
}

const texts = (card) => card.sections.flatMap((s) => s.widgets.map((w) => [w.top, w.text, w.bottom].filter(Boolean).join(' | ')));

for (const [name, r] of Object.entries(responses)) {
  for (const granted of [['gmail.readonly'], []]) {
    for (const dev of [false, true]) {
      test(`valid cards: ${name} (${granted.length ? 'mailbox' : 'no mailbox'}, ${dev ? 'dev' : 'prod'})`, () => {
        const { CardService, errors, built } = strictCardService();
        const ctx = load(CardService, dev);
        ctx.buildResultCard_(r, 'msg1', granted);
        ctx.buildTechnicalCard_(r, 'msg1');
        assert.deepStrictEqual(errors, []);
        const [main, tech] = built;
        assert.ok(main.footer && main.footer.primary, 'main card has the fixed footer');
        const probe = texts(tech).some((t) => /Developer/.test(t)) || tech.sections.some((s) => s.header === 'Developer');
        assert.strictEqual(probe, dev, 'developer probe only in dev builds');
      });
    }
  }
}

test('approved compact layout: <=2 why rows, <=2 actions, no bar for Inconclusive, quiet Low', () => {
  for (const [name, r] of Object.entries(responses)) {
    const { CardService, built } = strictCardService();
    load(CardService, false).buildResultCard_(r, 'm', ['gmail.readonly']);
    const main = built[0];
    const all = texts(main).join('\n');
    const whyRows = main.sections.flatMap((s) => s.widgets).filter((w) => w.kind === 'DecoratedText' && /^Claims:|^Asks|^Advice/.test(w.top || ''));
    assert.ok(whyRows.length <= 2, `${name}: ${whyRows.length} why rows`);
    const actionLines = (all.match(/<b>\d\.<\/b>/g) || []).length;
    assert.ok(actionLines <= 2, `${name}: ${actionLines} actions`);
    if (r.verdict === 'INCONCLUSIVE') assert.ok(!all.includes('▰'), `${name}: no score bar for Inconclusive`);
    if (r.verdict === 'LOW') assert.ok(!/Claims:/.test(all), `${name}: Low card shows no claim/reality alarm rows`);
  }
});

test('no sentence is repeated on the main card (T2 advice once; T5 summary differs from the rows)', () => {
  for (const [name, r] of Object.entries(responses)) {
    const { CardService, built } = strictCardService();
    load(CardService, false).buildResultCard_(r, 'm', ['gmail.readonly']);
    const all = texts(built[0]).join('\n');
    assert.ok((all.match(/directly/g) || []).length <= 1, `${name}: advice repeated`);
    for (const f of r.findings) assert.ok(!r.headline.includes(f.reality), `${name}: headline repeats a finding`);
    if (r.verdict === 'INCONCLUSIVE') assert.ok(!all.includes(r.archetype) || r.archetype === 'No attack pattern', `${name}: archetype on Inconclusive`);
  }
});

test('T5 shows the takeover reason, the irreversible request and the folded consequence', () => {
  const { CardService, built } = strictCardService();
  load(CardService, false).buildResultCard_(responses.t5, 'm', ['gmail.readonly']);
  const all = texts(built[0]).join('\n');
  assert.match(all, /HIGH RISK/);
  assert.match(all, /Asks for something irreversible/);
  assert.match(all, /unrecoverable/);
});

test('error and settings cards are valid', () => {
  for (const dev of [false, true]) {
    const { CardService, errors } = strictCardService();
    const ctx = load(CardService, dev);
    ctx.buildErrorCard_(new Error('The MailLens backend is unreachable. No verdict was produced.'), 'm', 'call backend', []);
    ctx.buildErrorCard_(new Error("Metadata scope doesn't allow format FULL"), 'm', 'read open-message body', null);
    ctx.buildErrorCard_(new Error('weird <script> internal'), 'm', 'render', ['gmail.readonly']);
    ctx.buildSettingsCard_('Backend not configured yet.');
    ctx.buildSettingsCard_();
    assert.deepStrictEqual(errors, []);
  }
});

test('production error card hides raw runtime text', () => {
  const { CardService, built } = strictCardService();
  load(CardService, false).buildErrorCard_(new Error('Exception: internal detail XYZ'), 'm', 'render', []);
  assert.ok(!texts(built[0]).join('\n').includes('XYZ'));
});
