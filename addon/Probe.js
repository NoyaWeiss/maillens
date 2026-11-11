/**
 * Hour-0 feasibility probe (developer-only). Verifies spec gates against the real
 * mailbox and shows results in a card. Reports counts and timings, not content.
 */

function onRunProbe(e) {
  var rows = [];
  var t0 = Date.now();
  function add(gate, ok, detail) { rows.push({ gate: gate, ok: ok, detail: detail }); }
  function timed(fn) { var s = Date.now(); var v = fn(); return { v: v, ms: Date.now() - s }; }

  var granted = getGrantedScopes_();
  add('Granted scopes', granted ? granted.indexOf('gmail.addons.current.message.readonly') !== -1 : null,
    granted ? (granted.join(', ') || '(none)') : 'runtime could not report scopes');

  var message = null;
  var token = recallMessageToken_(e, e.parameters.messageId);
  add('Message token available', !!token, token ? 'current-message token recovered' : 'reopen the email, then rerun the probe');
  try {
    if (token) GmailApp.setCurrentMessageAccessToken(token);
    message = GmailApp.getMessageById(e.parameters.messageId);
  } catch (err) { add('open message', false, err.message); }

  if (message) {
    var path = hasMailboxAccess_(granted) ? 'API format=metadata' : 'raw via current-message token';

    // G1: authentication headers, read exactly the way the analysis reads them.
    try {
      var hr = timed(function () { return readMessageHeaders_(message, granted); });
      var auth = allHeaders_(hr.v, 'authentication-results');
      var top = auth.length ? auth[0].split(';')[0].trim() : '(none)';
      add('G1 Authentication-Results', auth.length > 0,
        auth.length + ' header(s); topmost authserv-id = ' + top + '; ' + hr.v.length + ' headers via ' + path +
        ' in ' + hr.ms + ' ms');
    } catch (err) { add('G1 Authentication-Results', false, path + ': ' + err.message); }

    // G3: earlier thread messages' headers, via the analysis' own digest function.
    try {
      var dg = timed(function () { return readThreadDigest_(message, granted); });
      var e = dg.v.entries;
      add('G3 thread headers', dg.v.error ? false : (e.length ? true : null),
        dg.v.count + ' msg(s) in thread; earlier digested ' + e.length + ', with auth ' +
        e.filter(function (x) { return x.auth_result; }).length + ', with Reply-To ' +
        e.filter(function (x) { return x.reply_to; }).length + ' via ' + path + ' in ' + dg.ms + ' ms' +
        (dg.v.error ? '; error: ' + dg.v.error : '') + (e.length || dg.v.error ? '' : ' (open a multi-message thread)'));
    } catch (err) { add('G3 thread headers', false, err.message); }

    // G1b: body of the open message via GmailApp + current-message token.
    var bodyChecks = [
      ['getBody', function () { return message.getBody().length + ' chars'; }],
      ['getPlainBody', function () { return message.getPlainBody().length + ' chars'; }],
      ['getAttachments', function () { return message.getAttachments({ includeInlineImages: false }).length + ' file(s)'; }]
    ];
    var parts = [], allOk = true;
    bodyChecks.forEach(function (c) {
      try { parts.push(c[0] + ' OK (' + c[1]() + ')'); } catch (err) { allOk = false; parts.push(c[0] + ' FAIL: ' + err.message); }
    });
    add('G1b open-message body', allOk, parts.join('; '));
  }

  // G8: the complete analysis path, exactly as onGmailMessage runs it, ending at the backend.
  if (message) {
    try {
      var settingsG8 = getSettings_();
      var run = timed(function () { return callAnalyze_(settingsG8, buildPayload_(message, granted)); });
      add('G8 full analysis path', true, 'verdict ' + run.v.verdict + ' via ' + (run.v.gate || '-') + ', ' + run.v.vector +
        ' in ' + run.ms + ' ms');
    } catch (err) { add('G8 full analysis path', false, err.message); }
  }

  // G2: mailbox-wide header reads (format=metadata; list Sent by label).
  try {
    var g = timed(function () { return Gmail.Users.Messages.list('me', { labelIds: ['SENT'], maxResults: 50 }); });
    var ids = (g.v.messages || []);
    var meta = ids.length ? timed(function () {
      return Gmail.Users.Messages.get('me', ids[0].id, { format: 'metadata', metadataHeaders: ['To', 'From'] });
    }) : { ms: 0 };
    add('G2 Gmail API metadata', true, ids.length + ' sent msg(s) listed in ' + g.ms + ' ms; metadata get ' + meta.ms + ' ms');
  } catch (err) { add('G2 Gmail API metadata', false, err.message); }

  // G7: backend reachable from Google's servers.
  var settings = getSettings_();
  try {
    var h = timed(function () {
      return UrlFetchApp.fetch(settings.url + '/healthz', { muteHttpExceptions: true, followRedirects: false });
    });
    add('G7 backend reachable', h.v.getResponseCode() === 200, 'HTTP ' + h.v.getResponseCode() + ' in ' + h.ms + ' ms');
  } catch (err) { add('G7 backend reachable', false, err.message); }

  // Report results to the backend's dev-only endpoint (counts and timings only).
  var reported = 'not reported';
  try {
    var rr = UrlFetchApp.fetch(settings.url + '/v1/dev/probe-report', {
      method: 'post', contentType: 'application/json', headers: { 'X-API-Key': settings.apiKey },
      payload: JSON.stringify(rows.map(function (r) { return { gate: r.gate, ok: r.ok, detail: String(r.detail).slice(0, 400) }; })),
      muteHttpExceptions: true, followRedirects: false
    });
    reported = 'report HTTP ' + rr.getResponseCode();
  } catch (err) { reported = 'report failed: ' + err.message; }

  var section = CardService.newCardSection().setHeader('Gate results (total ' + (Date.now() - t0) + ' ms, ' + reported + ')');
  rows.forEach(function (r) {
    var mark = r.ok === null ? '<font color="#5f6368">N/A</font>'
      : r.ok ? '<font color="#188038"><b>PASS</b></font>' : '<font color="#d93025"><b>FAIL</b></font>';
    section.addWidget(CardService.newDecoratedText().setTopLabel(escapeHtml_(r.gate))
      .setText(mark).setBottomLabel(escapeHtml_(String(r.detail).slice(0, 400))).setWrapText(true));
  });
  var g6 = CardService.newCardSection().setHeader('G6 rendering (visual check)').setCollapsible(true)
    .setNumUncollapsibleWidgets(1)
    .addWidget(CardService.newTextParagraph().setText('If this section collapses and the colors above show, G6 passes.'))
    .addWidget(CardService.newTextParagraph().setText('Hidden until expanded.'));

  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle('Feasibility probe'))
    .addSection(section).addSection(g6).build();
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card)).build();
}
