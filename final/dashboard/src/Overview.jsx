import { useEffect, useMemo, useRef, useState } from 'react';
import ActivityChart from './ActivityChart.jsx';
import { DEFAULT_STOP, STOPS, TICKS, cutoffFor, filterByReceived, shortLabel, stopLabel } from './timefilter.js';
import EmailAssessment from './Investigation.jsx';
import { api } from './api.js';
import { Panel, SectionHeader, State, VERDICTS, VERDICT_ORDER, VerdictBadge, fmtDate, splitSender } from './ui.jsx';


export default function Overview({ source, selected, onSelect, onBack, onClear, onDemo, onRefresh }) {
  const [stopIndex, setStopIndex] = useState(DEFAULT_STOP);
  const [now, setNow] = useState(() => Date.now() / 1000);
  const setStop = (i) => { setNow(Date.now() / 1000); setStopIndex(i); };  // fresh cutoff on every change
  useEffect(() => setNow(Date.now() / 1000), [source.emails]);
  const stop = STOPS[stopIndex];
  const label = stopLabel(stop);
  const cutoff = useMemo(() => cutoffFor(stop, now), [stop, now]);
  const [query, setQuery] = useState('');
  const [verdict, setVerdict] = useState('ALL');
  const { emails = [], mode } = source;

  // Every count, the chart and the list use RECEIVED time only (see timefilter.js).
  const inRange = useMemo(() => filterByReceived(emails, cutoff), [emails, cutoff]);
  const unknown = emails.filter((e) => typeof e.received_at !== 'number').length;
  const list = useMemo(() => inRange.filter((e) => (verdict === 'ALL' || e.verdict === verdict) &&
    (!query || `${e.subject} ${e.sender}`.toLowerCase().includes(query.trim().toLowerCase()))), [inRange, query, verdict]);
  const count = (v) => inRange.filter((e) => e.verdict === v).length;

  if (selected && mode !== 'none') return <EmailAssessment id={selected} source={source} onBack={onBack} />;

  return (
    <>
      <SectionHeader title="Overview" subtitle="Monitor your email security, search messages, and understand potential threats." />

      {mode === 'none' ? (
        <Panel>
          <State title="Open the dashboard from Gmail" action={<button type="button" className="btn btn-secondary" onClick={onDemo}>Explore Demo Mode</button>}>
            In MailLens, choose <b>View full dashboard</b> to see your account. Detection Performance and How MailLens Works are available now.
          </State>
        </Panel>
      ) : (
        <>
          <section className="panel range-panel" aria-label="Time range">
            <RangeSlider index={stopIndex} onChange={setStop} label={label} />
            <ScanInbox mode={mode} available={source.scan} label={label} cutoff={cutoff} onFinished={onRefresh} />
          </section>
          <div className="stats">
            <Stat label="Analyzed emails" value={inRange.length} />
            <Stat label="High risk" value={count('HIGH')} tone="high" />
            <Stat label="Suspicious" value={count('SUSPICIOUS')} tone="susp" />
            <Stat label="Inconclusive" value={count('INCONCLUSIVE')} tone="inc" />
          </div>

          <Panel title="Risk activity">
            {emails.length ? <ActivityChart emails={emails} cutoff={cutoff} now={now} label={label} />
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
              ) : <p className="muted pad">No emails received in the {label} match.</p>}
              <p className="footnote">{mode === 'demo' ? 'Synthetic demo emails.' : 'Only emails MailLens has analyzed are listed.'}
                {unknown ? ` ${unknown} older ${unknown === 1 ? 'record has' : 'records have'} no received time and ${unknown === 1 ? 'is' : 'are'} hidden; open ${unknown === 1 ? 'it' : 'them'} in Gmail again to update.` : ''}</p>
            </Panel>
          ) : null}
        </>
      )}
    </>
  );
}

