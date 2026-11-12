// Time ranges refer ONLY to when an email was received in Gmail (received_at, UTC epoch seconds).
// Analysis/scan times are never used here. Emails with an unknown received time are excluded.

/** Slider stops: dense for short ranges, sparse for long ones (a log-like scale from 1 hour to 1 year). */
export const STOPS = [
  { n: 1, unit: 'hour' }, { n: 2, unit: 'hour' }, { n: 3, unit: 'hour' }, { n: 6, unit: 'hour' }, { n: 12, unit: 'hour' },
  { n: 1, unit: 'day' }, { n: 2, unit: 'day' }, { n: 3, unit: 'day' }, { n: 5, unit: 'day' },
  { n: 1, unit: 'week' }, { n: 2, unit: 'week' }, { n: 3, unit: 'week' },
  { n: 1, unit: 'month' }, { n: 2, unit: 'month' }, { n: 3, unit: 'month' }, { n: 6, unit: 'month' }, { n: 9, unit: 'month' },
  { n: 1, unit: 'year' },
];
export const DEFAULT_STOP = 9; // 1 week

export function stopLabel(s) {
  if (s.n === 1 && s.unit === 'day') return 'last 24 hours';
  return s.n === 1 ? `last ${s.unit}` : `last ${s.n} ${s.unit}s`;
}

export function shortLabel(s) {
  return `${s.n}${{ hour: 'h', day: 'd', week: 'w', month: 'mo', year: 'y' }[s.unit]}`;
}

/**
 * Start of the window, as UTC epoch seconds. Hours, days and weeks are exact rolling durations (the same in
 * every time zone). Months and years are calendar months in the viewer's local time zone (local wall-clock
 * time kept across DST), clamped to the last day of a shorter month: 1 month before 31 March is 28/29 Feb.
 */
export function cutoffFor(stop, now) {
  const fixed = { hour: 3600, day: 86400, week: 7 * 86400 }[stop.unit];
  if (fixed) return now - stop.n * fixed;
  const months = stop.unit === 'year' ? 12 * stop.n : stop.n;
  const d = new Date(now * 1000);
  const day = d.getDate();
  d.setDate(1);
  d.setMonth(d.getMonth() - months);
  const lastDay = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  d.setDate(Math.min(day, lastDay));
  return d.getTime() / 1000;
}

/** Received within [cutoff, now]; a small clock skew into the future still counts. */
export function filterByReceived(emails, cutoff) {
  return emails.filter((e) => typeof e.received_at === 'number' && e.received_at >= cutoff);
}

const BUCKET_SIZES = [300, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400, 2 * 86400, 7 * 86400, 14 * 86400, 30 * 86400];

/** Buckets covering exactly [cutoff, now] (at most 31), so the chart always matches filterByReceived. */
export function bucketByReceived(emails, cutoff, now) {
  const span = Math.max(1, now - cutoff);
  const size = BUCKET_SIZES.find((s) => span / s <= 31) || BUCKET_SIZES[BUCKET_SIZES.length - 1];
  const count = Math.max(1, Math.ceil(span / size));
  const b = Array.from({ length: count }, (_, i) => ({ start: cutoff + i * size, size, HIGH: 0, SUSPICIOUS: 0, INCONCLUSIVE: 0, LOW: 0, total: 0 }));
  for (const e of filterByReceived(emails, cutoff)) {
    const i = Math.min(count - 1, Math.max(0, Math.floor((e.received_at - cutoff) / size)));
    b[i][e.verdict] += 1;
    b[i].total += 1;
  }
  return b;
}
