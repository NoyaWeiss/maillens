import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, ApiError, getSession, redeemLaunchCode } from './api.js';
import demo from './demo.json';
import HowItWorks from './HowItWorks.jsx';
import Investigation from './Investigation.jsx';
import Overview from './Overview.jsx';
import Performance from './Performance.jsx';
import { State } from './ui.jsx';

const NAV = [
  { key: 'overview', label: 'Overview', icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z' },
  { key: 'investigate', label: 'Security Investigations', icon: 'M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z' },
  { key: 'performance', label: 'Detection Performance', icon: 'M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z' },
  { key: 'how', label: 'How MailLens Works', icon: 'M12 2a10 10 0 100 20 10 10 0 000-20zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26A1.99 1.99 0 0012 7a2 2 0 00-2 2H8a4 4 0 118 0c0 .88-.36 1.68-.93 2.25z' },
];

function parseRoute() {
  const [, page = 'overview', id = ''] = window.location.hash.match(/^#\/([a-z]+)(?:\/([A-Za-z0-9_-]+))?/) || [];
  return { page: NAV.some((n) => n.key === page) ? page : 'overview', id };
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  const [account, setAccount] = useState({ status: 'loading' });
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    const on = () => setRoute(parseRoute());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  const go = useCallback((page, id) => { window.location.hash = `#/${page}${id ? '/' + id : ''}`; }, []);

  const loadAccount = useCallback(async () => {
    try {
      const fresh = await redeemLaunchCode();
      const session = fresh || getSession();
      if (!session) { setAccount({ status: 'none' }); return; }
      const d = await api.emails();
      setAccount({ status: 'ready', emails: d.emails, context: session.context || d.context, label: d.account_label || session.label, now: d.now });
      if (fresh && session.context) go('overview');
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setAccount({ status: 'expired', message: e.message });
      else setAccount({ status: 'error', message: e.message });
    }
  }, [go]);
  useEffect(() => { loadAccount(); }, [loadAccount]);

  const demoSource = useMemo(() => {
    const now = Date.now() / 1000;
    const emails = demo.emails.map((e) => ({ id: e.id, analyzed_at: now - e.minutes_ago * 60, verdict: e.result.verdict, score: e.result.score,
      subject: e.subject, sender: e.sender, category: e.result.category, headline: e.result.headline, times_analyzed: 1 }));
    return { mode: 'demo', emails, now, context: null,
      loadDetail: async (id) => { const e = demo.emails.find((x) => x.id === id); if (!e) throw new ApiError(404, 'Not found');
        return { subject: e.subject, sender: e.sender, analyzed_at: now - e.minutes_ago * 60, result: e.result }; } };
  }, []);

  const accountSource = useMemo(() => (account.status === 'ready' ? {
    mode: 'account', emails: account.emails, now: account.now, context: account.context, loadDetail: (id) => api.email(id),
  } : { mode: 'none', emails: [], now: Date.now() / 1000, context: null, loadDetail: () => Promise.reject(new ApiError(401, 'No session')) }),
  [account]);

  const source = demoMode ? demoSource : accountSource;
  const onClear = async () => {
    try { await api.clearHistory(); await loadAccount(); } catch (e) { setAccount({ status: 'error', message: e.message }); }
  };
  const examples = useMemo(() => (source.mode === 'none'
    ? { list: demoSource.emails, selected: null, load: demoSource.loadDetail }
    : { list: source.emails, selected: route.page === 'investigate' ? route.id : source.context, load: source.loadDetail }), [source, demoSource, route]);

  const needsAccount = route.page === 'overview' || route.page === 'investigate';
  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <nav className="sidebar" aria-label="Sections">
        <div className="brand"><span className="logo" aria-hidden="true" /><span>MailLens<small>Security Console</small></span></div>
        <ul>
          {NAV.map((n) => (
            <li key={n.key}>
              <a href={`#/${n.key}`} className={route.page === n.key ? 'active' : ''} aria-current={route.page === n.key ? 'page' : undefined}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d={n.icon} /></svg><span>{n.label}</span>
              </a>
            </li>
          ))}
        </ul>
        <div className="sidebar-foot">
          <AccountChip account={account} demoMode={demoMode} />
        </div>
      </nav>

      <main id="main" className="main">
        {demoMode ? (
          <div className="demo-banner" role="status">
            <span><b>Demo Mode</b> · synthetic emails from the MailLens demo mailbox, analyzed by the real engine. Not your account.</span>
            <button type="button" className="btn btn-ghost small" onClick={() => setDemoMode(false)}>Exit Demo Mode</button>
          </div>
        ) : null}

        {needsAccount && !demoMode && account.status === 'loading' ? <div className="panel"><State kind="loading" title="Connecting to your MailLens backend…" /></div> : null}
        {needsAccount && !demoMode && account.status === 'expired' ? (
          <div className="panel"><State kind="error" title="This dashboard link has expired" action={<button type="button" className="btn btn-secondary" onClick={() => setDemoMode(true)}>Explore Demo Mode</button>}>
            For your privacy, links work once and sessions last 8 hours. Open the dashboard again from MailLens in Gmail.</State></div>
        ) : null}
        {needsAccount && !demoMode && account.status === 'error' ? (
          <div className="panel"><State kind="error" title="The MailLens backend is unavailable" action={<button type="button" className="btn btn-secondary" onClick={loadAccount}>Try again</button>}>
            {account.message} Check that the backend and your tunnel are running.</State></div>
        ) : null}

        {route.page === 'overview' && (demoMode || ['ready', 'none'].includes(account.status)) ? (
          <Overview source={source} onInvestigate={(id) => go('investigate', id)} onClear={onClear} onDemo={() => setDemoMode(true)} />
        ) : null}
        {route.page === 'investigate' && (demoMode || ['ready', 'none'].includes(account.status)) ? (
          <Investigation source={source} selected={route.id || source.context} onSelect={(id) => go('investigate', id)} />
        ) : null}
        {route.page === 'performance' ? <Performance /> : null}
        {route.page === 'how' ? (
          <HowItWorks examples={examples} exampleLabel={source.mode === 'account' ? 'From your analyzed emails.' : 'Synthetic demo example.'} />
        ) : null}
      </main>
    </div>
  );
}

function AccountChip({ account, demoMode }) {
  if (demoMode) return <p className="acct acct-demo"><span className="acct-dot" />Demo Mode</p>;
  if (account.status === 'ready') {
    return <p className="acct"><span className="acct-dot ok" />{account.label ? <span className="mono">{account.label}</span> : 'Gmail account connected'}<small>Session for this tab only</small></p>;
  }
  return <p className="acct"><span className="acct-dot" />No account connected<small>Open from Gmail</small></p>;
}

