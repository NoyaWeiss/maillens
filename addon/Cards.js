/**
 * Rendering (spec section 5). Every string that comes from the email or the backend
 * passes through escapeHtml_ before it reaches a widget. URLs arrive defanged from
 * the backend and are never rendered as links.
 */

var VERDICT_STYLE = {
  LOW: { label: 'Low risk', color: '#188038' },
  SUSPICIOUS: { label: 'Suspicious', color: '#e37400' },
  HIGH: { label: 'High risk', color: '#d93025' },
  INCONCLUSIVE: { label: 'Inconclusive', color: '#5f6368' }
};
var BASIS_LABEL = { OBSERVED: 'Observed in this email', MAILBOX: 'From your mailbox history', HEURISTIC: 'Pattern judgment' };
var CACHE_TTL = 600;

function buildResultCard_(r, messageId, granted) {
  try { CacheService.getUserCache().put('result_' + r.request_id, JSON.stringify(r), CACHE_TTL); } catch (e) { /* ignore */ }
  var style = VERDICT_STYLE[r.verdict];
  var card = CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('MailLens').setSubtitle(escapeHtml_(r.archetype)));

  // 1. Verdict
  var score = r.score === null || r.score === undefined ? '' : ' · ' + Number(r.score) + '/100';
  card.addSection(CardService.newCardSection()
    .addWidget(CardService.newDecoratedText()
      .setTopLabel('Verdict' + score)
      .setText('<font color="' + style.color + '"><b>' + style.label + '</b></font>')
      .setBottomLabel(escapeHtml_(r.headline)).setWrapText(true))
    .addWidget(CardService.newDecoratedText()
      .setTopLabel('Confidence')
      .setText(escapeHtml_(r.confidence) + ' · ' + Number(r.coverage_ran) + ' of ' +
        Number(r.coverage_applicable) + ' applicable checks ran')
      .setWrapText(true)));

  // 2. Claim vs. Reality (one row per entity, deduplicated by the backend).
  // Gmail rejects a section with no widgets at render time, AFTER our code returns
  // ("Unable to load content"), so rows are collected first and the section is added only if non-empty.
  var rows = r.findings.slice(0, 6).map(function (f) {
    return CardService.newDecoratedText()
      .setTopLabel(escapeHtml_((BASIS_LABEL[f.basis] || f.basis) + ' · ' + f.signal + levelTag_(f.level)))
      .setText('<b>Claims:</b> ' + escapeHtml_(f.claim) + '<br><b>Reality:</b> <font color="' +
        (f.level >= 2 ? '#d93025' : '#e37400') + '">' + escapeHtml_(f.reality) + '</font>')
      .setWrapText(true);
  });
  if (r.request && r.request.level >= 2) {
    var ask = CardService.newDecoratedText()
      .setTopLabel(BASIS_LABEL.HEURISTIC + ' · S13' + (r.request.level === 3 ? ' · irreversible' : ''))
      .setText('<b>Asks you to:</b> ' + escapeHtml_(r.request.label))
      .setWrapText(true);
    if (r.pressure_cues.length) ask.setBottomLabel('Pressure: ' + escapeHtml_(r.pressure_cues.join(', ')));
    rows.push(ask);
  }
  if (rows.length) {
    var cvr = CardService.newCardSection().setHeader('Claim vs. Reality');
    rows.forEach(function (w) { cvr.addWidget(w); });
    card.addSection(cvr);
  }

  // 3. Attack Story
  if (r.story.length && (r.verdict !== 'LOW' || r.story.length > 1)) {
    card.addSection(CardService.newCardSection().setHeader(r.verdict === 'LOW' ? 'Note' : 'Attack story')
      .addWidget(CardService.newTextParagraph().setText(r.story.map(escapeHtml_).join('<br><br>'))));
  }

  // 4. What to do now
  if (r.actions.length) {
    card.addSection(CardService.newCardSection().setHeader('What to do now')
      .addWidget(CardService.newTextParagraph().setText(
        r.actions.map(function (a, i) { return (i + 1) + '. ' + escapeHtml_(a); }).join('<br>'))));
  }

  if (granted && !hasMailboxAccess_(granted)) card.addSection(mailboxAccessSection_(granted));

  card.addSection(CardService.newCardSection()
    .addWidget(CardService.newTextButton().setText('Technical evidence')
      .setOnClickAction(CardService.newAction().setFunctionName('onShowTechnical')
        .setParameters({ requestId: String(r.request_id), messageId: String(messageId) }))));
  return card.build();
}

function onShowTechnical(e) {
  var raw = CacheService.getUserCache().get('result_' + e.parameters.requestId);
  if (!raw) return notify_('Evidence expired. Reopen the email to re-analyze.');
  var card = buildTechnicalCard_(JSON.parse(raw), e.parameters.messageId);
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card)).build();
}

