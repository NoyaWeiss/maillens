/**
 * Inbox scan (Security Console "Scan inbox").
 *
 * Runs as an Apps Script web app on this same project, as the signed-in user, deployed only as the
 * owner-only test (/dev) URL. It uses the already-granted gmail.readonly scope through the advanced
 * Gmail service: no new OAuth scopes, and the backend never receives Gmail credentials.
 *
 * Binding: the dashboard gets a short-lived scan ticket for its session's account. Every backend call
 * from here sends that ticket plus this user's private account key (Dashboard.js); the backend
 * accepts them only if the key hashes to the ticket's account. So a scan opened under a different
 * Google account is refused instead of mixing mailboxes.
 *
 * Each message is analyzed with the same pipeline as an opened email (buildPayload_ -> callAnalyze_).
 * Limits: newest 50 inbox messages in the range, already-analyzed ones skipped, 5 per server call.
 */

var SCAN_TICKET_RE = /^[A-Za-z0-9_-]{20,64}$/;
var SCAN_ID_RE = /^[A-Za-z0-9]{6,64}$/;

function doGet(e) {
  var t = String((e && e.parameter && e.parameter.t) || '');
  var html = HtmlService.createHtmlOutput(scanPageHtml_(SCAN_TICKET_RE.test(t) ? t : ''))
    .setTitle('MailLens · Scan inbox');
  return html.setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DENY);
}

function scanStart(ticket) {
  var ctx = scanContext_(ticket);
  if (!hasMailboxAccess_(ctx.granted)) {
    scanReport_(ctx, { state: 'error', total: 0, done: 0, skipped: 0, failed: 0, error: 'Mailbox access is off' });
    throw new Error('Scanning needs MailLens mailbox access. In Gmail, open an email in MailLens and enable mailbox access, then try again.');
  }
  var start = scanPost_(ctx, '/v1/scan/start', {});
  var after = Math.floor(Date.now() / 1000 - Number(start.range_seconds));
  var list = Gmail.Users.Messages.list('me', { q: 'in:inbox after:' + after, maxResults: Number(start.limit) || 50 });
  var ids = (list.messages || []).map(function (m) { return String(m.id); }).filter(function (id) { return SCAN_ID_RE.test(id); });
  var known = ids.length ? scanPost_(ctx, '/v1/scan/known', { ids: ids }).known : [];
  var pending = ids.filter(function (id) { return known.indexOf(id) === -1; });
  var totals = { state: 'running', total: ids.length, done: 0, skipped: ids.length - pending.length, failed: 0 };
  scanReport_(ctx, totals);
  return { pending: pending, totals: totals };
}

function scanBatch(ticket, ids, totals) {
  var ctx = scanContext_(ticket);
  (ids || []).slice(0, 5).forEach(function (id) {
    if (!SCAN_ID_RE.test(String(id))) { totals.failed++; return; }
    try {
      var m = Gmail.Users.Messages.get('me', String(id), { format: 'full' });
      var payload = buildPayload_(apiMessageAdapter_(m), ctx.granted, newTimer_());
      callAnalyze_(ctx.settings, payload, '', String(id), Number(m.internalDate) || null);
      totals.done++;
    } catch (err) {
      console.warn('scan: message failed: ' + String(err && err.message || err).slice(0, 120));
      totals.failed++;
    }
  });
  scanReport_(ctx, totals);
  return totals;
}

function scanFinish(ticket, totals, error) {
  var ctx = scanContext_(ticket);
  totals.state = error ? 'error' : 'done';
  totals.error = error ? String(error).slice(0, 200) : '';
  scanReport_(ctx, totals);
  return totals;
}

function scanContext_(ticket) {
  if (!SCAN_TICKET_RE.test(String(ticket || ''))) throw new Error('This scan link is invalid. Start the scan again from the dashboard.');
  var settings = getSettings_();
  if (!settings.url || !settings.apiKey) throw new Error('MailLens is not set up for this account.');
  return { ticket: String(ticket), settings: settings, granted: getGrantedScopes_() };
}

function scanReport_(ctx, totals) {
  try {
    scanPost_(ctx, '/v1/scan/progress', { state: totals.state, total: totals.total, done: totals.done,
      skipped: totals.skipped, failed: totals.failed, error: totals.error || '' });
  } catch (e) { /* progress is best effort; the dashboard times out on its own */ }
}

