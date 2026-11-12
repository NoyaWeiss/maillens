import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, ApiError, getSession, redeemLaunchCode } from './api.js';
import demo from './demo.json';
import HowItWorks from './HowItWorks.jsx';
import Overview from './Overview.jsx';
import Performance from './Performance.jsx';
import { State } from './ui.jsx';

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'performance', label: 'Detection Performance' },
  { key: 'how', label: 'How MailLens Works' },
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
      <header className="topbar">
        <div className="brand"><span className="logo" aria-hidden="true" /><span>MailLens</span></div>
        <nav aria-label="Sections">
          <ul className="tabs">
            {TABS.map((t) => (
              <li key={t.key}><a href={`#/${t.key}`} className={route.page === t.key ? 'active' : ''} aria-current={route.page === t.key ? 'page' : undefined}>{t.label}</a></li>
            ))}
          </ul>
        </nav>
        <AccountChip account={account} demoMode={demoMode} />
      </header>

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
