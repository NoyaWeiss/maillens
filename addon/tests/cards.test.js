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
    const w = { kind, buttons: [], value: undefined };
    return chain(Object.assign(w, {
      setText(v) { record(`${kind}.text`, v); w.text = v; return this; },
      setTopLabel(v) { record(`${kind}.topLabel`, v); w.top = v; return this; },
      setBottomLabel(v) { record(`${kind}.bottomLabel`, v); w.bottom = v; return this; },
      setTitle(v) { record(`${kind}.title`, v); w.title = v; return this; },
      setSubtitle(v) { record(`${kind}.subtitle`, v); return this; },
      setStartIcon(i) { w.icon = i; return this; },
      setTextButtonStyle(s) { w.style = s; return this; },
      addButton(b) { w.buttons.push(b); return this; },
      setHint(v) { record(`${kind}.hint`, v); return this; },
      setValue(v) { w.value = v; strings.push(String(v)); return this; },
      setFieldName(v) { w.field = v; return this; },
      setButton(b) { w.button = b; return this; },
      setBackgroundColor(c) { w.bg = c; return this; },
      setOnClickAction(a) { w.action = a; return this; },
    }));
  };
  const built = [];
  const CardService = {
    TextButtonStyle: STYLE,
    ImageStyle: { CIRCLE: 'CIRCLE', SQUARE: 'SQUARE' },
    newDivider: () => ({ kind: 'Divider' }),
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
    newAction: () => { const a = {}; return chain(Object.assign(a, { setFunctionName(n) { a.fn = n; return this; }, setParameters(p) { a.params = p; return this; } })); },
  };
  return { CardService, errors, built, strings };
}

const responses = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'responses.json'), 'utf8'));

function load(cs, dev, opts = {}) {
  const props = opts.props || {};
  const ctx = { CardService: cs, CacheService: { getUserCache: () => ({ put() {}, get: () => null, remove() {}, removeAll() {} }) },
    PropertiesService: { getUserProperties: () => ({ getProperty: (k) => props[k] || '' }) }, console,
    UrlFetchApp: { fetch: () => { if (opts.statusCode === 'throw') throw new Error('dns'); return { getResponseCode: () => opts.statusCode || 200 }; } } };
  if (dev) ctx.DEV_DEFAULTS = { url: 'https://x', apiKey: 'k', dev: true };
  vm.createContext(ctx);
  for (const f of ['Cards.js', 'Auth.js', 'Extract.js', 'Settings.js', 'RenderTest.js', 'Dashboard.js']) {
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
        assert.strictEqual(last.buttons.length, 1, 'no Re-analyze button');
        assert.ok(!/@|https?:\/\/|hxxp/.test(mainText(main)), `${name}: raw address or URL on main card`);

        const techHeadings = tech.sections.map(firstText);
        const expectTech = ['How was this decision made?', 'Evidence found']
          .concat(r.limitations.length ? ['What may affect this result'] : []).concat(['Analysis coverage']);
        assert.deepStrictEqual(techHeadings, expectTech, `${name}: Detailed analysis sections`);
        assert.ok(!techHeadings.includes('Limitations'), 'no general Limitations section');
        if (r.verdict === 'LOW') assert.ok(/not a guarantee/.test(mainText(tech)), `${name}: Low-risk safety line`);
        const techText = mainText(tech) + '\n' + plain(tech.header.title || '');
        assert.ok(!/Request [0-9a-f]{12}|\bRule\b|Signals |\bH-[ABC]\b|\bS\d{1,2} ·|D\d ·|Developer|probe|direction test/i.test(techText),
          `${name}: developer-facing information in Detailed analysis`);
        assert.ok(tech.sections[tech.sections.length - 1].collapsible, 'Analysis coverage is collapsed by default');
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


test('welcome screen states: honest readiness, never "Protection ready"', () => {
  const cases = [
    [{ BACKEND_URL: 'https://svc.example', API_KEY: 'k' }, 200, 'Analysis service ready'],
    [{ BACKEND_URL: 'https://svc.example', API_KEY: 'k' }, 'throw', 'Analysis service unavailable'],
    [{ BACKEND_URL: 'https://svc.example', API_KEY: 'k' }, 401, 'Setup needs attention'],
    [{}, 200, 'Setup required'],
  ];
  for (const [props, statusCode, expected] of cases) {
    const { CardService, errors, built, strings } = strictCardService();
    load(CardService, false, { props, statusCode }).buildWelcomeCard_();
    assert.deepStrictEqual(errors, []);
    assertIsolated(strings.filter((x) => !/^https:/.test(x)), 'welcome');
    const text = mainText(built[0]);
    assert.match(text, new RegExp(expected));
    assert.ok(!/Protection ready|API key|Backend URL/.test(text), 'welcome shows no configuration fields');
    assert.strictEqual(/Open an email to analyze it/.test(text), expected === 'Analysis service ready');
  }
});

test('advanced settings never displays the saved API key; developer tools only in dev builds', () => {
  for (const dev of [false, true]) {
    const { CardService, errors, built, strings } = strictCardService();
    load(CardService, dev, { props: { BACKEND_URL: 'https://svc.example', API_KEY: 'SECRET-KEY-123' } }).buildAdvancedSettingsCard_();
    assert.deepStrictEqual(errors, []);
    assert.ok(!strings.some((x) => x.includes('SECRET-KEY-123')), 'API key must never be rendered');
    const keyInput = built[0].sections[0].widgets.find((w) => w.field === 'apiKey');
    assert.strictEqual(keyInput.value, undefined, 'API key input is never pre-filled');
    assert.strictEqual(mainText(built[0]).includes('Developer tools'), dev);
  }
});

test('production error card shows no step or raw error', () => {
  const { CardService, built } = strictCardService();
  load(CardService, false).buildErrorCard_(new Error('Exception: internal'), 'm', 'call backend', []);
  assert.ok(!/Step:|internal/.test(mainText(built[0])));
});

test('hostile strings in every backend field are escaped before rendering', () => {
  const evil = '<img src=x onerror=alert(1)><a href="javascript:alert(2)">x</a><script>alert(3)</script>';
  const KEEP = new Set(['verdict', 'basis', 'state', 'group', 'request_id', 'level', 'score']);
  const deep = (v, k) => KEEP.has(k) ? v : typeof v === 'string' ? evil + v : Array.isArray(v) ? v.map((x) => deep(x))
    : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([kk, x]) => [kk, deep(x, kk)])) : v;
  for (const [name, r] of Object.entries(responses)) {
    const { CardService, strings } = strictCardService();
    const ctx = load(CardService, false);
    const hostile = deep(r);
    ctx.buildResultCard_(hostile, 'm', ['gmail.readonly']);
    ctx.buildTechnicalCard_(hostile, 'm');
    for (const s of strings) {
      const withoutOurTags = String(s).replace(/<\/?b>|<br>|<\/font>|<font color="#[0-9a-f]{6}">/gi, '');
      assert.ok(!withoutOurTags.includes('<'), `${name}: unescaped markup reached a widget: ${withoutOurTags.slice(0, 120)}`);
    }
  }
});

