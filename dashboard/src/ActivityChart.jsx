import { useMemo, useState } from 'react';
import { VERDICTS, VERDICT_ORDER } from './ui.jsx';

export const RANGES = {
  '1H': { seconds: 3600, buckets: 12, label: 'last hour' },
  '24H': { seconds: 86400, buckets: 24, label: 'last 24 hours' },
  '7D': { seconds: 7 * 86400, buckets: 7, label: 'last 7 days' },
  '30D': { seconds: 30 * 86400, buckets: 30, label: 'last 30 days' },
};

function bucketLabel(start, size) {
  const d = new Date(start * 1000);
  if (size < 86400) return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Stacked bars of analyzed emails per time bucket, by verdict. Built from recorded events only. */
export default function ActivityChart({ emails, range, now }) {
  const [active, setActive] = useState(null);
  const { buckets, max } = useMemo(() => {
    const r = RANGES[range];
    const size = r.seconds / r.buckets;
    const start = now - r.seconds;
    const b = Array.from({ length: r.buckets }, (_, i) => ({ start: start + i * size, size, HIGH: 0, SUSPICIOUS: 0, INCONCLUSIVE: 0, LOW: 0, total: 0 }));
    for (const e of emails) {
      const i = Math.floor((e.analyzed_at - start) / size);
      if (i >= 0 && i < b.length) { b[i][e.verdict] += 1; b[i].total += 1; }
    }
    return { buckets: b, max: Math.max(1, ...b.map((x) => x.total)) };
  }, [emails, range, now]);

  const total = buckets.reduce((s, b) => s + b.total, 0);
  const tick = Math.ceil(buckets.length / 6);
  return (
    <div className="chart">
      <div className="chart-legend" aria-hidden="true">
        {VERDICT_ORDER.map((v) => <span key={v}><i className={`sw sw-${VERDICTS[v].tone}`} />{VERDICTS[v].label}</span>)}
      </div>
      <div className="chart-plot" role="group" aria-label={`Analyzed emails in the ${RANGES[range].label}: ${total} in total. Use Tab to inspect each period.`}>
        <div className="chart-grid" aria-hidden="true"><span>{max}</span><span>{Math.round(max / 2)}</span><span>0</span></div>
        <div className="chart-bars">
          {buckets.map((b, i) => (
            <button key={i} type="button" className={`bar ${active === i ? 'is-active' : ''}`}
              onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(i)} onBlur={() => setActive(null)}
              aria-label={`${bucketLabel(b.start, b.size)}: ${b.total} analyzed${b.total ? ', ' + VERDICT_ORDER.filter((v) => b[v]).map((v) => `${b[v]} ${VERDICTS[v].label}`).join(', ') : ''}`}>
              <span className="bar-stack" style={{ height: `${(b.total / max) * 100}%` }}>
                {VERDICT_ORDER.map((v) => b[v] ? <span key={v} className={`seg seg-${VERDICTS[v].tone}`} style={{ flexGrow: b[v] }} /> : null)}
              </span>
              {active === i ? (
                <span className="tooltip" role="presentation">
                  <strong>{bucketLabel(b.start, b.size)}</strong>
                  <span>{b.total} analyzed</span>
                  {VERDICT_ORDER.filter((v) => b[v]).map((v) => <span key={v}><i className={`sw sw-${VERDICTS[v].tone}`} />{b[v]} {VERDICTS[v].label}</span>)}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-axis" aria-hidden="true">
        {buckets.map((b, i) => <span key={i}>{i % tick === 0 ? bucketLabel(b.start, b.size) : ''}</span>)}
      </div>
    </div>
  );
}
