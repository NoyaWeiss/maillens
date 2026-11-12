// node --test dashboard/tests/  — received-time filtering for the time-range slider (never analysis time).
import test from 'node:test';
import assert from 'node:assert';

process.env.TZ = 'Asia/Jerusalem'; // a zone with DST; set before any Date is used
const { STOPS, bucketByReceived, cutoffFor, filterByReceived, stopLabel } = await import('../src/timefilter.js');

const at = (iso) => Date.parse(iso) / 1000;
const NOW = at('2026-11-12T12:00:00Z');
const H = 3600, D = 86400;
const stop = (n, unit) => STOPS.find((s) => s.n === n && s.unit === unit);
const mail = (id, receivedAgo, analyzedAgo = 0, verdict = 'LOW') =>
  ({ id, verdict, received_at: receivedAgo === null ? null : NOW - receivedAgo, analyzed_at: NOW - analyzedAgo });

test('slider covers 1 hour to 1 year with readable labels', () => {
  assert.strictEqual(stopLabel(STOPS[0]), 'last hour');
  assert.strictEqual(stopLabel(STOPS[STOPS.length - 1]), 'last year');
  assert.strictEqual(stopLabel(stop(2, 'month')), 'last 2 months');
  assert.strictEqual(stopLabel(stop(1, 'day')), 'last 24 hours');
  const spans = STOPS.map((s) => NOW - cutoffFor(s, NOW));
  assert.ok(spans.every((x, i) => i === 0 || x > spans[i - 1]), 'strictly increasing');
});

test('an old email analyzed today is placed by when it was received', () => {
  const e = [mail('old-analyzed-now', 20 * D, 0)];
  const counts = [stop(1, 'hour'), stop(1, 'day'), stop(1, 'week'), stop(1, 'month')].map((s) => filterByReceived(e, cutoffFor(s, NOW)).length);
  assert.deepStrictEqual(counts, [0, 0, 0, 1]);
});

test('a recently received email analyzed long ago is recent', () => {
  assert.strictEqual(filterByReceived([mail('recent', 10 * 60, 200 * D)], cutoffFor(stop(1, 'hour'), NOW)).length, 1);
});

test('boundaries: exactly at the cutoff is included, one second earlier is not; unknown received time never counts', () => {
  for (const s of STOPS) {
    const c = cutoffFor(s, NOW);
    const e = [{ id: 'edge', received_at: c }, { id: 'before', received_at: c - 1 }, { id: 'skew', received_at: NOW + 30 }, { id: 'unknown', received_at: null }];
    assert.deepStrictEqual(filterByReceived(e, c).map((x) => x.id), ['edge', 'skew'], stopLabel(s));
  }
});

test('calendar months in local time: month ends clamp, DST keeps local wall-clock time', () => {
  const fmt = (sec) => new Date(sec * 1000).toLocaleString('sv-SE', { timeZone: 'Asia/Jerusalem' });
  assert.strictEqual(fmt(cutoffFor(stop(1, 'month'), at('2026-03-31T07:00:00Z'))), '2026-02-28 10:00:00');  // 10:00 IDT -> 10:00 IST; no "March 3"
  assert.strictEqual(fmt(cutoffFor(stop(3, 'month'), at('2026-05-31T07:00:00Z'))), '2026-02-28 10:00:00');  // 10:00 IDT -> 10:00 IST
  assert.strictEqual(fmt(cutoffFor(stop(1, 'year'), at('2028-02-29T10:00:00Z'))), '2027-02-28 12:00:00');   // leap day
  assert.strictEqual(NOW - cutoffFor(stop(1, 'week'), NOW), 7 * D);                                        // fixed units are exact
});

test('changing the range changes counts; the chart always matches the filtered list', () => {
  const e = [mail('a', 30 * 60, 0, 'HIGH'), mail('b', 5 * H, 0, 'SUSPICIOUS'), mail('c', 3 * D, 0, 'LOW'), mail('d', 12 * D, 0, 'INCONCLUSIVE'),
    mail('e', 40 * D, 0, 'HIGH'), mail('f', 200 * D, 0, 'LOW'), mail('now', 0, 0, 'HIGH')];
  const counts = {};
  for (const s of STOPS) {
    const c = cutoffFor(s, NOW);
    const list = filterByReceived(e, c);
    const b = bucketByReceived(e, c, NOW);
    assert.ok(b.length <= 31);
    assert.strictEqual(b.reduce((x, y) => x + y.total, 0), list.length, stopLabel(s));
    counts[stopLabel(s)] = list.length;
  }
  assert.deepStrictEqual([counts['last hour'], counts['last 24 hours'], counts['last week'], counts['last month'], counts['last 3 months'], counts['last year']], [2, 3, 4, 5, 6, 7]);
});