/** Time-range slider: discrete, log-like stops from 1 hour to 1 year (received time). */
function RangeSlider({ index, onChange, label }) {
  const pct = (100 * index) / (STOPS.length - 1);
  return (
    <div className="range">
      <label htmlFor="range" className="range-label">Emails received in the <b>{label}</b></label>
      <input id="range" type="range" min="0" max={STOPS.length - 1} step="1" value={index} style={{ '--pct': `${pct}%` }}
        onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={`Emails received in the ${label}`} />
      <div className="range-ticks" aria-hidden="true">
        {TICKS.map((i) => (
          <button key={i} type="button" tabIndex={-1} style={{ left: `${(100 * i) / (STOPS.length - 1)}%` }}
            className={`${i === index ? 'on' : ''} ${i === 0 ? 'first' : i === STOPS.length - 1 ? 'last' : ''}`} onClick={() => onChange(i)}>{shortLabel(STOPS[i])}</button>
        ))}
      </div>
    </div>
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

/**
 * Inbox scan, kept inside Overview. Gmail can only be read by code running under the user's own Google
 * sign-in, so the scan runs in the user's Apps Script project, loaded in an invisible frame. If the
 * browser blocks Google's sign-in inside frames, or Google needs a consent click, a small Google window
 * is offered instead and closed automatically when the scan finishes.
 */
function ScanInbox({ mode, available, label, cutoff, onFinished }) {
  const [scan, setScan] = useState({ status: 'idle' });
  const timer = useRef(null);
  const win = useRef(null);
  const pageLoaded = useRef(false);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {  // content-free signal from the Google-hosted scan page: "Google showed me in the frame"
    const on = (e) => { if (/\.googleusercontent\.com$/.test(new URL(e.origin).hostname) && e.data && e.data.maillens === 'scan-page-loaded') pageLoaded.current = true; };
    window.addEventListener('message', on);
    return () => window.removeEventListener('message', on);
  }, []);

  if (mode !== 'account') return null;
  if (!available) return <span className="muted small" title="Run scripts/push-addon.sh to enable inbox scanning.">Inbox scan isn't set up</span>;

  const finish = (next) => {
    try { if (win.current && !win.current.closed) win.current.close(); } catch { /* ignore */ }
    win.current = null;
    setScan(next);
    onFinished();
  };

  const poll = (ticket, url, started, lastDone) => {
    timer.current = setTimeout(async () => {
      try {
        const p = await api.scanStatus(ticket);
        const waited = Date.now() - started;
        if (p.done > lastDone) onFinished(); // new results appear in Overview while the scan runs
        if (['done', 'cancelled', 'error'].includes(p.state)) { finish({ status: p.state, p, url }); return; }
        if (waited > 15 * 60 * 1000) { finish({ status: 'error', p: { ...p, error: 'The scan timed out.' }, url }); return; }
        setScan((s) => ({ ...s, status: p.state === 'running' ? 'running' : 'waiting', p, needsWindow: p.state === 'waiting' && waited > 12000, frameLoaded: pageLoaded.current }));
        poll(ticket, url, started, p.done);
      } catch (e) { setScan({ status: 'error', p: { error: e.message } }); }
    }, 1500);
  };

  const start = async () => {
    clearTimeout(timer.current);
    pageLoaded.current = false;
    setScan({ status: 'starting' });
    try {
      const r = await api.startScan(Math.max(3600, Math.round(Date.now() / 1000 - cutoff)));
      setScan({ status: 'waiting', url: r.url, frame: true });
      poll(r.ticket, r.url, Date.now(), 0);
    } catch (e) { setScan({ status: 'error', p: { error: e.message } }); }
  };

  const openWindow = () => {
    win.current = window.open(scan.url, 'maillens-scan', 'popup,width=480,height=560');
    setScan((s) => ({ ...s, frame: false, needsWindow: false, windowOpen: true }));
  };

  const p = scan.p || {};
  const newCount = Math.max(0, (p.total || 0) - (p.skipped || 0));
  const remaining = Math.max(0, newCount - (p.done || 0) - (p.failed || 0));
  const busy = ['starting', 'waiting', 'running'].includes(scan.status);
  const finished = ['done', 'cancelled', 'error'].includes(scan.status);
  const allFailed = finished && p.failed > 0 && !p.done;

  let line = null;
  if (scan.status === 'starting' || (scan.status === 'waiting' && !scan.needsWindow)) line = <span className="scan-msg"><span className="spinner sm" />Connecting to Gmail…</span>;
  if (scan.status === 'waiting' && scan.needsWindow) {
    line = (
      <span className="scan-msg">
        {scan.frameLoaded ? 'Google is waiting for you to confirm access.' : 'Your browser didn\u2019t let Google run the scan inside the dashboard.'}
        <button type="button" className="link" onClick={openWindow}>Continue in a Google window</button>
      </span>
    );
  }
  if (scan.status === 'running') {
    line = (
      <span className="scan-msg">
        <span className="scan-bar" aria-hidden="true"><span style={{ width: `${newCount ? (100 * (newCount - remaining)) / newCount : 0}%` }} /></span>
        {p.total} found · {p.done} analyzed{p.failed ? ` · ${p.failed} failed` : ''} · {remaining} left
      </span>
    );
  }
  if (finished) {
    const summary = `${p.total || 0} found · ${p.done || 0} analyzed${p.skipped ? ` · ${p.skipped} already analyzed` : ''}${p.failed ? ` · ${p.failed} failed` : ''}`;
    const tone = scan.status === 'done' && !p.failed ? 'ok' : 'err';
    const title = scan.status === 'cancelled' ? 'Scan cancelled' : scan.status === 'error' ? 'Scan stopped'
      : allFailed ? 'Scan finished, but no emails could be analyzed' : p.failed ? 'Scan finished with problems' : 'Scan complete';
    line = (
      <span className={`scan-msg ${tone}`} role={tone === 'err' ? 'alert' : 'status'}>
        <span><b>{title}</b> · {summary}{p.error && tone === 'err' ? <span className="scan-err"> ({p.error})</span> : null}</span>
      </span>
    );
  }

  return (
    <div className="scan" aria-live="polite">
      {line}
      <span className="scan-action">
        <button type="button" className={`btn ${finished && tone_(scan, p) ? 'btn-secondary' : 'btn-primary'}`} onClick={start} disabled={busy}>
          {busy ? 'Scanning…' : finished && (p.failed || scan.status !== 'done') ? (p.failed ? 'Retry failed' : 'Scan again') : 'Scan inbox'}
        </button>
        <span className="scan-hint">Scans emails received in the {label} (up to 50).</span>
      </span>
      {busy && scan.frame && scan.url ? <iframe className="scan-frame" title="MailLens inbox scan" src={scan.url} /> : null}
    </div>
  );
}

const tone_ = (scan, p) => scan.status !== 'done' || p.failed;

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
