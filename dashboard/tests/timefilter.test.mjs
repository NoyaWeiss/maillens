// node --test dashboard/tests/  — received-time filtering (never analysis time).
import test from 'node:test';
import assert from 'node:assert';
import { RANGES, bucketByReceived, filterByReceived } from '../src/timefilter.js';

const NOW = Date.UTC(2026, 10, 12, 12, 0, 0) / 1000;
const H = 3600, D = 86400;
const mail = (id, receivedAgo, analyzedAgo = 0, verdict = 'LOW') =>
  ({ id, verdict, received_at: receivedAgo === null ? null : NOW - receivedAgo, analyzed_at: NOW - analyzedAgo });

test('an old email analyzed today is filtered by when it was received', () => {
  const e = [mail('old-analyzed-now', 20 * D, 0)];
  assert.deepStrictEqual(['1H', '24H', '7D', '30D'].map((r) => filterByReceived(e, r, NOW).length), [0, 0, 0, 1]);
});

test('a recently received email analyzed long ago still counts as recent', () => {
  const e = [mail('recent', 10 * 60, 25 * D)];
  assert.deepStrictEqual(['1H', '24H', '7D', '30D'].map((r) => filterByReceived(e, r, NOW).length), [1, 1, 1, 1]);
});

test('boundaries: exactly at the cutoff is included, one second earlier is not; future skew counts as now', () => {
  for (const r of Object.keys(RANGES)) {
    const s = RANGES[r].seconds;
    const ids = filterByReceived([mail('edge', s), mail('before', s + 1), mail('skew', -30)], r, NOW).map((x) => x.id);
    assert.deepStrictEqual(ids, ['edge', 'skew'], r);
  }
});

test('unknown received time is never placed in a range', () => {
  assert.strictEqual(filterByReceived([mail('unknown', null, 0)], '30D', NOW).length, 0);
});

test('changing the range changes counts; chart buckets always match the filtered list', () => {
  const e = [mail('a', 30 * 60, 0, 'HIGH'), mail('b', 5 * H, 0, 'SUSPICIOUS'), mail('c', 3 * D, 0, 'LOW'), mail('d', 12 * D, 0, 'INCONCLUSIVE'),
    mail('e', 40 * D, 0, 'HIGH'), mail('now', 0, 0, 'HIGH')];
  const counts = {};
  for (const r of Object.keys(RANGES)) {
    const list = filterByReceived(e, r, NOW);
    const b = bucketByReceived(e, r, NOW);
    assert.strictEqual(b.reduce((s, x) => s + x.total, 0), list.length, r);
    assert.strictEqual(b.length, RANGES[r].buckets);
    counts[r] = list.length;
  }
  assert.deepStrictEqual(counts, { '1H': 2, '24H': 3, '7D': 4, '30D': 5 });
  assert.strictEqual(bucketByReceived(e, '24H', NOW)[23].HIGH, 2);  // received "now" lands in the last bucket
});
