/**
 * Rendering: Phase 2 v3 (docs/UI_PROPOSAL.md, approved structure).
 *
 * Main card, fixed order: Risk assessment / Why ... / What could happen? / What should you do? /
 * [View detailed analysis] Re-analyze. Headings adapt to the verdict.
 *
 * Text direction (owner-selected Variant C, verified in Hebrew Gmail): CardService has no dir or
 * alignment control, so every English line is wrapped in a Unicode isolate (LRI U+2066 ... PDI U+2069)
 * by ltr_(). Each <br>-separated line is isolated separately, and addresses or domains inside technical
 * lines get their own inner isolate. Gmail still right-aligns text in an RTL interface; the design
 * keeps lines short so that stays readable.
 *
 * Render-time rules (Gmail rejects violations after our code returns): no empty sections, text or
 * labels; every DecoratedText has a label or icon. All enforced by addon/tests/cards.test.js.
 * Every string from the email or backend is HTML-escaped before it is wrapped.
 */

var LRI = '\u2066';
var PDI = '\u2069';
var VERDICT_STYLE = {
  HIGH: { label: 'High risk', color: '#c5221f', icon: 'gpp_bad', why: 'Why this email is suspicious' },
  SUSPICIOUS: { label: 'Suspicious', color: '#b06000', icon: 'warning', why: 'Why this needs a second look' },
  INCONCLUSIVE: { label: 'Inconclusive', color: '#5f6368', icon: 'help', why: "Why we can't be sure" },
  LOW: { label: 'Low risk', color: '#188038', icon: 'verified_user', why: '' }
};
var GREY = '#5f6368';
var CACHE_TTL = 600;

// ------------------------------------------------------------------ direction helpers (Variant C)
/** Isolates one line of already-escaped text (may contain inline tags). Empty stays empty. */
function ltr_(line) {
  line = String(line == null ? '' : line);
  return line === '' ? '' : LRI + line + PDI;
}

/** Isolates each line separately and joins them with <br>; empty lines are dropped. */
function ltrLines_(lines) {
  return lines.filter(function (l) { return l !== '' && l != null; }).map(ltr_).join('<br>');
}

var TOKEN_RE = /(hxxps?:\/\/[^\s<]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+|[A-Za-z0-9-]+(?:\.|\[\.\])[A-Za-z0-9-]+(?:(?:\.|\[\.\])[A-Za-z0-9-]+)*)/g;

/**
 * Labels (top/bottom labels, titles, hints, button text) are documented as plain text, so HTML-escaping
 * would show entities literally. Instead, data placed in a label has angle brackets removed: markup can
 * never be interpreted, whatever Gmail's renderer does.
 */
function plain_(s) {
  return String(s == null ? '' : s).replace(/[<>]/g, '');
}

/** Escapes, then gives each address, domain or defanged URL its own isolate (technical lines). */
function escapeTokens_(s) {
  return escapeHtml_(s).replace(TOKEN_RE, function (t) { return LRI + t + PDI; });
}

// ------------------------------------------------------------------ main card
function buildResultCard_(r, messageId, granted) {
  try { CacheService.getUserCache().put('result_' + r.request_id, JSON.stringify(r), CACHE_TTL); } catch (e) { /* ignore */ }
  var style = VERDICT_STYLE[r.verdict];
  var card = CardService.newCardBuilder();  // no header: Gmail already shows "MailLens" above the card

  // 1. Risk assessment
  // Compact "Full dashboard" link sits in the assessment row's button slot; the approved layout is unchanged.
  card.addSection(block_('Risk assessment', [assessmentWidget_(r, style)
    .setButton(dashboardButton_('Full dashboard', CardService.TextButtonStyle.BORDERLESS, messageId)),
    CardService.newTextParagraph().setText(ltr_(escapeHtml_(r.headline)))]));

  // 2. Why ... (not shown for Low)
  if (style.why && r.reasons.length) {
    card.addSection(block_(style.why, r.reasons.slice(0, 2).map(function (x) {
      return row_(reasonIcon_(x.title), x.title, x.summary, x.basis);
    })));
  }

  // 3. What could happen?
  if (r.impact) {
    card.addSection(block_('What could happen?', [CardService.newTextParagraph().setText(ltr_(escapeHtml_(r.impact)))]));
  }

  // 4. What should you do? (Low: "Before you act", only when there is something to act on)
  if (r.actions.length) {
    card.addSection(block_(r.verdict === 'LOW' ? 'Before you act' : 'What should you do?',
      r.actions.slice(0, 2).map(function (a) { return row_(actionIcon_(a.title), a.title, a.detail, ''); })));
  }

  if (granted && !hasMailboxAccess_(granted)) card.addSection(mailboxAccessSection_());

  // 5. View detailed analysis (tonal) · Re-analyze (borderless, visually secondary)
  card.addSection(CardService.newCardSection().addWidget(CardService.newButtonSet()
    .addButton(CardService.newTextButton().setText(ltr_('View detailed analysis'))
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED_TONAL)
      .setOnClickAction(CardService.newAction().setFunctionName('onShowTechnical')
        .setParameters({ requestId: String(r.request_id), messageId: String(messageId) })))
    .addButton(reanalyzeButton_(messageId, CardService.TextButtonStyle.BORDERLESS, 'Re-analyze'))));
  return card.build();
}

