/**
 * Rendering (Phase 2 design, docs/UI_PROPOSAL.md, compact variant).
 *
 * Rules that keep Gmail from rejecting a card at render time (which happens AFTER our code
 * returns, so try/catch can't see it): no section without widgets, no empty text or labels,
 * every DecoratedText has a label as well as any icon. Every card is rendered for all demo
 * scenarios through a strict CardService double in addon/tests/cards.test.js.
 *
 * Every string from the email or the backend passes through escapeHtml_. URLs arrive defanged
 * from the backend and are never rendered as links.
 */

var VERDICT_STYLE = {
  LOW: { label: 'LOW RISK', color: '#188038', icon: 'verified_user' },
  SUSPICIOUS: { label: 'SUSPICIOUS', color: '#e37400', icon: 'warning' },
  HIGH: { label: 'HIGH RISK', color: '#d93025', icon: 'gpp_bad' },
  INCONCLUSIVE: { label: 'INCONCLUSIVE', color: '#5f6368', icon: 'help' }
};
var GROUP_ICON = { IDENTITY: 'alternate_email', AUTH: 'lock_open', DEST: 'link', PAYLOAD: 'attach_file', DRIFT: 'forum' };
var GREY = '#5f6368';
var CACHE_TTL = 600;
var MAX_WHY_ROWS = 2;
var MAX_ACTIONS = 2;

// ------------------------------------------------------------------ main card
function buildResultCard_(r, messageId, granted) {
  try { CacheService.getUserCache().put('result_' + r.request_id, JSON.stringify(r), CACHE_TTL); } catch (e) { /* ignore */ }
  var style = VERDICT_STYLE[r.verdict];
  var card = CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('MailLens'));

  // 1. Verdict block: icon + coloured verdict + score + bar, archetype, one-line explanation.
  var top = CardService.newCardSection().addWidget(verdictWidget_(r, style));
  top.addWidget(CardService.newTextParagraph().setText(escapeHtml_(r.headline)));
  if (r.confidence === 'Limited') {
    top.addWidget(CardService.newTextParagraph().setText('<font color="' + GREY + '">Limited confidence · ' +
      Number(r.coverage_ran) + ' of ' + Number(r.coverage_applicable) + ' checks could run</font>'));
  }
  card.addSection(top);

  // 2. Why: at most two rows. Strongest finding first, then the request when it is elevated.
  var rows = whyRows_(r);
  if (rows.length) {
    var why = CardService.newCardSection();
    rows.forEach(function (w) { why.addWidget(w); });
    card.addSection(why);
  }

  // 3. What to do: at most two actions. Low cards carry their single piece of advice in the
  //    Advice row instead, so nothing is said twice.
  var actions = r.verdict === 'LOW' ? [] : (r.actions || []).slice(0, MAX_ACTIONS);
  if (actions.length) {
    card.addSection(CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(
      actions.map(function (a, i) { return '<b>' + (i + 1) + '.</b> ' + escapeHtml_(a); }).join('<br>'))));
  }

  if (granted && !hasMailboxAccess_(granted)) card.addSection(mailboxAccessSection_());

  card.setFixedFooter(CardService.newFixedFooter()
    .setPrimaryButton(CardService.newTextButton().setText('Technical evidence')
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED).setBackgroundColor(style.color)
      .setOnClickAction(CardService.newAction().setFunctionName('onShowTechnical')
        .setParameters({ requestId: String(r.request_id), messageId: String(messageId) })))
    .setSecondaryButton(reanalyzeButton_(messageId, CardService.TextButtonStyle.OUTLINED, 'Re-analyze')));
  return card.build();
}

