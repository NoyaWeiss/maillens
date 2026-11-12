/**
 * Backend client. The response is treated as untrusted too: it is shape-checked
 * here and every string is escaped at render time.
 */

var VERDICTS = ['LOW', 'SUSPICIOUS', 'HIGH', 'INCONCLUSIVE'];

function callAnalyze_(settings, payload, timing, messageId) {
  var resp;
  var account = '';
  try { account = accountKey_(); } catch (e) { /* history is best effort; analysis never depends on it */ }
  try {
    resp = UrlFetchApp.fetch(settings.url + '/v1/analyze', {
    method: 'post',
    contentType: 'application/json',
    // Account key + message id let the backend keep this account's dashboard history (addon/Dashboard.js).
    headers: { 'X-API-Key': settings.apiKey, 'X-MailLens-Timing': String(timing || '').slice(0, 300),
      'X-MailLens-Account': account, 'X-MailLens-Message': String(messageId || '') },
    payload: JSON.stringify(payload),
      muteHttpExceptions: true,
      followRedirects: false
    });
  } catch (err) {  // DNS failure, tunnel down, connection refused, or blocked by urlFetchWhitelist
    if (/whitelist|allowlist|not allowed/i.test(String(err && err.message))) {
      throw new Error('The MailLens backend address is not permitted by this add-on. No verdict was produced.');
    }
    throw new Error('The MailLens backend is unreachable. No verdict was produced. (' +
      String(err && err.message || err).slice(0, 120) + ')');
  }
  var code = resp.getResponseCode();
  if (code === 401) throw new Error('The backend rejected the API key. Check Backend settings.');
  if (code === 429) throw new Error('The backend is rate-limiting requests. Try again in a minute.');
  if (code >= 500 || code === 404) {
    throw new Error('The MailLens backend is unavailable (HTTP ' + code + '). No verdict was produced.');
  }
  if (code !== 200) throw new Error('Backend returned HTTP ' + code);
  var body = JSON.parse(resp.getContentText());
  validateResponse_(body);
  return body;
}

/** Shape check: a malformed or tampered response must never render as a verdict. */
function validateResponse_(b) {
  var ok = b && VERDICTS.indexOf(b.verdict) !== -1 && typeof b.headline === 'string' &&
    typeof b.request_id === 'string' && typeof b.vector === 'string' &&
    typeof b.category === 'string' && typeof b.impact === 'string' &&
    ['findings', 'also_observed', 'suppressed', 'story', 'actions', 'reasons', 'checks', 'out_of_scope', 'assumptions',
      'pressure_cues'].every(function (k) { return Array.isArray(b[k]); }) &&
    b.reasons.every(function (x) { return x && typeof x.title === 'string' && typeof x.summary === 'string'; }) &&
    b.actions.every(function (x) { return x && typeof x.title === 'string' && typeof x.detail === 'string'; });
  if (!ok) throw new Error('Backend response failed validation');
}