test('regression: a stale URL saved in user settings never overrides the deployment config', () => {
  const { CardService } = strictCardService();
  const ctx = load(CardService, false, { props: { BACKEND_URL: 'https://old-dead-tunnel.trycloudflare.com', API_KEY: 'old' } });
  ctx.DEV_DEFAULTS = { url: 'https://current.trycloudflare.com', apiKey: 'current', dev: false };
  const s = ctx.getSettings_();
  assert.strictEqual(s.url, 'https://current.trycloudflare.com');
  assert.strictEqual(s.apiKey, 'current');
  assert.strictEqual(s.managed, true);
});

test('View full dashboard: below View detailed analysis on the result card, top of Home; FILLED navy, same wording', () => {
  const { CardService, built } = strictCardService();
  const ctx = load(CardService, false, { props: { backendUrl: 'https://b.example', apiKey: 'k' } });
  ctx.buildResultCard_(responses.t5, 'msg123', ['gmail.readonly'], 'canonical123');
  const card = built[0];
  const last = card.sections[card.sections.length - 1];
  assert.strictEqual(plain(last.widgets[0].buttons[0].text).replace(/[⁦⁩]/g, ''), 'View detailed analysis');
  const btn = last.widgets[1].buttons[0];  // directly below View detailed analysis
  assert.strictEqual(plain(btn.text).replace(/[⁦⁩]/g, ''), 'View full dashboard');
  assert.deepStrictEqual([btn.style, btn.bg], ['FILLED', '#1b2a4a']);
  assert.strictEqual(JSON.stringify([btn.action.fn, btn.action.params]), JSON.stringify(['onOpenDashboard', { messageId: 'canonical123' }]));
  assert.strictEqual(plain(firstText(card.sections[0])).replace(/[⁦⁩]/g, ''), 'Risk assessment');
  assert.ok(!Object.keys(card.sections[0].widgets[1]).includes('button'), 'assessment row itself unchanged');
  const ctx2 = load(CardService, false, { props: { backendUrl: 'https://b.example', apiKey: 'k' } });
  ctx2.serviceStatus_ = () => 'ready';
  const home = ctx2.buildWelcomeCard_();
  const hb = home.sections[0].widgets[0].buttons[0];
  assert.deepStrictEqual([plain(hb.text).replace(/[⁦⁩]/g, ''), hb.style, hb.bg], ['View full dashboard', 'FILLED', '#1b2a4a']);
  assert.ok(!Object.keys(hb.action).includes('params'), 'Home opens the account-level view (no email selected)');
  const homeText = mainText(home);
  for (const gone of ['The result appears here automatically.', 'Connected and ready to analyze emails.', 'checks whether an email is what it claims'])
    assert.ok(!homeText.includes(gone), gone);
});