function verdictWidget_(r, style) {
  var hasScore = r.score !== null && r.score !== undefined;
  var text = '<font color="' + style.color + '"><b>' + style.label + '</b></font>' +
    (hasScore ? '  ·  <b>' + Number(r.score) + '</b> / 100<br><font color="' + style.color + '">' +
      scoreBar_(Number(r.score)) + '</font>' : '');
  var w = CardService.newDecoratedText().setTopLabel('Verdict').setText(text).setWrapText(true);
  // Only an actual High/Suspicious verdict names an attack type; Inconclusive must not imply one.
  if ((r.verdict === 'HIGH' || r.verdict === 'SUSPICIOUS') && r.archetype) w.setBottomLabel(escapeHtml_(r.archetype));
  return withIcon_(w, style.icon);
}

/** 10 segments; Inconclusive gets no bar (a score would imply false precision). */
function scoreBar_(score) {
  var n = Math.max(1, Math.min(10, Math.round(score / 10)));
  return new Array(n + 1).join('▰') + new Array(10 - n + 1).join('▱');
}

function whyRows_(r) {
  var showRequest = r.request && r.request.level >= 2;
  // Low with an elevated request: a single advisory row instead of alarm vocabulary.
  if (r.verdict === 'LOW' && !r.findings.length) {
    if (!showRequest) return [];
    return [withIcon_(CardService.newDecoratedText().setTopLabel('Advice')
      .setText('It asks you to ' + escapeHtml_(lowerFirst_(r.request.label)) +
        '. If you need to, go to the site directly instead of using its links.')
      .setWrapText(true), 'info')];
  }
  var rows = [];
  r.findings.slice(0, showRequest ? MAX_WHY_ROWS - 1 : MAX_WHY_ROWS).forEach(function (f) {
    rows.push(withIcon_(CardService.newDecoratedText()
      .setTopLabel(escapeHtml_(truncate_('Claims: ' + f.claim, 90)))
      .setText('<font color="' + (f.level >= 2 ? VERDICT_STYLE.HIGH.color : VERDICT_STYLE.SUSPICIOUS.color) + '">' +
        escapeHtml_(f.reality) + '</font>')
      .setWrapText(true), GROUP_ICON[f.group] || 'report'));
  });
  if (showRequest) {
    rows.push(withIcon_(CardService.newDecoratedText()
      .setTopLabel(r.request.level === 3 ? 'Asks for something irreversible' : 'Asks you to')
      .setText('<b>' + escapeHtml_(r.request.label) + '</b>' + (r.pressure_cues.length
        ? '<br><font color="' + GREY + '">with pressure: ' + escapeHtml_(r.pressure_cues.join(', ')) + '</font>' : ''))
      .setWrapText(true), requestIcon_(r.request.label)));
  }
  // Folded Attack Story: its consequence sentence becomes the last row's bottom line.
  var consequence = (r.verdict === 'HIGH' || r.verdict === 'SUSPICIOUS') ? lastStoryLine_(r) : '';
  if (rows.length && consequence) rows[rows.length - 1].setBottomLabel(escapeHtml_(consequence));
  return rows;
}

function lastStoryLine_(r) {
  var s = r.story || [];
  return s.length >= 2 ? String(s[s.length - 1]) : '';
}

function requestIcon_(label) {
  var l = String(label).toLowerCase();
  if (/payment|bank|payroll|gift/.test(l)) return 'payments';
  if (/sign in|credential|code|password/.test(l)) return 'password';
  if (/remote/.test(l)) return 'devices';
  return 'priority_high';
}

function mailboxAccessSection_() {
  return CardService.newCardSection().addWidget(withIcon_(CardService.newDecoratedText()
    .setTopLabel('Relationship checks are off')
    .setText('Compare senders with people you have emailed.')
    .setWrapText(true)
    .setButton(CardService.newTextButton().setText('Enable')
      .setTextButtonStyle(CardService.TextButtonStyle.OUTLINED)
      .setOnClickAction(CardService.newAction().setFunctionName('onEnableMailboxAccess'))), 'group'));
}

function reanalyzeButton_(messageId, style, text) {
  return CardService.newTextButton().setText(text).setTextButtonStyle(style)
    .setOnClickAction(CardService.newAction().setFunctionName('onReanalyze')
      .setParameters({ messageId: String(messageId) }));
}

