import { useEffect, useState } from 'react';
import { BASIS, Disclosure, Panel, SectionHeader, State, VerdictBadge } from './ui.jsx';

// Mirrors backend/app/engine.py (CHECK_NAMES, signal modules) and backend/app/decision.py.
const STAGES = [
  { key: 'collect', n: 1, title: 'Examine', short: 'What is read',
    text: 'The add-on reads the opened email: sender and reply addresses, Google’s authentication result, subject, visible and hidden text, links, and attachment names and types. With your permission it also summarizes who you’ve emailed in the last 180 days.',
    checks: [] },
  { key: 'identity', n: 2, title: 'Identity', short: 'Who really sent it',
    text: 'Checks Google’s SPF, DKIM and DMARC result, whether the display name or reply address contradicts the sender, look-alike domains (including character swaps), and names that collide with people you know.',
    checks: ['S1', 'S2', 'S3', 'S4', 'S5'] },
  { key: 'relationship', n: 3, title: 'Relationship', short: 'Do you know them',
    text: 'Compares the sender with your recent correspondence and the thread’s earlier messages. Unknown familiarity (no mailbox access) is never treated as “unfamiliar”, so missing data can’t raise risk.',
    checks: ['S6', 'S7'] },
  { key: 'content', n: 4, title: 'Content', short: 'Links, files, hidden text',
    text: 'Finds links whose text and destination disagree, deceptive URL construction, risky attachment types, and hidden text aimed at scanners.',
    checks: ['S9', 'S10', 'S11', 'S12'] },
  { key: 'request', n: 5, title: 'Request', short: 'What it asks you to do',
    text: 'Recognizes sensitive actions (payment or bank changes, credentials and MFA codes, gift cards, permissions, data disclosure, call-backs) and pressure or secrecy. Quoted, described and negated requests are ignored.',
    checks: ['S13', 'S14'] },
  { key: 'decide', n: 6, title: 'Decide', short: 'Combine evidence',
    text: 'Keeps one finding per thing examined (the strongest), never adds levels together, and counts independent entities. Fixed, ordered rules then assign the verdict.',
    checks: [] },
  { key: 'explain', n: 7, title: 'Explain', short: 'Plain-language result',
    text: 'Turns the decision into a headline, up to two reasons with their basis (seen in the email, from your history, or based on the wording), the possible impact, and recommended actions.',
    checks: [] },
];

const RULES = [
  ['HIGH', 'Strongest-level deception (for example a confusable look-alike of a known domain).'],
  ['HIGH', 'A strong warning sign together with a risky request, or strong warning signs about two different things.'],
  ['HIGH', 'A high-impact request with at least two corroborating signs: pressure wording, an unfamiliar sender, or weaker warning signs.'],
  ['SUSPICIOUS', 'A strong warning sign on its own, or a high-impact request on its own (for example new bank details).'],
  ['SUSPICIOUS', 'A sign-in request leading off-site, or a known contact sharing a file through an unrelated site.'],
  ['SUSPICIOUS', 'An unfamiliar sender asking for a sensitive action, plus an independent warning sign (unrelated link, call-back number, risky file, pressure, or money lure).'],
  ['SUSPICIOUS', 'An unfamiliar sender combining a pretext with a request for secrecy.'],
  ['INCONCLUSIVE', 'It would be Low, but authentication results are missing and there is a risky request or a weak warning sign.'],
  ['LOW', 'None of the above. Low risk is not a guarantee of safety.'],
];

export default function HowItWorks({ examples, exampleLabel }) {
  const [stage, setStage] = useState('identity');
  const s = STAGES.find((x) => x.key === stage);
  return (
    <>
      <SectionHeader title="Detection Explained" subtitle="From email signals to an explainable security decision." />
      <Panel title="How an email is analyzed" subtitle="Select a step to see what it does.">
        <ol className="flow" aria-label="Analysis steps">
          {STAGES.map((x) => (
            <li key={x.key}>
              <button type="button" className={`flow-step ${stage === x.key ? 'active' : ''}`} aria-pressed={stage === x.key} onClick={() => setStage(x.key)}>
                <span className="flow-n">{x.n}</span>
                <span className="flow-title">{x.title}</span>
                <span className="flow-short">{x.short}</span>
              </button>
            </li>
          ))}
        </ol>
        <div className="flow-detail" aria-live="polite">
          <p className="ev-title">{s.n}. {s.title}</p>
          <p>{s.text}</p>
          {s.key === 'decide' ? (
            <ul className="rules">{RULES.map(([v, t], i) => <li key={i}><VerdictBadge verdict={v} size="sm" /><span>{t}</span></li>)}</ul>
          ) : null}
          {s.key === 'decide' ? <p className="muted small">The risk index (0–100) is a position within the verdict’s band (Low 8–20, Suspicious 40–60, High 75–95), not a probability. Inconclusive has no index.</p> : null}
        </div>
      </Panel>

      <Walkthrough examples={examples} exampleLabel={exampleLabel} />

      <Panel title="Safeguards, privacy and limits" subtitle="Optional detail for security reviewers.">
        <Disclosure title="False-alarm safeguards">
          <ul className="plain">
            <li>Bulk mail (newsletters) can only downgrade weak findings; it never hides authentication failures or the strongest findings.</li>
            <li>Requests that are quoted, described, or ruled out (“we will never ask for your password”) are not treated as requests.</li>
            <li>A phish forwarded by a known, authenticated colleague (for example to IT) is evaluated as reported content.</li>
            <li>SPF failures are ignored when DKIM and DMARC pass, as with forwarded mail; links to the sender’s own signing domain or major providers are trusted.</li>
            <li>Missing information never raises risk: with no mailbox access or no authentication result, checks are marked unavailable instead.</li>
          </ul>
        </Disclosure>
        <Disclosure title="Privacy and data handling">
          <ul className="plain">
            <li>The opened email is sent over HTTPS to <b>your own</b> MailLens backend, which makes no outbound network calls.</li>
            <li>Relationship checks send only a summary (known domains, how often you’ve emailed the sender), not your sent mail.</li>
            <li>Dashboard history keeps subject, sender and the analysis result for 30 days, never the message body. It is keyed by a one-way hash of a private per-account key, and you can delete it from the Overview.</li>
            <li>The dashboard opens through a one-time link that expires in two minutes. No tokens, API keys or email content are placed in the URL.</li>
          </ul>
        </Disclosure>
        <Disclosure title="Permissions">
          <ul className="plain">
            <li><span className="mono">gmail.addons.execute</span>, <span className="mono">gmail.addons.current.message.readonly</span>: run in Gmail and read only the email you open.</li>
            <li><span className="mono">gmail.readonly</span> (optional): recipients of mail you’ve sent and earlier headers in the open thread, for relationship checks.</li>
            <li><span className="mono">script.external_request</span>, <span className="mono">script.storage</span>: call your backend and store settings. The dashboard added no new permissions.</li>
          </ul>
        </Disclosure>
        <Disclosure title="General limitations">
          <ul className="plain">
            <li>A well-made attack from a new sender with valid authentication can look clean.</li>
            <li>Attachment contents and text inside images are not analyzed; there are no reputation or threat-intelligence lookups.</li>
            <li>Request wording is recognized in English only; attack types outside the known sensitive actions can be missed.</li>
          </ul>
        </Disclosure>
      </Panel>
    </>
  );
}