/** A main-card block: a bold heading line followed by its widgets, in one section. */
function block_(heading, widgets) {
  var s = CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(ltr_('<b>' + escapeHtml_(heading) + '</b>')));
  widgets.forEach(function (w) { s.addWidget(w); });
  return s;
}

/** Icon + bold title, one neutral sentence below, optional grey tag. */
function row_(icon, title, text, tag) {
  var w = CardService.newDecoratedText()
    .setText(ltrLines_(['<b>' + escapeHtml_(title) + '</b>', escapeHtml_(text)]))
    .setWrapText(true);
  if (tag) w.setBottomLabel(ltr_(plain_(tag)));
  return withIcon_(w, icon, title);
}

function assessmentWidget_(r, style) {
  var hasScore = r.score !== null && r.score !== undefined;
  var verdictLine = '<b><font color="' + style.color + '">' + style.label + '</font></b>';
  var indexLine = hasScore
    ? 'Risk index ' + Number(r.score) + '/100  <font color="' + style.color + '">' + scoreBar_(Number(r.score)) + '</font>'
    : 'Risk index not available';
  var w = CardService.newDecoratedText().setText(ltrLines_([verdictLine, indexLine])).setWrapText(true);
  if (r.category) w.setBottomLabel(ltr_(plain_(r.category)));
  return withIcon_(w, style.icon, style.label);
}

/** 10 segments, filled left to right inside the isolate. */
function scoreBar_(score) {
  var n = Math.max(1, Math.min(10, Math.round(score / 10)));
  return new Array(n + 1).join('▰') + new Array(10 - n + 1).join('▱');
}

function reasonIcon_(title) {
  var t = String(title).toLowerCase();
  if (/reply/.test(t)) return 'reply';
  if (/bank|payment|card|gift|payroll/.test(t)) return 'account_balance';
  if (/sign in|code|password/.test(t)) return 'password';
  if (/link/.test(t)) return 'link';
  if (/attachment|file|document|archive/.test(t)) return 'attach_file';
  if (/domain/.test(t)) return 'language';
  if (/verified|authentication/.test(t)) return 'gpp_maybe';
  if (/hidden/.test(t)) return 'visibility_off';
  if (/install|remote/.test(t)) return 'devices';
  if (/name|sender|known/.test(t)) return 'person';
  return 'info';
}

function actionIcon_(title) {
  var t = String(title).toLowerCase();
  if (/verify|call|phone/.test(t)) return 'call';
  if (/report/.test(t)) return 'flag';
  if (/site directly/.test(t)) return 'open_in_new';
  if (/confirm|contact/.test(t)) return 'how_to_reg';
  if (/^don't|^do not/.test(t)) return 'block';
  return 'check_circle';
}

function mailboxAccessSection_() {
  return CardService.newCardSection().addWidget(withIcon_(CardService.newDecoratedText()
    .setText(ltrLines_(['<b>Relationship checks are off</b>', 'Compare senders with people you have emailed.']))
    .setWrapText(true)
    .setButton(CardService.newTextButton().setText(ltr_('Enable'))
      .setTextButtonStyle(CardService.TextButtonStyle.OUTLINED)
      .setOnClickAction(CardService.newAction().setFunctionName('onEnableMailboxAccess'))), 'group', 'Relationship checks'));
}

function reanalyzeButton_(messageId, style, text) {
  return CardService.newTextButton().setText(ltr_(text)).setTextButtonStyle(style)
    .setOnClickAction(CardService.newAction().setFunctionName('onReanalyze')
      .setParameters({ messageId: String(messageId) }));
}

// ------------------------------------------------------------------ detailed analysis (v4, approved)
function onShowTechnical(e) {
  var raw = CacheService.getUserCache().get('result_' + e.parameters.requestId);
  if (!raw) return notify_('Details expired. Use Re-analyze to refresh them.');
  var card = buildTechnicalCard_(JSON.parse(raw), e.parameters.messageId);
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card)).build();
}

