import { useMemo, useState } from 'react';
import ActivityChart, { RANGES } from './ActivityChart.jsx';
import { Panel, RiskIndex, SectionHeader, Segmented, State, VerdictBadge, splitSender, timeAgo } from './ui.jsx';

const RANGE_OPTIONS = Object.keys(RANGES).map((k) => ({ value: k, label: k }));

export default function Overview({ source, onInvestigate, onClear, onDemo }) {
  const [range, setRange] = useState('7D');
  const { emails = [], context, now, mode } = source;
  const inRange = useMemo(() => emails.filter((e) => e.analyzed_at >= now - RANGES[range].seconds), [emails, range, now]);
  const count = (v) => inRange.filter((e) => e.verdict === v).length;
  const current = context ? emails.find((e) => e.id === context) : null;

  return (
    <>
      <SectionHeader title="Account Security Activity" subtitle="Your analyzed emails, risk activity, and recent findings." />

      {mode === 'none' ? (
        <Panel>
          <State title="Open the dashboard from Gmail to see your account" action={
            <button type="button" className="btn btn-secondary" onClick={onDemo}>Explore Demo Mode</button>}>
            In Gmail, open MailLens and choose <b>View full dashboard</b>. The add-on creates a one-time, private link for your
            account. Detection Performance and How MailLens Works are available without signing in.
          </State>
        </Panel>
      ) : null}

      {current ? (
        <Panel className="context-panel" title="Current email" subtitle="The email you opened the dashboard from.">
          <div className="context-row">
            <div className="context-main">
              <p className="context-subject">{current.subject}</p>
              <p className="muted small">{splitSender(current.sender).name} · <span className="mono">{splitSender(current.sender).address}</span></p>
              <p className="context-headline">{current.headline}</p>
            </div>
            <div className="context-side">
              <VerdictBadge verdict={current.verdict} size="lg" />
              <RiskIndex score={current.score} verdict={current.verdict} />
              <button type="button" className="btn btn-primary" onClick={() => onInvestigate(current.id)}>Open investigation</button>
            </div>
          </div>
        </Panel>
      ) : null}

      {mode !== 'none' ? (
        <>
          <div className="toolbar">
            <p className="muted small">Showing the {RANGES[range].label} · records are kept for 30 days</p>
            <Segmented label="Time range" options={RANGE_OPTIONS} value={range} onChange={setRange} />
          </div>
          <div className="stats">
            <Stat label="Analyzed emails" value={inRange.length} />
            <Stat label="High risk" value={count('HIGH')} tone="high" />
            <Stat label="Suspicious" value={count('SUSPICIOUS')} tone="susp" />
            <Stat label="Inconclusive" value={count('INCONCLUSIVE')} tone="inc" />
          </div>
          <Panel title="Risk activity" subtitle="Emails analyzed over time, colored by verdict (by the time each was last analyzed).">
            {emails.length ? <ActivityChart emails={emails} range={range} now={now} />
              : <State title="No analyzed emails yet">Open an email in Gmail with MailLens. Each analysis appears here.</State>}
          </Panel>
          {emails.length ? <Panel title="Recent analyzed emails" subtitle="Select an email to see why it received its verdict."
            aside={mode === 'account' && emails.length ? <ClearHistory onClear={onClear} /> : null}>
            {inRange.length ? (
              <ul className="email-list">
                {inRange.slice(0, 8).map((e) => (
                  <li key={e.id}>
                    <button type="button" className="email-row" onClick={() => onInvestigate(e.id)}>
                      <VerdictBadge verdict={e.verdict} size="sm" />
                      <span className="email-text">
                        <span className="email-subject">{e.subject}</span>
                        <span className="muted small">{splitSender(e.sender).name}{e.category ? ` · ${e.category}` : ''}</span>
                      </span>
                      <span className="muted small nowrap">{timeAgo(e.analyzed_at, now)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <State title="Nothing analyzed in this period">Choose a longer time range above.</State>}
          </Panel> : null}
        </>
      ) : null}
    </>
  );
}

function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone ? 'stat-' + tone : ''}`}>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function ClearHistory({ onClear }) {
  const [confirming, setConfirming] = useState(false);
  if (!confirming) return <button type="button" className="btn btn-ghost small" onClick={() => setConfirming(true)}>Clear history</button>;
  return (
    <span className="confirm">
      <span className="small">Delete this account&apos;s history?</span>
      <button type="button" className="btn btn-danger small" onClick={() => { setConfirming(false); onClear(); }}>Delete</button>
      <button type="button" className="btn btn-ghost small" onClick={() => setConfirming(false)}>Cancel</button>
    </span>
  );
}