// ------------------------------------------------------------------ technical evidence card
function onShowTechnical(e) {
  var raw = CacheService.getUserCache().get('result_' + e.parameters.requestId);
  if (!raw) return notify_('Evidence expired. Use Re-analyze to refresh it.');
  var card = buildTechnicalCard_(JSON.parse(raw), e.parameters.messageId);
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card)).build();
}

function buildTechnicalCard_(r, messageId) {
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader()
    .setTitle('Technical evidence').setSubtitle('Request ' + escapeHtml_(r.request_id)));

  card.addSection(CardService.newCardSection().setHeader('Decision')
    .addWidget(CardService.newTextParagraph().setText(
      escapeHtml_(r.gate_explanation) +
      (r.pathway ? '<br><b>Pathway:</b> ' + escapeHtml_(r.pathway) : '') +
      '<br><b>Vector:</b> ' + escapeHtml_(r.vector) +
      '<br><font color="' + GREY + '">D strongest finding · A request level · E entities with strong findings · ' +
      'P pressure · N familiarity (0 known, 1 new, ? unknown)</font>' +
      '<br><b>Confidence:</b> ' + escapeHtml_(r.confidence) + ' · ' + Number(r.coverage_ran) + ' of ' +
      Number(r.coverage_applicable) + ' applicable checks ran')));

  var fs = CardService.newCardSection().setHeader('Findings (' + r.findings.length + ')');
  if (!r.findings.length) fs.addWidget(CardService.newTextParagraph().setText('None.'));
  r.findings.forEach(function (f) { fs.addWidget(findingWidget_(f)); });
  if (r.request) {
    fs.addWidget(CardService.newDecoratedText()
      .setTopLabel('S13 · ASK · level ' + Number(r.request.level) + ' · HEURISTIC')
      .setText(escapeHtml_(r.request.label)).setBottomLabel(escapeHtml_(r.request.excerpt || '-')).setWrapText(true));
  }
  card.addSection(fs);

  if (r.story && r.story.length) card.addSection(collapsible_('Attack story', [r.story.map(escapeHtml_).join('<br><br>')]));
  if (r.also_observed.length) {
    var ao = CardService.newCardSection().setHeader('Also observed (deduplicated)').setCollapsible(true)
      .setNumUncollapsibleWidgets(1);
    r.also_observed.forEach(function (f) { ao.addWidget(findingWidget_(f)); });
    card.addSection(ao);
  }
  if (r.suppressed.length) card.addSection(collapsible_('False-positive guards applied', [r.suppressed.map(escapeHtml_).join('<br>')]));

  var byState = { ran: [], unavailable: [], not_applicable: [] };
  r.checks.forEach(function (c) { (byState[c.state] || []).push(c.id + ' ' + c.name); });
  card.addSection(collapsible_('Checks', [
    '<b>Ran (' + byState.ran.length + '):</b> ' + escapeHtml_(byState.ran.join(', ')),
    '<b>Unavailable:</b> ' + escapeHtml_(byState.unavailable.join(', ') || 'none') +
      '<br><b>Not applicable:</b> ' + escapeHtml_(byState.not_applicable.join(', ') || 'none'),
    '<b>Out of scope:</b> ' + escapeHtml_(r.out_of_scope.join('; ')) +
      '<br><br><b>Assumptions:</b><br>' + r.assumptions.map(escapeHtml_).join('<br>')
  ]));

  if (isDevBuild_()) {
    card.addSection(CardService.newCardSection().setHeader('Developer').addWidget(probeButton_(messageId))
      .addWidget(CardService.newTextButton().setText('Text direction test (dev)')
        .setOnClickAction(CardService.newAction().setFunctionName('onBidiTest'))));
  }
  return card.build();
}

function findingWidget_(f) {
  return withIcon_(CardService.newDecoratedText()
    .setTopLabel(escapeHtml_(f.signal + ' · ' + f.group + levelTag_(f.level) + ' · ' + f.basis))
    .setText(escapeHtml_(f.reality))
    .setBottomLabel(escapeHtml_(f.entity + (f.excerpt ? ' · ' + f.excerpt : '')) || '-')
    .setWrapText(true), GROUP_ICON[f.group] || 'report');
}

