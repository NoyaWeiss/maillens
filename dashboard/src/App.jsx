import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, ApiError, getSession, redeemLaunchCode } from './api.js';
import demo from './demo.json';
import HowItWorks from './HowItWorks.jsx';
import Overview from './Overview.jsx';
import Performance from './Performance.jsx';
import { State } from './ui.jsx';

const TABS = [
  { key: 'overview', label: 'Overview', icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z' },
  { key: 'performance', label: 'Detection Performance', icon: 'M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z' },
  { key: 'how', label: 'How MailLens Works', icon: 'M12 2a10 10 0 100 20 10 10 0 000-20zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26A1.99 1.99 0 0012 7a2 2 0 00-2 2H8a4 4 0 118 0c0 .88-.36 1.68-.93 2.25z' },
];

function parseRoute() {
  const [, page = 'overview', id = ''] = window.location.hash.match(/^#\/([a-z]+)(?:\/([A-Za-z0-9_-]+))?/) || [];
  if (page === 'investigate') return { page: 'overview', id }; // old links: the investigation now lives in Overview
  return { page: TABS.some((t) => t.key === page) ? page : 'overview', id };
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  const [account, setAccount] = useState({ status: 'loading' });
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    const fixLegacy = () => { // old investigation links -> the selected email inside Overview
      if (/^#\/investigate/.test(window.location.hash)) window.history.replaceState(null, '', window.location.hash.replace('#/investigate', '#/overview'));
    };
    const on = () => { fixLegacy(); setRoute(parseRoute()); };
    window.addEventListener('hashchange', on);
    fixLegacy();
    return () => window.removeEventListener('hashchange', on);
  }, []);
  const go = useCallback((page, id) => { window.location.hash = `#/${page}${id ? '/' + id : ''}`; }, []);

  const loadAccount = useCallback(async ({ fromLaunch = true } = {}) => {
    try {
      const fresh = fromLaunch ? await redeemLaunchCode() : null;
      const session = fresh || getSession();
      if (!session) { setAccount({ status: 'none' }); return; }
      const d = await api.emails();
      setAccount({ status: 'ready', emails: d.emails, context: session.context || d.context, label: d.account_label || session.label,
        scan: !!(d.scan_available ?? session.scan), now: d.now });
      if (fresh && session.context) go('overview', session.context); // opened from an email: show its assessment
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setAccount({ status: 'expired' });
      else setAccount({ status: 'error', message: e.message });
    }
  }, [go]);
  useEffect(() => { loadAccount(); }, [loadAccount]);

  const demoSource = useMemo(() => {
    const now = Date.now() / 1000;
    const at = (e) => now - e.minutes_ago * 60;
    const emails = demo.emails.map((e) => ({ id: e.id, received_at: at(e), analyzed_at: at(e), verdict: e.result.verdict, score: e.result.score,
      subject: e.subject, sender: e.sender, category: e.result.category, headline: e.result.headline }));
    return { mode: 'demo', emails, now, context: null, scan: false,
      loadDetail: async (id) => { const e = demo.emails.find((x) => x.id === id); if (!e) throw new ApiError(404, 'Not found');
        return { subject: e.subject, sender: e.sender, received_at: at(e), analyzed_at: at(e), result: e.result }; } };
  }, []);

  const accountSource = useMemo(() => (account.status === 'ready'
    ? { mode: 'account', emails: account.emails, now: account.now, context: account.context, scan: account.scan, loadDetail: (id) => api.email(id) }
    : { mode: 'none', emails: [], now: Date.now() / 1000, context: null, scan: false, loadDetail: () => Promise.reject(new ApiError(401, 'No session')) }),
  [account]);
  const source = demoMode ? demoSource : accountSource;

  const onClear = async () => {
    try { await api.clearHistory(); await loadAccount({ fromLaunch: false }); go('overview'); } catch (e) { setAccount({ status: 'error', message: e.message }); }
  };

  const ready = demoMode || ['ready', 'none'].includes(account.status);
  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <aside className="sidebar">
        <div className="brand"><span className="logo" aria-hidden="true" /><span>MailLens<small>Security Console</small></span></div>
        <nav aria-label="Sections">
          <ul className="nav">
            {TABS.map((t) => (
              <li key={t.key}>
                <a href={`#/${t.key}`} className={route.page === t.key ? 'active' : ''} aria-current={route.page === t.key ? 'page' : undefined}>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d={t.icon} /></svg><span>{t.label}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="sidebar-foot"><AccountChip account={account} demoMode={demoMode} /></div>
      </aside>

      <main id="main" className="main">
        {demoMode ? (
          <div className="demo-banner" role="status">
            <span><b>Demo Mode</b>: synthetic emails analyzed by the real engine. Not your account.</span>
            <button type="button" className="btn btn-ghost" onClick={() => setDemoMode(false)}>Exit</button>
          </div>
        ) : null}

        {route.page === 'overview' && !demoMode && account.status === 'loading' ? <div className="panel"><State kind="loading" title="Connecting to MailLens…" /></div> : null}
        {route.page === 'overview' && !demoMode && account.status === 'expired' ? (
          <div className="panel"><State kind="error" title="This dashboard link has expired" action={<button type="button" className="btn btn-secondary" onClick={() => setDemoMode(true)}>Explore Demo Mode</button>}>
            Links work once and sessions last 8 hours. Open the dashboard again from MailLens in Gmail.</State></div>
        ) : null}
        {route.page === 'overview' && !demoMode && account.status === 'error' ? (
          <div className="panel"><State kind="error" title="MailLens is unavailable" action={<button type="button" className="btn btn-secondary" onClick={() => loadAccount({ fromLaunch: false })}>Try again</button>}>
            {account.message} Check that the backend and your tunnel are running.</State></div>
        ) : null}

        {route.page === 'overview' && ready ? (
          <Overview source={source} selected={route.id} onSelect={(id) => go('overview', id)} onBack={() => go('overview')}
            onClear={onClear} onDemo={() => setDemoMode(true)} onRefresh={() => loadAccount({ fromLaunch: false })} />
        ) : null}
        {route.page === 'performance' ? <Performance /> : null}
        {route.page === 'how' ? <HowItWorks source={source.mode === 'none' ? null : source} selected={route.id || source.context} /> : null}
      </main>
    </div>
  );
}

function AccountChip({ account, demoMode }) {
  if (demoMode) return <p className="acct"><span className="acct-dot demo" />Demo Mode</p>;
  if (account.status === 'ready') return <p className="acct"><span className="acct-dot ok" />{account.label || 'Gmail account connected'}</p>;
  return <p className="acct"><span className="acct-dot" />Not connected</p>;
}
