/**
 * Entry points. The add-on extracts a minimal, size-capped payload from the open
 * message, sends it to the backend, and renders the verdict. All analysis lives
 * in the backend so it can be unit-tested; the add-on only extracts and renders.
 */

function onGmailMessage(e) {
  var settings = getSettings_();
  if (!settings.url || !settings.apiKey) return buildWelcomeCard_();  // shows "Setup required"
  var granted = getGrantedScopes_();
  ensureCoreScopes_(granted); // outside try: may raise Google's re-consent prompt

  var messageId = e.gmail.messageId;
  rememberMessageToken_(messageId, e.gmail.accessToken);
  var step = 'start';
  var timer = newTimer_();
  try {
    step = 'open message (current-message token)';
    var message = timer.time('open', function () { return openMessage_(e); });
    step = 'extract message';
    var payload = buildPayload_(message, granted, timer);
    step = 'call backend';
    var result = timer.time('backend', function () { return callAnalyze_(settings, payload, timer.summary(), messageId); });
    step = 'render';
    var card = timer.time('render', function () { return buildResultCard_(result, messageId, granted); });
    if (isDevBuild_()) rememberForDevTools_(messageId, result.request_id);
    console.log('MailLens timing ' + timer.summary());  // visible in the editor's Executions page
    return card;
  } catch (err) {
    console.warn('MailLens failed at ' + step + ' after ' + timer.summary());
    return buildErrorCard_(err, messageId, step, granted);
  }
}

/**
 * "Re-analyze" / "Try again": re-runs the analysis in place. Button events don't carry the
 * current-message token, so it's recovered from the server-side cache (Body.js).
 */
function onReanalyze(e) {
  var messageId = e.parameters.messageId;
  var token = recallMessageToken_(e, messageId);
  if (!token) return notify_('Close and reopen the email to analyze it again.');
  var card = onGmailMessage({ gmail: { messageId: messageId, accessToken: token } });
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().updateCard(card)).build();
}

function onHomepage() {
  return buildWelcomeCard_();
}

function onSettingsAction() {
  return CardService.newUniversalActionResponseBuilder()
    .displayAddOnCards([buildAdvancedSettingsCard_()])
    .build();
}

function rememberForDevTools_(messageId, requestId) {
  try {
    var c = CacheService.getUserCache();
    c.put('dev_last_message', String(messageId), 600);
    c.put('dev_last_request', String(requestId), 600);
  } catch (e) { /* best effort */ }
}

function openMessage_(e) {
  GmailApp.setCurrentMessageAccessToken(e.gmail.accessToken);
  return GmailApp.getMessageById(e.gmail.messageId);
}
