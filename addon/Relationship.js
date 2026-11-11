/**
 * Relationship facts from the user's own Sent-mail HEADERS. Needs the optional gmail.readonly
 * grant (see Body.js for why not gmail.metadata), but only requests format=metadata, To/Cc.
 *
 * "Known contact" = someone the user sent mail to in the last WINDOW_DAYS.
 * Only derived facts leave this file (see relationshipFacts_); contact names never do.
 */

var REL = { WINDOW_DAYS: 180, MAX_MESSAGES: 100, CACHE_SECONDS: 3600, BUDGET_MS: 5000, CACHE_KEY: 'rel_v1' };

/** Returns the facts object for the backend, or null if relationship checks can't run. */
function relationshipFacts_(fromHeader, granted, timer) {
  if (!hasMailboxAccess_(granted)) return null;
  var profile;
  try {
    profile = loadProfile_(timer);
  } catch (err) {
    console.warn('relationship profile unavailable: ' + (err && err.message));
    return null; // unknown never escalates: the backend marks S4/S5/S6 unavailable
  }
  if (!profile) return null;

  var from = parseAddressList_(fromHeader)[0] || { name: '', address: '' };
  var nameKey = normalizeName_(from.name);
  var domainCounts = {};
  Object.keys(profile.addrs).forEach(function (a) {
    var d = a.split('@')[1];
    if (d) domainCounts[d] = (domainCounts[d] || 0) + profile.addrs[a];
  });
  var domains = Object.keys(domainCounts).sort(function (a, b) { return domainCounts[b] - domainCounts[a]; });
  return {
    window_days: REL.WINDOW_DAYS,
    known_domains: domains.slice(0, 100),
    sender_sent_count: profile.addrs[from.address] || 0,
    name_match_addresses: nameKey.split(' ').length >= 2 ? (profile.byName[nameKey] || []).slice(0, 10) : []
  };
}

/** Built at most once per hour per user (cached), never a mailbox search per email. */
function loadProfile_(timer) {
  var cache = CacheService.getUserCache();
  var cached = cache.get(REL.CACHE_KEY);
  if (cached) {
    if (timer) timer.note('rel_cache=hit');
    return JSON.parse(cached);
  }
  if (timer) timer.note('rel_cache=miss');

  var started = Date.now();
  var list = Gmail.Users.Messages.list('me', { labelIds: ['SENT'], maxResults: REL.MAX_MESSAGES });
  var ids = (list.messages || []).map(function (m) { return m.id; });
  var token = ScriptApp.getOAuthToken();
  var requests = ids.map(function (id) {
    return {
      url: 'https://gmail.googleapis.com/gmail/v1/users/me/messages/' + encodeURIComponent(id) +
        '?format=metadata&metadataHeaders=To&metadataHeaders=Cc&fields=internalDate,payload/headers',
      headers: { Authorization: 'Bearer ' + token },
      muteHttpExceptions: true
    };
  });
  var responses = requests.length ? UrlFetchApp.fetchAll(requests) : [];
  if (Date.now() - started > REL.BUDGET_MS) throw new Error('relationship lookup exceeded time budget');

  var cutoff = Date.now() - REL.WINDOW_DAYS * 86400000;
  var profile = { addrs: {}, byName: {} };
  responses.forEach(function (resp) {
    if (resp.getResponseCode() !== 200) return;
    var msg = JSON.parse(resp.getContentText());
    if (Number(msg.internalDate) < cutoff) return;
    (msg.payload && msg.payload.headers || []).forEach(function (h) {
      parseAddressList_(h.value).forEach(function (p) {
        if (!p.address) return;
        profile.addrs[p.address] = (profile.addrs[p.address] || 0) + 1;
        var key = normalizeName_(p.name);
        if (key.split(' ').length >= 2) {
          var arr = profile.byName[key] || (profile.byName[key] = []);
          if (arr.indexOf(p.address) === -1) arr.push(p.address);
        }
      });
    });
  });
  try { cache.put(REL.CACHE_KEY, JSON.stringify(profile), REL.CACHE_SECONDS); } catch (e) { /* too large: skip cache */ }
  return profile;
}

/** Splits an address-list header on commas outside quotes/angle brackets. */
function parseAddressList_(header) {
  var s = String(header || '').slice(0, 8000);
  var parts = [], cur = '', quoted = false, angle = 0;
  for (var i = 0; i < s.length; i++) {
    var c = s[i];
    if (c === '"') quoted = !quoted;
    else if (c === '<' && !quoted) angle++;
    else if (c === '>' && !quoted) angle = Math.max(0, angle - 1);
    if (c === ',' && !quoted && angle === 0) { parts.push(cur); cur = ''; } else cur += c;
  }
  parts.push(cur);
  return parts.map(function (p) {
    var m = p.match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$/);
    var name = m ? m[1] : '';
    var address = (m ? m[2] : p).trim().toLowerCase();
    return { name: name.trim(), address: /@/.test(address) ? address : '' };
  }).filter(function (p) { return p.address; });
}

function normalizeName_(name) {
  return String(name || '').normalize('NFKC').toLowerCase().replace(/["']/g, '').replace(/\s+/g, ' ').trim();
}