function Walkthrough({ examples, exampleLabel }) {
  const [id, setId] = useState(examples.selected || examples.list[0]?.id);
  const [detail, setDetail] = useState({ status: 'idle' });
  useEffect(() => { if (examples.selected) setId(examples.selected); }, [examples.selected]);
  useEffect(() => {
    if (!id) return undefined;
    let live = true;
    setDetail({ status: 'loading' });
    examples.load(id).then((d) => live && setDetail({ status: 'ready', d })).catch((e) => live && setDetail({ status: 'error', message: e.message }));
    return () => { live = false; };
  }, [id, examples]);

  return (
    <Panel title="Walkthrough of a real analysis" subtitle={`Each step for one analyzed email: what ran, what it found, and why the verdict followed. ${exampleLabel}`}
      aside={examples.list.length ? (
        <select className="input select" value={id || ''} onChange={(e) => setId(e.target.value)} aria-label="Choose an analyzed email">
          {examples.list.map((e) => <option key={e.id} value={e.id}>{e.subject.slice(0, 60)}</option>)}
        </select>) : null}>
      {!examples.list.length ? <State title="No analyzed emails to walk through" /> : null}
      {detail.status === 'loading' ? <State kind="loading" title="Loading…" /> : null}
      {detail.status === 'error' ? <State kind="error" title="Couldn't load this analysis">{detail.message}</State> : null}
      {detail.status === 'ready' ? <Steps r={detail.d.result} /> : null}
    </Panel>
  );
}

function Steps({ r }) {
  const checks = Object.fromEntries(r.checks.map((c) => [c.id, c]));
  const all = [...r.findings, ...r.also_observed.map((f) => ({ ...f, also: true }))];
  return (
    <ol className="walk">
      {STAGES.filter((s) => s.checks.length).map((s) => {
        const found = all.filter((f) => s.checks.includes(f.signal));
        const ran = s.checks.filter((c) => checks[c]?.state === 'ran').length;
        return (
          <li key={s.key} className={found.length ? 'has-finding' : ''}>
            <p className="ev-title">{s.title} <span className="muted small">· {ran}/{s.checks.length} checks ran</span></p>
            {found.length ? found.map((f, i) => (
              <p key={i} className="small"><span className={`tag ${f.basis === 'HEURISTIC' ? 'tag-inferred' : 'tag-fact'}`}>{BASIS[f.basis]}</span> {f.title}
                {f.also ? <span className="muted"> (also noticed; counted once)</span> : <span className="muted"> · strength {f.level}/3</span>}</p>
            )) : <p className="muted small">No warning signs.</p>}
            {s.checks.filter((c) => checks[c] && checks[c].state !== 'ran').map((c) => (
              <p key={c} className="muted small">{checks[c].label || checks[c].name}: {checks[c].state === 'unavailable' ? 'unavailable' : 'not applicable'}{checks[c].note ? ` (${checks[c].note})` : ''}</p>
            ))}
          </li>
        );
      })}
      <li className="walk-decision">
        <p className="ev-title">Decision <VerdictBadge verdict={r.verdict} size="sm" /></p>
        <p className="small">{r.decision_explanation}</p>
        <p className="muted small mono">{r.gate_explanation}</p>
      </li>
      <li>
        <p className="ev-title">Explanation shown in Gmail</p>
        <p className="small">{r.headline}</p>
        {r.actions.length ? <p className="muted small">Recommended: {r.actions.map((a) => a.title).join(' · ')}</p> : null}
      </li>
    </ol>
  );
}
