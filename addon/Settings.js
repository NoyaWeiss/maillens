/**
 * Welcome screen (homepage), Advanced settings, and the dev-only Developer tools screen.
 *
 * Configuration: the service URL and API key live in per-user properties, never in source code.
 * A gitignored, locally generated Secrets.js (DEV_DEFAULTS) can supply defaults; it is pushed only to
 * the private Apps Script project, never to git. The API key is never displayed or echoed back.
 */

var STATUS_CACHE_KEY = 'service_status_v1';
var STATUS_CACHE_SECONDS = 60;
var WELCOME_LOGO = 'https://www.gstatic.com/images/icons/material/system/2x/security_black_48dp.png';

function getSettings_() {
  var props = PropertiesService.getUserProperties();
  var dev = (typeof DEV_DEFAULTS !== 'undefined') ? DEV_DEFAULTS : {};
  return {
    url: props.getProperty('BACKEND_URL') || dev.url || '',
    apiKey: props.getProperty('API_KEY') || dev.apiKey || ''
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
  var status;
  try {
    var resp = UrlFetchApp.fetch(s.url + '/v1/status', {
      headers: { 'X-API-Key': s.apiKey }, muteHttpExceptions: true, followRedirects: false
    });
    var code = resp.getResponseCode();
    status = code === 200 ? 'ready' : code === 401 ? 'key_rejected' : 'unavailable';
  } catch (err) {
    status = 'unavailable';
  }
  cache.put(STATUS_CACHE_KEY, status, STATUS_CACHE_SECONDS);
  return status;
}

var STATUS_VIEW = {
  ready: { icon: 'check_circle', color: '#188038', title: 'Analysis service ready', text: 'Connected and ready to analyze emails.' },
  unavailable: { icon: 'cloud_off', color: '#b06000', title: 'Analysis service unavailable', text: "MailLens can't reach its analysis service right now." },
  key_rejected: { icon: 'key_off', color: '#b06000', title: 'Setup needs attention', text: 'The analysis service did not accept the saved key.' },
  setup: { icon: 'settings', color: '#5f6368', title: 'Setup required', text: "MailLens isn't connected to its analysis service yet." }
};

// ------------------------------------------------------------------ Welcome (homepage)
function buildWelcomeCard_() {
  var status = serviceStatus_();
  var view = STATUS_VIEW[status];
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader()
    .setTitle(ltr_('Welcome to MailLens')).setSubtitle(ltr_('Email risk analysis'))
    .setImageUrl(WELCOME_LOGO).setImageStyle(CardService.ImageStyle.CIRCLE));

  var intro = CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText(ltr_(
      'MailLens checks whether an email is what it claims to be, and explains any risk in plain language.')))
    .addWidget(withIcon_(CardService.newDecoratedText()
      .setText(ltrLines_(['<b><font color="' + view.color + '">' + view.title + '</font></b>', escapeHtml_(view.text)]))
      .setWrapText(true), view.icon, view.title));
  if (status === 'ready') {
    intro.addWidget(withIcon_(CardService.newDecoratedText()
      .setText(ltrLines_(['<b>Open an email to analyze it</b>', 'The result appears here automatically.']))
      .setWrapText(true), 'mail', 'Open an email'));
  }
  card.addSection(intro);
  card.addSection(CardService.newCardSection().addWidget(CardService.newButtonSet().addButton(
    CardService.newTextButton().setText(ltr_(status === 'ready' ? 'Advanced settings' : 'Open advanced settings'))
      .setTextButtonStyle(status === 'ready' ? CardService.TextButtonStyle.BORDERLESS : CardService.TextButtonStyle.FILLED_TONAL)
      .setOnClickAction(CardService.newAction().setFunctionName('onOpenAdvancedSettings')))));
  return card.build();
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

  var granted = getGrantedScopes_();
  var relOn = hasMailboxAccess_(granted);
  var rel = withIcon_(CardService.newDecoratedText()
    .setText(ltrLines_(['<b>Relationship checks: ' + (relOn ? 'on' : 'off') + '</b>',
      'Recognizes people you have emailed, using the recipients of mail you sent.']))
    .setWrapText(true), 'group', 'Relationship checks');
  if (!relOn) {
    rel.setButton(CardService.newTextButton().setText(ltr_('Enable')).setTextButtonStyle(CardService.TextButtonStyle.OUTLINED)
      .setOnClickAction(CardService.newAction().setFunctionName('onEnableMailboxAccess')));
  }
  card.addSection(CardService.newCardSection().addWidget(rel));

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
  var props = PropertiesService.getUserProperties();
  props.setProperty('BACKEND_URL', url);
  if (inputs.apiKey) props.setProperty('API_KEY', String(inputs.apiKey).trim());
  CacheService.getUserCache().remove(STATUS_CACHE_KEY);
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
