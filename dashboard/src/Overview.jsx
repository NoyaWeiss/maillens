import { useEffect, useMemo, useRef, useState } from 'react';
import ActivityChart from './ActivityChart.jsx';
import { RANGES, filterByReceived } from './timefilter.js';
import EmailAssessment from './Investigation.jsx';
import { api } from './api.js';
import { Panel, SectionHeader, Segmented, State, VERDICTS, VERDICT_ORDER, VerdictBadge, fmtDate, splitSender } from './ui.jsx';

const RANGE_OPTIONS = Object.keys(RANGES).map((k) => ({ value: k, label: k }));

export default function Overview({ source, selected, onSelect, onBack, onClear, onDemo, onRefresh }) {
  const [range, setRangeState] = useState('7D');
  const [now, setNow] = useState(() => Date.now() / 1000);
  const setRange = (r) => { setNow(Date.now() / 1000); setRangeState(r); };  // fresh cutoff on every change
  useEffect(() => setNow(Date.now() / 1000), [source.emails]);
  const [query, setQuery] = useState('');
  const [verdict, setVerdict] = useState('ALL');
  const { emails = [], mode } = source;

  // Every count, the chart and the list use RECEIVED time only (see timefilter.js).
  const inRange = useMemo(() => filterByReceived(emails, range, now), [emails, range, now]);
  const unknown = emails.filter((e) => typeof e.received_at !== 'number').length;
  const list = useMemo(() => inRange.filter((e) => (verdict === 'ALL' || e.verdict === verdict) &&
    (!query || `${e.subject} ${e.sender}`.toLowerCase().includes(query.trim().toLowerCase()))), [inRange, query, verdict]);
  const count = (v) => inRange.filter((e) => e.verdict === v).length;

  if (selected && mode !== 'none') return <EmailAssessment id={selected} source={source} onBack={onBack} />;

  return (
    <>
      <SectionHeader title="Overview" subtitle="Monitor your email security, search messages, and understand potential threats.">
        {mode !== 'none' ? <Segmented label="Time range" options={RANGE_OPTIONS} value={range} onChange={setRange} /> : null}
      </SectionHeader>

      {mode === 'none' ? (
        <Panel>
          <State title="Open the dashboard from Gmail" action={<button type="button" className="btn btn-secondary" onClick={onDemo}>Explore Demo Mode</button>}>
            In MailLens, choose <b>View full dashboard</b> to see your account. Detection Performance and How MailLens Works are available now.
          </State>
        </Panel>
      ) : (
        <>
          <p className="range-note">Showing emails received in the {RANGES[range].label}.</p>
          <div className="stats">
            <Stat label="Analyzed emails" value={inRange.length} />
            <Stat label="High risk" value={count('HIGH')} tone="high" />
            <Stat label="Suspicious" value={count('SUSPICIOUS')} tone="susp" />
            <Stat label="Inconclusive" value={count('INCONCLUSIVE')} tone="inc" />
          </div>

          <Panel title="Risk activity" aside={<ScanInbox mode={mode} available={source.scan} range={range} onFinished={onRefresh} />}>
            {emails.length ? <ActivityChart emails={emails} range={range} now={now} />
              : <State title="No analyzed emails yet">Open an email with MailLens in Gmail, or scan your inbox.</State>}
          </Panel>

          {emails.length ? (
            <Panel title="Emails" aside={mode === 'account' ? <ClearHistory onClear={onClear} /> : null}>
              <div className="filters">
                <input type="search" className="input" placeholder="Search sender or subject" value={query}
                  onChange={(e) => setQuery(e.target.value)} aria-label="Search sender or subject" />
                <div className="chips" role="group" aria-label="Filter by risk level">
                  {['ALL', ...VERDICT_ORDER].map((v) => (
                    <button key={v} type="button" aria-pressed={verdict === v} className={`chip ${verdict === v ? 'active' : ''}`}
                      onClick={() => setVerdict(v)}>{v === 'ALL' ? 'All' : VERDICTS[v].label}</button>
                  ))}
                </div>
              </div>
              {list.length ? (
                <ul className="email-list">
                  {list.map((e) => {
                    const s = splitSender(e.sender);
                    return (
                      <li key={e.id}>
                        <button type="button" className={`email-row ${e.id === source.context ? 'is-context' : ''}`} onClick={() => onSelect(e.id)}>
                          <VerdictBadge verdict={e.verdict} />
                          <span className="email-text">
                            <span className="email-subject">{e.subject}</span>
                            <span className="email-sender">{s.name}</span>
                          </span>
                          <span className="email-date">{e.id === source.context ? <span className="from-gmail">Opened in Gmail</span> : null}{fmtDate(e.received_at)}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : <p className="muted pad">No emails received in the {RANGES[range].label} match.</p>}
              <p className="footnote">{mode === 'demo' ? 'Synthetic demo emails.' : 'Only emails MailLens has analyzed are listed.'}
                {unknown ? ` ${unknown} older ${unknown === 1 ? 'record has' : 'records have'} no received time and ${unknown === 1 ? 'is' : 'are'} hidden; open ${unknown === 1 ? 'it' : 'them'} in Gmail again to update.` : ''}</p>
            </Panel>
          ) : null}
        </>
      )}
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

/** Opens the user's own Apps Script scan page (existing Gmail permission) and tracks its progress. */
function ScanInbox({ mode, available, range, onFinished }) {
  const [scan, setScan] = useState({ status: 'idle' });
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);

  if (mode !== 'account') return null;
  if (!available) return <span className="muted small" title="Run scripts/push-addon.sh to enable the scan page.">Inbox scan isn't set up</span>;

  const poll = (ticket, started) => {
    timer.current = setTimeout(async () => {
      try {
        const p = await api.scanStatus(ticket);
        const waited = Date.now() - started;
        if (p.state === 'done') { setScan({ status: 'done', p }); onFinished(); return; }
        if (p.state === 'error') { setScan({ status: 'error', message: p.error || 'The scan stopped.' }); return; }
        if (p.state === 'cancelled') { setScan({ status: 'error', message: `Scan cancelled after ${p.done} emails.` }); onFinished(); return; }
        if (waited > 15 * 60 * 1000) { setScan({ status: 'error', message: 'The scan timed out.' }); return; }
        setScan({ status: p.state === 'running' ? 'running' : 'waiting', p, slow: p.state === 'waiting' && waited > 60000 });
        poll(ticket, started);
      } catch (e) { setScan({ status: 'error', message: e.message }); }
    }, 2000);
  };

  const start = async () => {
    const tab = window.open('about:blank', '_blank'); // opened synchronously so the browser doesn't block it
    setScan({ status: 'starting' });
    try {
      const r = await api.startScan(range);
      if (tab) { tab.opener = null; tab.location.href = r.url; }
      setScan({ status: 'waiting', url: tab ? null : r.url });
      poll(r.ticket, Date.now());
    } catch (e) {
      if (tab) tab.close();
      setScan({ status: 'error', message: e.message });
    }
  };

  const busy = ['starting', 'waiting', 'running'].includes(scan.status);
  const p = scan.p || {};
  const processed = (p.done || 0) + (p.failed || 0) + (p.skipped || 0);
  return (
    <div className="scan" aria-live="polite">
      {scan.status === 'waiting' ? <span className="scan-msg">{scan.url
        ? <a href={scan.url} target="_blank" rel="noopener noreferrer">Open the scan page</a>
        : scan.slow ? 'Continue in the Google tab (approve access if asked)' : 'Starting in a new tab…'}</span> : null}
      {scan.status === 'running' ? (
        <span className="scan-msg"><span className="scan-bar"><span style={{ width: `${p.total ? (100 * processed) / p.total : 5}%` }} /></span>{processed}/{p.total}</span>
      ) : null}
      {scan.status === 'done' ? <span className="scan-msg ok">Scanned {p.total}: {p.done} new{p.skipped ? `, ${p.skipped} already analyzed` : ''}{p.failed ? `, ${p.failed} failed` : ''}</span> : null}
      {scan.status === 'error' ? <span className="scan-msg err" role="alert">{scan.message}</span> : null}
      <span className="scan-action">
        <button type="button" className="btn btn-primary" onClick={start} disabled={busy}>{busy ? 'Scanning…' : 'Scan inbox'}</button>
        <span className="scan-hint">Scans emails received in the {RANGES[range].label} (up to 50).</span>
      </span>
    </div>
  );
}

function ClearHistory({ onClear }) {
  const [confirming, setConfirming] = useState(false);
  if (!confirming) return <button type="button" className="btn btn-ghost" onClick={() => setConfirming(true)}>Clear history</button>;
  return (
    <span className="confirm">
      <span>Delete all records?</span>
      <button type="button" className="btn btn-danger" onClick={() => { setConfirming(false); onClear(); }}>Delete</button>
      <button type="button" className="btn btn-ghost" onClick={() => setConfirming(false)}>Cancel</button>
    </span>
  );
}
