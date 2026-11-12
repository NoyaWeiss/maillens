import { useMemo, useState } from 'react';
import { VERDICTS, VERDICT_ORDER } from './ui.jsx';
import { bucketByReceived } from './timefilter.js';

function bucketLabel(start, size) {
  const d = new Date(start * 1000);
  if (size < 86400) return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Stacked bars of analyzed emails per period, by RECEIVED time, over exactly the selected window. */
export default function ActivityChart({ emails, cutoff, now, label }) {
  const [active, setActive] = useState(null);
  const { buckets, max } = useMemo(() => {
    const b = bucketByReceived(emails, cutoff, now);
    return { buckets: b, max: Math.max(1, ...b.map((x) => x.total)) };
  }, [emails, cutoff, now]);
  const total = buckets.reduce((s, b) => s + b.total, 0);
  return (
    <div className="chart">
      <div className="chart-legend" aria-hidden="true">
        {VERDICT_ORDER.map((v) => <span key={v}><i className={`sw sw-${VERDICTS[v].tone}`} />{VERDICTS[v].label}</span>)}
      </div>
      <div className="chart-plot" role="group" aria-label={`Analyzed emails received in the ${label}: ${total} in total. Use Tab to inspect each period.`}>
        <div className="chart-grid" aria-hidden="true"><span>{max}</span><span>{Math.round(max / 2)}</span><span>0</span></div>
        <div className="chart-bars">
          {buckets.map((b, i) => (
            <button key={i} type="button" className={`bar ${active === i ? 'is-active' : ''}`}
              onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(i)} onBlur={() => setActive(null)}
              aria-label={`${bucketLabel(b.start, b.size)}: ${b.total} analyzed${b.total ? ', ' + VERDICT_ORDER.filter((v) => b[v]).map((v) => `${b[v]} ${VERDICTS[v].label}`).join(', ') : ''}`}>
              <span className="bar-stack" style={{ height: `${(b.total / max) * 100}%` }}>
                {VERDICT_ORDER.map((v) => (b[v] ? <span key={v} className={`seg seg-${VERDICTS[v].tone}`} style={{ flexGrow: b[v] }} /> : null))}
              </span>
              {active === i ? (
                <span className="tooltip" role="presentation">
                  <strong>{bucketLabel(b.start, b.size)}</strong>
                  <span>{b.total} received</span>
                  {VERDICT_ORDER.filter((v) => b[v]).map((v) => <span key={v}><i className={`sw sw-${VERDICTS[v].tone}`} />{b[v]} {VERDICTS[v].label}</span>)}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-axis" aria-hidden="true">
        <span>{bucketLabel(cutoff, buckets[0].size)}</span>
        <span>{bucketLabel((cutoff + now) / 2, buckets[0].size)}</span>
        <span>{buckets[0].size < 86400 ? 'Now' : 'Today'}</span>
      </div>
    </div>
  );
}
