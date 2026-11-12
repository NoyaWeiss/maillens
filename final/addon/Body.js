/**
 * Reading the OPEN message's body and attachment metadata, via GmailApp with the add-on's
 * current-message token. Works with no mailbox scope and with gmail.readonly.
 *
 * Why the mailbox scope is gmail.readonly and not gmail.metadata (probe evidence, 2026-11-11):
 * Apps Script uses ONE OAuth token carrying every granted scope. When it includes
 * gmail.metadata, Gmail caps every request at headers only: GmailApp getBody() fails
 * ("format FULL" refused, G1b), and so does the REST API even with the current-message
 * token in X-Goog-Gmail-Access-Token (HTTP 403, G1c). The body cannot be read at all.
 *
 * Attachment bytes are never downloaded: only name, MIME type and declared size.
 */

function readOpenMessageContent_(message) {
  return {
    html: message.getBody(),
    text: message.getPlainBody(),
    attachments: message.getAttachments({ includeInlineImages: false }).map(function (a) {
      return { name: a.getName(), content_type: a.getContentType(), size: a.getSize() };
    })
  };
}

/**
 * The current-message token arrives only in the contextual trigger event, not in button
 * callbacks. Keep it server-side (per-user cache, 5 min, keyed by message id) so dev
 * actions can reuse it; it is never placed in a card, which would send it to the browser.
 */
function rememberMessageToken_(messageId, accessToken) {
  if (!messageId || !accessToken) return;
  try { CacheService.getUserCache().put('mat_' + messageId, accessToken, 300); } catch (e) { /* best effort */ }
}

function recallMessageToken_(e, messageId) {
  if (e && e.gmail && e.gmail.accessToken) return e.gmail.accessToken;
  try { return CacheService.getUserCache().get('mat_' + messageId); } catch (err) { return null; }
}
