/**
 * Welcome screen (homepage), Advanced settings, and the dev-only Developer tools screen.
 *
 * Configuration: the service URL and API key live in per-user properties, never in source code.
 * A gitignored, locally generated Secrets.js (DEV_DEFAULTS) can supply defaults; it is pushed only to
 * the private Apps Script project, never to git. The API key is never displayed or echoed back.
 */

var STATUS_CACHE_KEY = 'service_status_v2';
var STATUS_DETAIL_KEY = 'service_status_detail_v2';
var STATUS_CACHE_SECONDS = 60;
var WELCOME_LOGO = 'https://www.gstatic.com/images/icons/material/system/2x/security_black_48dp.png';

function getSettings_() {
  // The deployment configuration (generated Secrets.js) always wins: a URL saved earlier through
  // Advanced settings must never override it (a stale saved tunnel URL caused a real outage, and a
  // user-chosen URL is the F-09 risk). User properties are used only when no deployment config exists.
  var props = PropertiesService.getUserProperties();
  var dev = (typeof DEV_DEFAULTS !== 'undefined') ? DEV_DEFAULTS : {};
  return {
    url: dev.url || props.getProperty('BACKEND_URL') || '',
    apiKey: dev.apiKey || props.getProperty('API_KEY') || '',
    managed: !!dev.url
  };
}

/**
 * 'ready' only when the service answers an AUTHENTICATED status call (so the key is accepted too).
 * Returns one of: 'setup' (not configured), 'ready', 'key_rejected', 'unavailable'. Cached for 60 s.
 */
function serviceStatus_() {
  var s = getSettings_();
  if (!s.url || !s.apiKey) return 'setup';
  var cache = CacheService.getUserCache();
  var cached = cache.get(STATUS_CACHE_KEY);
  if (cached) return cached;
  var status, detail = '';
  try {
    var resp = UrlFetchApp.fetch(s.url + '/v1/status', {
      headers: { 'X-API-Key': s.apiKey }, muteHttpExceptions: true, followRedirects: false
    });
    var code = resp.getResponseCode();
    status = code === 200 ? 'ready' : code === 401 ? 'key_rejected' : 'unavailable';
    detail = 'HTTP ' + code;
  } catch (err) {
    detail = String(err && err.message || err).slice(0, 200);
    // Apps Script refuses URLs outside the manifest's urlFetchWhitelist (F-09): say so explicitly.
    status = /whitelist|allowlist|not allowed|permission/i.test(String(err && err.message)) ? 'blocked' : 'unavailable';
  }
  cache.put(STATUS_CACHE_KEY, status, STATUS_CACHE_SECONDS);
  cache.put(STATUS_DETAIL_KEY, hostOf_(s.url) + ': ' + detail, STATUS_CACHE_SECONDS);
  return status;
}

var STATUS_VIEW = {
  ready: { icon: 'check_circle', color: '#188038', title: 'Analysis service ready', text: '' },
  unavailable: { icon: 'cloud_off', color: '#b06000', title: 'Analysis service unavailable', text: "MailLens can't reach its analysis service right now." },
  key_rejected: { icon: 'key_off', color: '#b06000', title: 'Setup needs attention', text: 'The analysis service did not accept the saved key.' },
  blocked: { icon: 'block', color: '#c5221f', title: 'Service URL not permitted', text: 'This add-on only connects to its approved analysis service.' },
  setup: { icon: 'settings', color: '#5f6368', title: 'Setup required', text: "MailLens isn't connected to its analysis service yet." }
};

function hostOf_(url) {
  var m = String(url || '').match(/^https:\/\/([^\/:]+)/i);
  return m ? m[1] : '(no URL)';
}

/** Short diagnostic shown only when the service isn't ready: which host was tried, and the error. */
function statusDetail_() {
  try { return CacheService.getUserCache().get(STATUS_DETAIL_KEY) || ''; } catch (e) { return ''; }
}