function buildTechnicalCard_(r, messageId) {
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader()
    .setTitle('Technical evidence').setSubtitle('Request ' + escapeHtml_(r.request_id)));

  card.addSection(CardService.newCardSection().setHeader('Decision trace')
    .addWidget(CardService.newTextParagraph().setText(
      '<b>Vector:</b> ' + escapeHtml_(r.vector) +
      '<br><b>Gate:</b> ' + escapeHtml_(r.gate_explanation) +
      (r.pathway ? '<br><b>Pathway:</b> ' + escapeHtml_(r.pathway) : '') +
      '<br><font color="#5f6368">D = strongest finding · A = request level · E = entities with strong findings · ' +
      'P = pressure · N = familiarity (0 known, 1 new, ? unknown)</font>')));

  var fs = CardService.newCardSection().setHeader('Findings (' + r.findings.length + ')').setCollapsible(true)
    .setNumUncollapsibleWidgets(Math.min(3, Math.max(1, r.findings.length)));
  if (!r.findings.length) fs.addWidget(CardService.newTextParagraph().setText('None.'));
  r.findings.forEach(function (f) { fs.addWidget(findingWidget_(f)); });
  card.addSection(fs);

  if (r.also_observed.length) {
    var ao = CardService.newCardSection().setHeader('Also observed (deduplicated)').setCollapsible(true)
      .setNumUncollapsibleWidgets(1);
    r.also_observed.forEach(function (f) { ao.addWidget(findingWidget_(f)); });
    card.addSection(ao);
  }

  if (r.suppressed.length) {
    card.addSection(CardService.newCardSection().setHeader('False-positive guards applied').setCollapsible(true)
      .setNumUncollapsibleWidgets(1)
      .addWidget(CardService.newTextParagraph().setText(r.suppressed.map(escapeHtml_).join('<br>'))));
  }

  var byState = { ran: [], unavailable: [], not_applicable: [] };
  r.checks.forEach(function (c) { (byState[c.state] || []).push(c.id + ' ' + c.name); });
  card.addSection(CardService.newCardSection().setHeader('Checks').setCollapsible(true)
    .setNumUncollapsibleWidgets(1)
    .addWidget(CardService.newTextParagraph().setText(
      '<b>Ran (' + byState.ran.length + '):</b> ' + escapeHtml_(byState.ran.join(', '))))
    .addWidget(CardService.newTextParagraph().setText(
      '<b>Unavailable:</b> ' + escapeHtml_(byState.unavailable.join(', ') || 'none') +
      '<br><b>Not applicable:</b> ' + escapeHtml_(byState.not_applicable.join(', ') || 'none') +
      '<br><b>Out of scope:</b> ' + escapeHtml_(r.out_of_scope.join('; '))))
    .addWidget(CardService.newTextParagraph().setText(
      '<b>Assumptions:</b><br>' + r.assumptions.map(escapeHtml_).join('<br>'))));

  card.addSection(CardService.newCardSection().addWidget(probeButton_(messageId)));
  return card.build();
}

function findingWidget_(f) {
  return CardService.newDecoratedText()
    .setTopLabel(escapeHtml_(f.signal + ' · ' + f.group + levelTag_(f.level) + ' · ' + f.basis))
    .setText(escapeHtml_(f.reality))
    .setBottomLabel(escapeHtml_(f.entity + (f.excerpt ? ' · ' + f.excerpt : '')) || '-')
    .setWrapText(true);
}

function levelTag_(level) {
  return level === 3 ? ' · deliberate construct' : level === 2 ? ' · strong' : ' · weak';
}

function buildErrorCard_(err, messageId, step, granted) {
  // Never green, never a verdict: say plainly that no verdict was produced.
  // The message is Google's/our runtime error text, not email content; still escaped.
  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('MailLens'))
    .addSection(CardService.newCardSection()
      .addWidget(CardService.newDecoratedText().setTopLabel('No verdict was produced')
        .setText('<font color="#5f6368"><b>Analysis unavailable</b></font>')
        .setBottomLabel('Failed at: ' + escapeHtml_(step || 'unknown')).setWrapText(true))
      .addWidget(CardService.newTextParagraph().setText(
        escapeHtml_(String(err && err.message || err).slice(0, 800)) + staleGrantHint_(err) +
        '<br><br>' + scopeLine_(granted)))
      .addWidget(probeButton_(messageId)))
    .build();
}

/** An old gmail.metadata grant caps every read at headers only; tell the user how to reset it. */
function staleGrantHint_(err) {
  if (!/metadata scope/i.test(String(err && err.message || err))) return '';
  return '<br><br><b>Fix:</b> an earlier "metadata" permission is still active. Remove MailLens at ' +
    'myaccount.google.com/connections, then reopen this email and authorize again.';
}

function scopeLine_(granted) {
  if (!granted) return 'Granted scopes: unknown';
  return 'Granted scopes: ' + escapeHtml_(granted.join(', ') || '(none)');
}

function probeButton_(messageId) {
  return CardService.newTextButton().setText('Run feasibility probe (dev)')
    .setOnClickAction(CardService.newAction().setFunctionName('onRunProbe')
      .setParameters({ messageId: String(messageId) }));
}

function escapeHtml_(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
