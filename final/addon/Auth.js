/**
 * Permission handling under Google's granular consent: a user can grant some
 * scopes and not others, so we check what was actually granted instead of
 * assuming the manifest list.
 *
 * - CORE scopes are needed to analyze the open message at all. If one is missing
 *   we ask Google to show its own re-consent prompt for exactly those scopes.
 * - OPTIONAL scopes (mailbox-wide read) only power relationship checks; without
 *   them analysis still runs and those checks are reported as unavailable.
 */

var SCOPE_PREFIX = 'https://www.googleapis.com/auth/';
var CORE_SCOPES = [
  'gmail.addons.execute',
  'gmail.addons.current.message.readonly',
  'script.external_request',
  'script.storage'
];
// Optional, opt-in. Used only for Sent-mail headers (format=metadata); bodies are read only
// for the open message. gmail.metadata would be narrower but makes the open message's body
// unreadable by every path (see Body.js for the probe evidence).
var OPTIONAL_SCOPES = ['gmail.readonly'];

/** Returns the short names of granted scopes, or null if the runtime can't tell us. */
function getGrantedScopes_() {
  try {
    var all = CORE_SCOPES.concat(OPTIONAL_SCOPES).map(function (s) { return SCOPE_PREFIX + s; });
    var info = ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL, all);
    return (info.getAuthorizedScopes() || []).map(function (s) { return s.replace(SCOPE_PREFIX, ''); });
  } catch (err) {
    return null;
  }
}

/**
 * Must be called OUTSIDE any try/catch: requireScopes throws a special exception
 * that the add-on framework turns into Google's authorization prompt.
 */
function ensureCoreScopes_(granted) {
  if (!granted) return;
  var missing = CORE_SCOPES.filter(function (s) { return granted.indexOf(s) === -1; });
  if (missing.length) {
    ScriptApp.requireScopes(ScriptApp.AuthMode.FULL, missing.map(function (s) { return SCOPE_PREFIX + s; }));
  }
}

function hasMailboxAccess_(granted) {
  return !!granted && granted.indexOf('gmail.readonly') !== -1;
}

/** Button handler: asks Google to prompt for the optional mailbox-wide read scope only. */
function onEnableMailboxAccess() {
  ScriptApp.requireScopes(ScriptApp.AuthMode.FULL, OPTIONAL_SCOPES.map(function (s) { return SCOPE_PREFIX + s; }));
  return notify_('Relationship checks enabled. Reopen the email to re-analyze.');
}