// ------------------------------------------------------------------ Welcome (homepage)
function buildWelcomeCard_() {
  var status = serviceStatus_();
  var view = STATUS_VIEW[status];
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader()
    .setTitle(ltr_('Welcome to MailLens')).setSubtitle(ltr_('Email risk analysis'))
    .setImageUrl(WELCOME_LOGO).setImageStyle(CardService.ImageStyle.CIRCLE));

  // View full dashboard first, directly under the header (same button as on the result card).
  if (status === 'ready') card.addSection(CardService.newCardSection().addWidget(dashboardButtonSet_()));

  var intro = CardService.newCardSection()
    .addWidget(withIcon_(CardService.newDecoratedText()
      .setText(ltrLines_(['<b><font color="' + view.color + '">' + view.title + '</font></b>', escapeHtml_(view.text)]))
      .setWrapText(true), view.icon, view.title));
  if (status !== 'ready' && status !== 'setup' && statusDetail_()) {
    intro.addWidget(CardService.newTextParagraph().setText('<font color="#5f6368">' +
      ltr_('Details: ' + escapeHtml_(statusDetail_())) + '</font>'));
  }
  if (status === 'ready') {
    intro.addWidget(withIcon_(CardService.newDecoratedText()
      .setText(ltrLines_(['<b>Open an email to analyze it</b>']))
      .setWrapText(true), 'mail', 'Open an email'));
  }
  card.addSection(intro);
  var buttons = CardService.newButtonSet();
  buttons.addButton(CardService.newTextButton().setText(ltr_(status === 'ready' ? 'Advanced settings' : 'Open advanced settings'))
      .setTextButtonStyle(status === 'ready' ? CardService.TextButtonStyle.BORDERLESS : CardService.TextButtonStyle.FILLED_TONAL)
      .setOnClickAction(CardService.newAction().setFunctionName('onOpenAdvancedSettings')));
  card.addSection(CardService.newCardSection().addWidget(buttons));
  return card.build();
}

/** Email-context card when MailLens isn't configured (the Home card is only for the non-email view). */
function buildSetupRequiredCard_() {
  var view = STATUS_VIEW.setup;
  return CardService.newCardBuilder().addSection(CardService.newCardSection()
    .addWidget(withIcon_(CardService.newDecoratedText()
      .setText(ltrLines_(['<b>' + view.title + '</b>', escapeHtml_(view.text)])).setWrapText(true), view.icon, view.title))
    .addWidget(CardService.newButtonSet().addButton(CardService.newTextButton().setText(ltr_('Open advanced settings'))
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED_TONAL)
      .setOnClickAction(CardService.newAction().setFunctionName('onOpenAdvancedSettings'))))).build();
}

// ------------------------------------------------------------------ Advanced settings
function onOpenAdvancedSettings() {
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(buildAdvancedSettingsCard_())).build();
}

