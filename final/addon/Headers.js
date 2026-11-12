/**
 * Header reading for the open message and its thread, under either permission set.
 *
 * Headers are always read with the least data needed:
 *  - mailbox scope granted -> Gmail API, format=METADATA (headers only, in order; no body fetched).
 *  - not granted           -> raw headers via the current-message token (add-on scope).
 *
 * Either way we only ever hold headers here; bodies are read separately, and only for
 * the open message.
 */

var THREAD_HEADERS = ['From', 'Reply-To', 'To', 'Cc', 'Authentication-Results'];

/** [{name (lowercase), value}] in original order, topmost first. */
function readMessageHeaders_(message, granted) {
  if (hasMailboxAccess_(granted)) {
    var m = Gmail.Users.Messages.get('me', message.getId(), { format: 'metadata' });
    return apiHeaders_(m);
  }
  return parseRawHeaders_(headerBlock_(message.getRawContent()));
}

/** Digest of up to 5 earlier messages in the thread (no bodies). */
function readThreadDigest_(message, granted) {
  try {
    var currentId = message.getId();
    var entries = [], count = 1;
    if (hasMailboxAccess_(granted)) {
      var t = Gmail.Users.Threads.get('me', message.getThread().getId(),
        { format: 'metadata', metadataHeaders: THREAD_HEADERS });
      var msgs = t.messages || [];
      count = msgs.length;
      var idx = indexWhere_(msgs, function (m) { return m.id === currentId; });
      entries = (idx === -1 ? msgs : msgs.slice(0, idx)).slice(-5).map(function (m) {
        return digestEntry_(apiHeaders_(m));
      });
    } else {
      var all = message.getThread().getMessages();
      count = all.length;
      var i = indexWhere_(all, function (m) { return m.getId() === currentId; });
      entries = (i === -1 ? all : all.slice(0, i)).slice(-5).map(function (m) {
        return digestEntry_(parseRawHeaders_(headerBlock_(m.getRawContent())));
      });
    }
    return { count: Math.min(Math.max(count, 1), 1000), entries: entries };
  } catch (err) {
    console.warn('thread digest unavailable: ' + (err && err.message));
    return { count: 1, entries: [], error: String(err && err.message || err) };
  }
}

function digestEntry_(headers) {
  var auth = allHeaders_(headers, 'authentication-results');
  var participants = parseAddressList_((firstHeader_(headers, 'to') || '') + ',' + (firstHeader_(headers, 'cc') || ''))
    .map(function (p) { return p.address; });
  return {
    from_header: cap_(firstHeader_(headers, 'from') || '', LIMITS.short),
    reply_to: nullable_(firstHeader_(headers, 'reply-to'), LIMITS.short),
    auth_result: auth.length ? cap_(auth[0], LIMITS.header) : null,
    participants: participants.slice(0, 30)
  };
}

/** Gmail API message (format=metadata) -> [{name, value}] in original order. */
function apiHeaders_(apiMessage) {
  var hs = (apiMessage && apiMessage.payload && apiMessage.payload.headers) || [];
  return hs.slice(0, 500).map(function (h) {
    return { name: String(h.name || '').trim().toLowerCase(), value: String(h.value || '').replace(/\s+/g, ' ').trim() };
  });
}

function indexWhere_(arr, pred) {
  for (var i = 0; i < arr.length; i++) if (pred(arr[i])) return i;
  return -1;
}