/**
 * User-facing "Detailed analysis": decision, evidence, email-specific limitations (only when relevant),
 * coverage. No request IDs,
 * rule IDs, signal vectors or developer tools (those live only in dev-build Developer tools).
 * Concise by default: check lists and safeguards are collapsed.
 */
function buildTechnicalCard_(r) {
  var style = VERDICT_STYLE[r.verdict];
  var subtitle = style.label + (r.score === null || r.score === undefined ? '' : ' · risk index ' + Number(r.score) + '/100');
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader()
    .setTitle(ltr_('Detailed analysis')).setSubtitle(ltr_(subtitle)));

  // A. How was this decision made?
  var indexNote = r.score === null || r.score === undefined
    ? 'No risk index is shown because the evidence is incomplete.'
    : 'The risk index shows where this email sits within its risk level. It is not a probability.';
  var aLines = [escapeHtml_(r.decision_explanation), '<font color="' + GREY + '">' + escapeHtml_(indexNote) + '</font>'];
  if (r.verdict === 'LOW') {
    aLines.push('<font color="' + GREY + '">Low risk is not a guarantee that an email is safe. If a request seems unusual, ' +
      'confirm it through a channel you already trust.</font>');
  }
  card.addSection(block_('How was this decision made?', [CardService.newTextParagraph().setText(ltrLines_(aLines))]));

  // B. Evidence found
  var evidence = [];
  r.findings.forEach(function (f, i) {
    if (i > 0) evidence.push(CardService.newDivider());
    evidence.push(row_(reasonIcon_(f.title), f.title, f.summary, basisTag_(f.basis)));
    (f.details || []).forEach(function (d) { evidence.push(detailRow_(d.label, d.value)); });
    r.also_observed.filter(function (a) { return a.entity === f.entity && a.group === f.group; }).forEach(function (a) {
      evidence.push(detailRow_('Also noticed', a.title));
    });
  });
  if (r.request && r.request.level >= 2) {
    if (evidence.length) evidence.push(CardService.newDivider());
    var req = (r.reasons || []).filter(function (x) { return x.basis === 'Based on the wording'; })[0];
    evidence.push(row_(reasonIcon_(req ? req.title : r.request.label), req ? req.title : r.request.label,
      req ? req.summary : '', 'Based on the wording'));
    if (r.request.excerpt) {
      evidence.push(detailRow_('Quoted from the ' + (r.request.source === 'Subject' ? 'subject line' : 'message body'),
        '“' + r.request.excerpt + '”'));
    }
  }
  if (!evidence.length) {
    evidence.push(CardService.newTextParagraph().setText(ltr_("Nothing contradicted what the email claims.")));
  }
  card.addSection(block_('Evidence found', evidence));

  // C. Only limitations that affect THIS email (general product limitations are in the README / dashboard).
  if ((r.limitations || []).length) {
    card.addSection(block_('What may affect this result', [CardService.newTextParagraph().setText(ltrLines_(
      r.limitations.map(function (x) { return '• ' + escapeHtml_(x); })))]));
  }

  // D. Analysis coverage (summary visible; lists collapsed)
  var by = { ran: [], unavailable: [], not_applicable: [] };
  r.checks.forEach(function (c) { (by[c.state] || []).push(c); });
  var label = function (c) { return escapeHtml_(c.label || c.name) + (c.note ? ' (' + escapeHtml_(c.note) + ')' : ''); };
  var coverage = collapsibleBlock_('Analysis coverage', [
    by.ran.length + ' checks completed · ' + by.not_applicable.length + ' not applicable · ' +
      by.unavailable.length + ' unavailable',
    '<font color="' + GREY + '">Completed checks show what was examined, not how certain the verdict is.</font>'
  ], [
    ['<b>Completed</b>'].concat(by.ran.map(label)),
    ['<b>Not applicable</b>'].concat(by.not_applicable.length ? by.not_applicable.map(label) : ['None']),
    ['<b>Unavailable</b>'].concat(by.unavailable.length ? by.unavailable.map(label) : ['None']),
    ['<b>False-alarm safeguards</b>'].concat(r.safeguards.length ? r.safeguards.map(escapeHtml_) : ['None needed'])
  ]);
  card.addSection(coverage);

  return card.build();
}

