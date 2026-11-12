import { useMemo, useState } from 'react';
import { VERDICTS, VERDICT_ORDER } from './ui.jsx';
import { RANGES, bucketByReceived } from './timefilter.js';

export { RANGES };

function bucketLabel(start, size) {
  const d = new Date(start * 1000);
  if (size < 86400) return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Stacked bars of analyzed emails per time bucket, by verdict. Built from recorded events only. */
export default function ActivityChart({ emails, range, now }) {
  const [active, setActive] = useState(null);
  const { buckets, max } = useMemo(() => {
    const b = bucketByReceived(emails, range, now);  // received time only
    return { buckets: b, max: Math.max(1, ...b.map((x) => x.total)) };
  }, [emails, range, now]);

  const total = buckets.reduce((s, b) => s + b.total, 0);
  const tick = Math.ceil(buckets.length / 6);
  return (
    <div className="chart">
      <div className="chart-legend" aria-hidden="true">
        {VERDICT_ORDER.map((v) => <span key={v}><i className={`sw sw-${VERDICTS[v].tone}`} />{VERDICTS[v].label}</span>)}
      </div>
      <div className="chart-plot" role="group" aria-label={`Analyzed emails received in the ${RANGES[range].label}: ${total} in total. Use Tab to inspect each period.`}>
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
