/**
 * Entry points. The add-on extracts a minimal, size-capped payload from the open
 * message, sends it to the backend, and renders the verdict. All analysis lives
 * in the backend so it can be unit-tested; the add-on only extracts and renders.
 */

function onGmailMessage(e) {
  var settings = getSettings_();
  if (!settings.url || !settings.apiKey) {
    return buildSettingsCard_('Configure the backend to start analyzing email.');
  }
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
    var result = timer.time('backend', function () { return callAnalyze_(settings, payload, timer.summary()); });
    step = 'render';
    var card = timer.time('render', function () { return buildResultCard_(result, messageId, granted); });
    console.log('MailLens timing ' + timer.summary());  // visible in the editor's Executions page
    return card;
  } catch (err) {
    console.warn('MailLens failed at ' + step + ' after ' + timer.summary());
    return buildErrorCard_(err, messageId, step, granted);
  }
}

function onHomepage() {
  var s = getSettings_();
  var status = s.url && s.apiKey ? 'Backend configured. Open an email to analyze it.'
    : 'Backend not configured yet.';
  return buildSettingsCard_(status);
}

function onSettingsAction() {
  return CardService.newUniversalActionResponseBuilder()
    .displayAddOnCards([buildSettingsCard_()])
    .build();
}

function openMessage_(e) {
  GmailApp.setCurrentMessageAccessToken(e.gmail.accessToken);
  return GmailApp.getMessageById(e.gmail.messageId);
}
