/**
 * Security Console (Phase 4) entry points.
 *
 * Account scoping without new OAuth scopes: each Google account gets its own random account key in
 * Apps Script user properties (private to that user). It is sent with every analysis and with the
 * dashboard launch request, never in a URL. On click, the backend mints a one-time, 2-minute launch
 * code; only that code goes into the dashboard URL fragment. The selected email is resolved
 * server-side from this account's own history, so a URL can't select another account's email.
 */

var ACCOUNT_KEY_PROP = 'maillens_account_key';

function accountKey_() {
  var props = PropertiesService.getUserProperties();
  var k = props.getProperty(ACCOUNT_KEY_PROP);
  if (!k) {
    k = (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');  // 244 random bits
    props.setProperty(ACCOUNT_KEY_PROP, k);
  }
  return k;
}

/** Masked account label for the dashboard header (only with mailbox access; never the full address). */
function accountLabel_() {
  try {
    if (!hasMailboxAccess_(getGrantedScopes_())) return '';
    var a = String(Gmail.Users.getProfile('me').emailAddress || '');
    var at = a.indexOf('@');
    return at > 0 ? a.slice(0, Math.min(2, at)) + '•••' + a.slice(at) : '';
  } catch (e) { return ''; }
}

/** Button action (Welcome screen and main card). Opens the dashboard in a new browser tab. */
function onOpenDashboard(e) {
  var settings = getSettings_();
  var messageId = e && e.parameters && e.parameters.messageId;
  try {
    var resp = UrlFetchApp.fetch(settings.url + '/v1/dashboard/launch', {
      method: 'post', contentType: 'application/json', muteHttpExceptions: true, followRedirects: false,
      headers: { 'X-API-Key': settings.apiKey },
      payload: JSON.stringify({ account: accountKey_(), message: messageId || null, label: accountLabel_(),
        scan_url: (typeof DEV_DEFAULTS !== 'undefined' && DEV_DEFAULTS.scanUrl) || null })
    });
    if (resp.getResponseCode() !== 200) return notify_('The dashboard is unavailable (HTTP ' + resp.getResponseCode() + ').');
    var path = String(JSON.parse(resp.getContentText()).path || '');
    if (!/^\/dashboard\/#launch=[A-Za-z0-9_-]+$/.test(path)) return notify_('The dashboard returned an unexpected link.');
    return CardService.newActionResponseBuilder().setOpenLink(CardService.newOpenLink()
      .setUrl(settings.url + path).setOpenAs(CardService.OpenAs.FULL_SIZE).setOnClose(CardService.OnClose.NOTHING)).build();
  } catch (err) {
    return notify_('The MailLens backend is unreachable, so the dashboard can\'t open.');
  }
}

function dashboardButton_(text, style, messageId) {
  var action = CardService.newAction().setFunctionName('onOpenDashboard');
  if (messageId) action.setParameters({ messageId: String(messageId) });
  return CardService.newTextButton().setText(ltr_(text)).setTextButtonStyle(style).setOnClickAction(action);
}