function collapsible_(header, paragraphs) {
  var s = CardService.newCardSection().setHeader(header).setCollapsible(true).setNumUncollapsibleWidgets(1);
  paragraphs.forEach(function (p) { s.addWidget(CardService.newTextParagraph().setText(p || '-')); });
  return s;
}

function levelTag_(level) {
  return level === 3 ? ' · deliberate construct' : level === 2 ? ' · strong' : ' · weak';
}

// ------------------------------------------------------------------ error card
function buildErrorCard_(err, messageId, step, granted) {
  // Never green, never a verdict: say plainly that no verdict was produced.
  var message = String(err && err.message || err);
  var section = CardService.newCardSection()
    .addWidget(withIcon_(CardService.newDecoratedText().setTopLabel('Verdict')
      .setText('<font color="' + GREY + '"><b>NO VERDICT</b></font>')
      .setBottomLabel("MailLens couldn't analyze this email.").setWrapText(true), 'error'))
    .addWidget(CardService.newTextParagraph().setText(escapeHtml_(friendlyReason_(message)) + staleGrantHint_(message)))
    .addWidget(CardService.newButtonSet().addButton(reanalyzeButton_(messageId, CardService.TextButtonStyle.FILLED, 'Try again')))
    .addWidget(CardService.newTextParagraph().setText('<font color="' + GREY + '">Failed at: ' + escapeHtml_(step || 'unknown') +
      (isDevBuild_() ? ' · ' + escapeHtml_(message.slice(0, 300)) + ' · ' + scopeLine_(granted) : '') + '</font>'));
  if (isDevBuild_()) section.addWidget(probeButton_(messageId));
  return CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle('MailLens')).addSection(section).build();
}

/** Our own error messages are already user-facing; Google's raw runtime text is summarized. */
function friendlyReason_(message) {
  if (/^The MailLens backend|^The backend/.test(message)) return message;
  if (/metadata scope/i.test(message)) return 'An outdated permission is blocking access to this email.';
  if (/permission/i.test(message)) return 'MailLens is missing a permission it needs for this email.';
  if (/timed out|timeout|deadline/i.test(message)) return 'Gmail took too long to respond. Try again.';
  return 'Something went wrong while reading this email. Try again.';
}

/** An old gmail.metadata grant caps every read at headers only; tell the user how to reset it. */
function staleGrantHint_(message) {
  if (!/metadata scope/i.test(String(message))) return '';
  return '<br><br><b>Fix:</b> remove MailLens at myaccount.google.com/connections, then reopen this email and authorize again.';
}

function scopeLine_(granted) {
  if (!granted) return 'granted scopes unknown';
  return 'granted: ' + escapeHtml_(granted.join(', ') || '(none)');
}

// ------------------------------------------------------------------ shared helpers
/** Material icons are decoration only: every caller also sets a text label. */
function withIcon_(decoratedText, name) {
  try {
    decoratedText.setStartIcon(CardService.newIconImage().setMaterialIcon(CardService.newMaterialIcon().setName(name)));
  } catch (e) { /* runtime without MaterialIcon: the label alone keeps the widget valid */ }
  return decoratedText;
}

function isDevBuild_() {
  return typeof DEV_DEFAULTS !== 'undefined' && DEV_DEFAULTS && DEV_DEFAULTS.dev === true;
}

function probeButton_(messageId) {
  return CardService.newTextButton().setText('Run feasibility probe (dev)')
    .setOnClickAction(CardService.newAction().setFunctionName('onRunProbe')
      .setParameters({ messageId: String(messageId) }));
}

function lowerFirst_(s) {
  s = String(s || '');
  return s.charAt(0).toLowerCase() + s.slice(1);
}

function truncate_(s, n) {
  s = String(s == null ? '' : s);
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

function escapeHtml_(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