function scanPost_(ctx, path, body) {
  body.ticket = ctx.ticket;
  body.account = accountKey_();
  var resp = UrlFetchApp.fetch(ctx.settings.url + path, {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true, followRedirects: false,
    headers: { 'X-API-Key': ctx.settings.apiKey }, payload: JSON.stringify(body)
  });
  var code = resp.getResponseCode();
  if (code === 403) {
    throw new Error('This scan was started from a dashboard for a different Google account. Switch to the same account and try again.');
  }
  if (code !== 200) throw new Error('The MailLens backend is unavailable (HTTP ' + code + ').');
  return JSON.parse(resp.getContentText());
}

/** Presents a Gmail API message (format=full) with the GmailMessage methods buildPayload_ uses. */
function apiMessageAdapter_(m) {
  var html = '', text = '', attachments = [];
  (function walk(part) {
    if (!part) return;
    var mime = String(part.mimeType || '').toLowerCase();
    var body = part.body || {};
    if (part.filename) {
      attachments.push({ name: part.filename, content_type: mime, size: Number(body.size) || 0 });
    } else if (body.data && mime === 'text/html' && !html) {
      html = decodePart_(body.data);
    } else if (body.data && mime === 'text/plain' && !text) {
      text = decodePart_(body.data);
    }
    (part.parts || []).forEach(walk);
  })(m.payload);
  return {
    getId: function () { return String(m.id); },
    getThread: function () { return { getId: function () { return String(m.threadId); } }; },
    getBody: function () { return html || text; },
    getPlainBody: function () { return text; },
    getAttachments: function () {
      return attachments.map(function (a) {
        return { getName: function () { return a.name; }, getContentType: function () { return a.content_type; },
          getSize: function () { return a.size; } };
      });
    },
    getRawContent: function () { throw new Error('raw content is not used when mailbox access is granted'); }
  };
}

function decodePart_(data) {
  return Utilities.newBlob(Utilities.base64DecodeWebSafe(String(data))).getDataAsString('UTF-8');
}

function scanPageHtml_(ticket) {
  return '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<style>body{margin:0;background:#070d1a;color:#e7edf7;font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;' +
    'display:grid;place-items:center;min-height:100vh}main{width:min(460px,90vw);background:#0e1729;border:1px solid #1e2b45;' +
    'border-radius:14px;padding:28px}h1{font-size:20px;margin:0 0 6px}p{color:#b4c0d4;margin:0 0 16px}' +
    '.bar{height:8px;background:#17243f;border-radius:99px;overflow:hidden}.fill{height:100%;width:0;background:#2cc6b3;transition:width .3s}' +
    '.err{color:#ffb3b5}</style></head><body><main><h1>Scanning your inbox</h1><p id="msg">Starting…</p>' +
    '<div class="bar"><div class="fill" id="fill"></div></div></main><script>' +
    'var T=' + JSON.stringify(ticket) + ';var msg=document.getElementById("msg"),fill=document.getElementById("fill");' +
    'function fail(e){msg.className="err";msg.textContent=(e&&e.message)||String(e);if(T)google.script.run.scanFinish(T,{total:0,done:0,skipped:0,failed:0},msg.textContent);}' +
    'function show(t){var n=t.done+t.failed+t.skipped;fill.style.width=(t.total?Math.round(100*n/t.total):100)+"%";' +
    'msg.textContent="Analyzed "+t.done+" of "+(t.total-t.skipped)+" new emails"+(t.skipped?" · "+t.skipped+" already analyzed":"")+(t.failed?" · "+t.failed+" failed":"");}' +
    'function next(p,t){if(!p.length){google.script.run.withSuccessHandler(function(t){show(t);msg.textContent+=". Done: you can close this tab and return to the dashboard.";}).withFailureHandler(fail).scanFinish(T,t,"");return;}' +
    'google.script.run.withSuccessHandler(function(t2){show(t2);next(p.slice(5),t2);}).withFailureHandler(fail).scanBatch(T,p.slice(0,5),t);}' +
    'if(!T){fail("This scan link is invalid. Start the scan again from the dashboard.");}else{' +
    'google.script.run.withSuccessHandler(function(r){show(r.totals);next(r.pending,r.totals);}).withFailureHandler(fail).scanStart(T);}' +
    '</script></body></html>';
}
