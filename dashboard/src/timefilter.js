// Time ranges in the dashboard refer ONLY to when an email was received in Gmail (received_at, UTC epoch
// seconds). Analysis/scan times are never used here. Emails with an unknown received time are excluded.
export const RANGES = {
  '1H': { seconds: 3600, buckets: 12, label: 'last hour' },
  '24H': { seconds: 86400, buckets: 24, label: 'last 24 hours' },
  '7D': { seconds: 7 * 86400, buckets: 7, label: 'last 7 days' },
  '30D': { seconds: 30 * 86400, buckets: 30, label: 'last 30 days' },
};

/** Received within [now - range, now]. A small clock skew into the future still counts as "now". */
export function receivedInRange(email, range, now) {
  const t = email.received_at;
  return typeof t === 'number' && t >= now - RANGES[range].seconds;
}

export function filterByReceived(emails, range, now) {
  return emails.filter((e) => receivedInRange(e, range, now));
}

/** Equal-width buckets over the same window, by received time; counts match filterByReceived exactly. */
export function bucketByReceived(emails, range, now) {
  const r = RANGES[range];
  const size = r.seconds / r.buckets;
  const start = now - r.seconds;
  const b = Array.from({ length: r.buckets }, (_, i) => ({ start: start + i * size, size, HIGH: 0, SUSPICIOUS: 0, INCONCLUSIVE: 0, LOW: 0, total: 0 }));
  for (const e of filterByReceived(emails, range, now)) {
    const i = Math.min(r.buckets - 1, Math.floor((e.received_at - start) / size));
    b[i][e.verdict] += 1;
    b[i].total += 1;
  }
  return b;
}