function buildAdvancedSettingsCard_() {
  var s = getSettings_();
  var status = serviceStatus_();
  var view = STATUS_VIEW[status];
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle(ltr_('Advanced settings')));

  card.addSection(CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText(ltr_('<b>Analysis service</b>')))
    .addWidget(CardService.newTextInput().setFieldName('url').setTitle(ltr_('Service URL')).setValue(s.url))
    .addWidget(CardService.newTextInput().setFieldName('apiKey').setTitle(ltr_('API key'))
      .setHint(ltr_(s.apiKey ? 'A key is saved. Enter a new one to replace it.' : 'Enter the key for your analysis service.')))
    .addWidget(CardService.newButtonSet().addButton(CardService.newTextButton().setText(ltr_('Save'))
      .setTextButtonStyle(CardService.TextButtonStyle.FILLED_TONAL)
      .setOnClickAction(CardService.newAction().setFunctionName('onSaveSettings'))))
    .addWidget(withIcon_(CardService.newDecoratedText()
      .setText(ltrLines_(['<b><font color="' + view.color + '">' + view.title + '</font></b>']))
      .setWrapText(true), view.icon, view.title)));

  // Relationship checks need the optional gmail.readonly consent, which Google asks for separately. When it
  // is granted there is nothing to control, so no line is shown; when it isn't, Enable is the only way to
  // grant it, so the prompt stays.
  if (!hasMailboxAccess_(getGrantedScopes_())) {
    card.addSection(CardService.newCardSection().addWidget(withIcon_(CardService.newDecoratedText()
      .setText(ltrLines_(['<b>Relationship checks are off</b>', 'Recognizes people you have emailed, using the recipients of mail you sent.']))
      .setWrapText(true)
      .setButton(CardService.newTextButton().setText(ltr_('Enable')).setTextButtonStyle(CardService.TextButtonStyle.OUTLINED)
        .setOnClickAction(CardService.newAction().setFunctionName('onEnableMailboxAccess'))), 'group', 'Relationship checks')));
  }

  if (isDevBuild_()) {
    card.addSection(CardService.newCardSection().addWidget(CardService.newTextButton().setText(ltr_('Developer tools'))
      .setTextButtonStyle(CardService.TextButtonStyle.BORDERLESS)
      .setOnClickAction(CardService.newAction().setFunctionName('onOpenDeveloperTools'))));
  }
  return card.build();
}

function onSaveSettings(e) {
  var inputs = e.formInput || {};
  var url = String(inputs.url || '').trim().replace(/\/+$/, '');
  if (!/^https:\/\/[a-z0-9.-]+(:\d+)?$/i.test(url)) {
    return notify_('The service URL must be an https:// address with no path.');
  }
  var current = getSettings_();
  if (current.managed && url !== current.url.replace(/\/+$/, '')) {
    return notify_('This deployment is locked to its approved analysis service.');
  }
  var props = PropertiesService.getUserProperties();
  props.deleteProperty('BACKEND_URL');  // never let a saved URL shadow the deployment config
  if (!current.managed) props.setProperty('BACKEND_URL', url);
  if (inputs.apiKey) props.setProperty('API_KEY', String(inputs.apiKey).trim());
  CacheService.getUserCache().removeAll([STATUS_CACHE_KEY, STATUS_DETAIL_KEY]);
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText('Saved.'))
    .setNavigation(CardService.newNavigation().updateCard(buildAdvancedSettingsCard_())).build();
}

// ------------------------------------------------------------------ Developer tools (dev builds only)
function onOpenDeveloperTools() {
  if (!isDevBuild_()) return notify_('Developer tools are not available in this build.');
  var cache = CacheService.getUserCache();
  var lastMessage = cache.get('dev_last_message') || '';
  var lastRequest = cache.get('dev_last_request') || 'none yet';
  var s = CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText(ltrLines_(['<b>Developer tools</b>', 'Last request: ' + escapeHtml_(lastRequest)])));
  if (lastMessage) s.addWidget(probeButton_(lastMessage));
  s.addWidget(CardService.newTextButton().setText(ltr_('Text direction test'))
    .setOnClickAction(CardService.newAction().setFunctionName('onBidiTest')));
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle(ltr_('Developer tools')))
    .addSection(s).addSection(renderTestSection_());
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card.build())).build();
}

function notify_(text) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(text)).build();
}

/**
 * Editor-only F-09 check (run from the Apps Script editor: select verifyAllowList, click Run).
 * Tries a URL that is NOT in the manifest's urlFetchWhitelist and logs whether Google blocked it.
 * Not reachable from the add-on UI.
 */
function verifyAllowList() {
  try {
    UrlFetchApp.fetch('https://example.com/', { muteHttpExceptions: true });
    console.log('F-09 FAIL: request to https://example.com/ was ALLOWED');
  } catch (err) {
    console.log('F-09 PASS: request to https://example.com/ was BLOCKED: ' + err.message);
  }
}
