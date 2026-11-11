/**
 * Backend URL and API key live in per-user properties, never in source code.
 */

function getSettings_() {
  // User-entered values win; otherwise fall back to the gitignored, locally generated
  // Secrets.js (dev only). It is pushed to the private Apps Script project, never to git.
  var props = PropertiesService.getUserProperties();
  var dev = (typeof DEV_DEFAULTS !== 'undefined') ? DEV_DEFAULTS : {};
  return {
    url: props.getProperty('BACKEND_URL') || dev.url || '',
    apiKey: props.getProperty('API_KEY') || dev.apiKey || ''
  };
}

function buildSettingsCard_(note) {
  var s = getSettings_();
  var section = CardService.newCardSection();
  if (note) section.addWidget(CardService.newTextParagraph().setText(escapeHtml_(note)));
  section
    .addWidget(CardService.newTextInput().setFieldName('url').setTitle('Backend URL (https://...)').setValue(s.url))
    .addWidget(CardService.newTextInput().setFieldName('apiKey')
      .setTitle(s.apiKey ? 'API key (saved; leave blank to keep)' : 'API key'))
    .addWidget(CardService.newTextButton().setText('Save')
      .setOnClickAction(CardService.newAction().setFunctionName('onSaveSettings')));
  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('MailLens settings'))
    .addSection(section).build();
}

function onSaveSettings(e) {
  var inputs = e.formInput || {};
  var url = String(inputs.url || '').trim().replace(/\/+$/, '');
  if (!/^https:\/\/[a-z0-9.-]+(:\d+)?$/i.test(url)) {
    return notify_('Backend URL must be an https:// origin with no path.');
  }
  var props = PropertiesService.getUserProperties();
  props.setProperty('BACKEND_URL', url);
  if (inputs.apiKey) props.setProperty('API_KEY', String(inputs.apiKey).trim());
  return notify_('Saved. Open an email to analyze it.');
}

function notify_(text) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(text)).build();
}