/** Small grey key above an isolated value (addresses and domains get their own isolate). */
function detailRow_(label, value) {
  return CardService.newDecoratedText().setTopLabel(ltr_(plain_(label)))
    .setText('<font color="' + GREY + '">' + ltr_(escapeTokens_(value)) + '</font>').setWrapText(true);
}

function basisTag_(b) {
  return b === 'MAILBOX' ? 'From your email history' : b === 'HEURISTIC' ? 'Based on the wording' : 'Seen in this email';
}

/** Bold heading + summary lines always visible; each extra paragraph is hidden until expanded. */
function collapsibleBlock_(heading, summaryLines, hiddenParagraphs) {
  var s = CardService.newCardSection().setCollapsible(true).setNumUncollapsibleWidgets(2)
    .addWidget(CardService.newTextParagraph().setText(ltr_('<b>' + escapeHtml_(heading) + '</b>')))
    .addWidget(CardService.newTextParagraph().setText(ltrLines_(summaryLines)));
  hiddenParagraphs.forEach(function (lines) {
    s.addWidget(CardService.newTextParagraph().setText(ltrLines_(lines) || ltr_('-')));
  });
  return s;
}

// ------------------------------------------------------------------ error card
function buildErrorCard_(err, messageId, step, granted) {
  // Never green, never a verdict: say plainly that no verdict was produced.
  var message = String(err && err.message || err);
  var s = block_('Analysis unavailable', [
    withIcon_(CardService.newDecoratedText().setText(ltrLines_(['<b>No verdict</b>', "MailLens couldn't analyze this email."]))
      .setWrapText(true), 'error', 'No verdict'),
    CardService.newTextParagraph().setText(ltr_(escapeHtml_(friendlyReason_(message))) + staleGrantHint_(message)),
    CardService.newButtonSet().addButton(reanalyzeButton_(messageId, CardService.TextButtonStyle.FILLED_TONAL, 'Try again')),
    CardService.newTextParagraph().setText('<font color="' + GREY + '">' + ltrLines_(isDevBuild_()
      ? ['Step: ' + escapeHtml_(step || 'unknown'), escapeHtml_(message.slice(0, 300)), scopeLine_(granted)]
      : ['If this keeps happening, close and reopen the email.']) + '</font>')
  ]);
  return CardService.newCardBuilder().addSection(s).build();
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
  return '<br>' + ltr_('<b>Fix:</b> remove MailLens at myaccount.google.com/connections, then reopen this email.');
}

function scopeLine_(granted) {
  if (!granted) return 'granted scopes unknown';
  return 'granted: ' + escapeHtml_(granted.join(', ') || '(none)');
}

// ------------------------------------------------------------------ shared helpers
/**
 * Material icons are decoration; `fallbackLabel` guarantees the widget still has a label
 * (a DecoratedText needs a label or an icon) if the runtime rejects the icon.
 */
function withIcon_(decoratedText, name, fallbackLabel) {
  try {
    decoratedText.setStartIcon(CardService.newIconImage().setMaterialIcon(CardService.newMaterialIcon().setName(name)));
  } catch (e) {
    decoratedText.setTopLabel(ltr_(plain_(fallbackLabel || 'MailLens')));
  }
  return decoratedText;
}

function isDevBuild_() {
  return typeof DEV_DEFAULTS !== 'undefined' && DEV_DEFAULTS && DEV_DEFAULTS.dev === true;
}

function probeButton_(messageId) {
  return CardService.newTextButton().setText(ltr_('Run feasibility probe (dev)'))
    .setOnClickAction(CardService.newAction().setFunctionName('onRunProbe')
      .setParameters({ messageId: String(messageId) }));
}

function escapeHtml_(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
