import { useId, useState } from 'react';

export const VERDICTS = {
  HIGH: { label: 'High risk', tone: 'high' },
  SUSPICIOUS: { label: 'Suspicious', tone: 'susp' },
  INCONCLUSIVE: { label: 'Inconclusive', tone: 'inc' },
  LOW: { label: 'Low risk', tone: 'low' },
};
export const VERDICT_ORDER = ['HIGH', 'SUSPICIOUS', 'INCONCLUSIVE', 'LOW'];

export const BASIS = {
  OBSERVED: 'Seen in this email',
  MAILBOX: 'From your email history',
  HEURISTIC: 'Based on the wording',
};

export function SectionHeader({ title, subtitle, children }) {
  return (
    <header className="section-header">
      <div>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
      {children ? <div className="section-header-aside">{children}</div> : null}
    </header>
  );
}

export function Panel({ title, subtitle, aside, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      {title ? (
        <div className="panel-head">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p className="panel-sub">{subtitle}</p> : null}
          </div>
          {aside}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function VerdictBadge({ verdict, size = 'md' }) {
  const v = VERDICTS[verdict] || { label: verdict, tone: 'inc' };
  return <span className={`badge badge-${v.tone} badge-${size}`}><span className="dot" aria-hidden="true" />{v.label}</span>;
}

export function RiskIndex({ score, verdict }) {
  if (score === null || score === undefined) return <span className="muted small">Risk index not available</span>;
  const tone = (VERDICTS[verdict] || {}).tone || 'inc';
  return (
    <span className="risk-index" title="Position within the risk level. Not a probability.">
      <span className="risk-num">{score}<span className="muted">/100</span></span>
      <span className="meter" aria-hidden="true"><span className={`meter-fill fill-${tone}`} style={{ width: `${Math.max(3, score)}%` }} /></span>
    </span>
  );
}

export function Disclosure({ title, hint, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={`disclosure ${open ? 'open' : ''}`}>
      <button type="button" className="disclosure-btn" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        <span className="chev" aria-hidden="true">›</span>
        <span className="disclosure-title">{title}</span>
        {hint ? <span className="disclosure-hint">{hint}</span> : null}
      </button>
      {open ? <div id={id} className="disclosure-body">{children}</div> : null}
    </div>
  );
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value}
          className={value === o.value ? 'active' : ''} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function State({ kind = 'empty', title, children, action }) {
  return (
    <div className={`state state-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {kind === 'loading' ? <span className="spinner" aria-hidden="true" /> : <span className={`state-icon icon-${kind}`} aria-hidden="true" />}
      <div>
        <p className="state-title">{title}</p>
        {children ? <div className="state-text">{children}</div> : null}
        {action ? <div className="state-action">{action}</div> : null}
      </div>
    </div>
  );
}

/** "Name <address>" -> { name, address } for display. */
export function splitSender(s) {
  const m = String(s || '').match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$/);
  return m ? { name: m[1] || m[2], address: m[2] } : { name: s, address: '' };
}

export function timeAgo(ts, now = Date.now() / 1000) {
  const d = Math.max(0, now - ts);
  if (d < 60) return 'just now';
  if (d < 3600) return `${Math.floor(d / 60)} min ago`;
  if (d < 86400) return `${Math.floor(d / 3600)} h ago`;
  return `${Math.floor(d / 86400)} d ago`;
}

export function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
