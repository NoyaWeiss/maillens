/**
 * Builds the backend payload from the open message. Sends only what analysis needs
 * (see README "Data sent to the backend"): no To/Cc/Bcc, no attachment bytes.
 */

var LIMITS = { short: 1000, header: 8000, html: 200000, text: 100000, attachments: 50, authResults: 20 };

/** Time budget for one analysis. Gmail aborts add-on executions at 30 s; we aim far lower. */
var BUDGET = { optionalChecksMs: 6000 };

function newTimer_() {
  var start = Date.now(), marks = [];
  return {
    time: function (name, fn) {
      var t = Date.now();
      try { return fn(); } finally { marks.push(name + '=' + (Date.now() - t)); }
    },
    note: function (s) { marks.push(s); },
    elapsed: function () { return Date.now() - start; },
    summary: function () { return marks.join(',') + ',total=' + (Date.now() - start); }
  };
}

function buildPayload_(message, granted, timer) {
  timer = timer || newTimer_();
  var headers = timer.time('headers', function () {
    return withStep_('read headers', function () { return readMessageHeaders_(message, granted); });
  });
  // Optional: skipped (not failed) if the run is already slow, so it can never block the verdict.
  var digest = timer.elapsed() > BUDGET.optionalChecksMs ? (timer.note('thread=skipped'), { count: 1, entries: [] })
    : timer.time('thread', function () { return readThreadDigest_(message, granted); });
  // Body and attachment metadata of the OPEN message only.
  var content = timer.time('body', function () {
    return withStep_('read open-message body', function () { return readOpenMessageContent_(message); });
  });
  var html = content.html, text = content.text;
  var attachments = content.attachments.slice(0, LIMITS.attachments).map(function (a) {
    return { name: cap_(a.name, 255), content_type: cap_(a.content_type, 255), size: Math.max(0, Number(a.size) || 0) };
  });
  var from = firstHeader_(headers, 'from') || '';
  return {
    schema_version: 1,
    message: {
      from_header: cap_(from, LIMITS.short),
      reply_to: nullable_(firstHeader_(headers, 'reply-to'), LIMITS.short),
      return_path: nullable_(firstHeader_(headers, 'return-path'), LIMITS.short),
      subject: cap_(firstHeader_(headers, 'subject') || '', LIMITS.short),
      date: nullable_(firstHeader_(headers, 'date'), LIMITS.short),
      message_id: nullable_(firstHeader_(headers, 'message-id'), LIMITS.short),
      in_reply_to: nullable_(firstHeader_(headers, 'in-reply-to'), LIMITS.short),
      references: nullable_(firstHeader_(headers, 'references'), LIMITS.header),
      auth_results: allHeaders_(headers, 'authentication-results').slice(0, LIMITS.authResults)
        .map(function (v) { return cap_(v, LIMITS.header); }),
      list_unsubscribe: firstHeader_(headers, 'list-unsubscribe') !== null,
      precedence: nullable_(firstHeader_(headers, 'precedence'), LIMITS.short),
      html_body: cap_(html, LIMITS.html),
      text_body: cap_(text, LIMITS.text),
      attachments: attachments
    },
    thread: digest.entries,
    thread_message_count: digest.count,
    relationship: timer.elapsed() > BUDGET.optionalChecksMs ? (timer.note('relationship=skipped'), null)
      : timer.time('relationship', function () { return relationshipFacts_(from, granted, timer); })
  };
}

/** Header block only, so we never hold more of a message than needed. */
function headerBlock_(raw) {
  var end = raw.search(/\r?\n\r?\n/);
  return end === -1 ? raw.slice(0, 64000) : raw.slice(0, Math.min(end, 64000));
}

/** Returns [{name, value}] in original order (topmost first), with folded lines unfolded. */
function parseRawHeaders_(raw) {
  var end = raw.search(/\r?\n\r?\n/);
  var block = end === -1 ? raw : raw.slice(0, end);
  var lines = block.replace(/\r?\n[ \t]+/g, ' ').split(/\r?\n/);
  var out = [];
  for (var i = 0; i < lines.length; i++) {
    var idx = lines[i].indexOf(':');
    if (idx > 0) out.push({ name: lines[i].slice(0, idx).trim().toLowerCase(), value: lines[i].slice(idx + 1).trim() });
  }
  return out;
}

function firstHeader_(headers, name) {
  for (var i = 0; i < headers.length; i++) if (headers[i].name === name) return headers[i].value;
  return null;
}

function allHeaders_(headers, name) {
  return headers.filter(function (h) { return h.name === name; }).map(function (h) { return h.value; });
}

function cap_(s, n) { return String(s == null ? '' : s).slice(0, n); }
function nullable_(s, n) { return s ? cap_(s, n) : null; }

/** Re-throws with the step name so the error card can say exactly which call failed. */
function withStep_(name, fn) {
  try { return fn(); } catch (err) { throw new Error(name + ': ' + (err && err.message || err)); }
}
