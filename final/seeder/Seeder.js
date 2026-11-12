/**
 * MailLens demo-mailbox seeder. A separate project from the add-on so that the
 * add-on never holds write access. Its only Gmail permission is gmail.insert:
 * it can add messages, but cannot read, modify or delete anything.
 *
 * Run seedDemoMailbox() once from the editor. Uses messages.insert (not import)
 * so Gmail's spam classifier does not reroute the phishing samples.
 */

function seedDemoMailbox() {
  var owner = Session.getEffectiveUser().getEmail();
  var threadIds = {};
  var results = [];
  SEED_MESSAGES.forEach(function (m) {
    var raw = m.raw.split('{{OWNER}}').join(owner);
    var resource = { labelIds: m.labels };
    if (m.thread && threadIds[m.thread]) resource.threadId = threadIds[m.thread];
    var blob = Utilities.newBlob(raw, 'message/rfc822');
    var inserted = Gmail.Users.Messages.insert(resource, 'me', blob, { internalDateSource: 'dateHeader' });
    if (m.thread && !threadIds[m.thread]) threadIds[m.thread] = inserted.threadId;
    results.push(m.key + ' -> thread ' + inserted.threadId + ' [' + m.labels.join(',') + ']');
  });
  Logger.log('Seeded ' + results.length + ' messages:\n' + results.join('\n'));
}
