import { useEffect, useState } from 'react';
import { BASIS, Disclosure, Panel, SectionHeader, VerdictBadge, splitSender } from './ui.jsx';

// Mirrors backend/app/engine.py (CHECK_NAMES) and backend/app/decision.py.
const STAGES = [
  { key: 'examine', title: 'Examine', checks: [],
    text: 'MailLens reads the opened email: sender details, Google’s authentication result, the text, links and attachment names. With your permission it also notes who you’ve emailed recently.' },
  { key: 'identity', title: 'Identity', checks: ['S1', 'S2', 'S3', 'S4', 'S5'],
    text: 'It checks whether the sender is who they claim to be: authentication, look-alike domains, misleading display names, and reply addresses that go somewhere else.' },
  { key: 'relationship', title: 'Relationship', checks: ['S6', 'S7'],
    text: 'It compares the sender with people you already correspond with and with earlier messages in the thread. Missing history never raises the risk.' },
  { key: 'content', title: 'Content', checks: ['S9', 'S10', 'S11', 'S12'],
    text: 'It looks for links that hide their real destination, risky attachment types, and hidden text aimed at security scanners.' },
  { key: 'request', title: 'Request', checks: ['S13', 'S14'],
    text: 'It recognizes requests for sensitive actions, such as payments, passwords or codes, and pressure or secrecy. Quoted or ruled-out requests don’t count.' },
  { key: 'decide', title: 'Decision', checks: [],
    text: 'Each thing examined counts once, at its strongest finding, and findings are never added up. Fixed rules then choose Low, Suspicious, High or Inconclusive.' },
  { key: 'explain', title: 'Explanation', checks: [],
    text: 'The result becomes a one-line summary, up to three plain-English reasons, and practical next steps.' },
];

export default function HowItWorks({ source, selected }) {
  const [stage, setStage] = useState('identity');
  const emails = source ? source.emails : [];
  const [id, setId] = useState(selected || '');
  const [detail, setDetail] = useState(null);
  useEffect(() => { if (selected) setId(selected); }, [selected]);
  useEffect(() => {
    if (!id || !source) { setDetail(null); return undefined; }
    let live = true;
    source.loadDetail(id).then((d) => live && setDetail(d)).catch(() => live && setDetail(null));
    return () => { live = false; };
  }, [id, source]);

  const s = STAGES.find((x) => x.key === stage);
  const i = STAGES.indexOf(s);
  return (
    <>
      <SectionHeader title="How MailLens Works" subtitle="How MailLens examines email signals and turns evidence into a security decision." />
      <Panel>
        <ol className="stages" aria-label="Analysis stages">
          {STAGES.map((x, n) => (
            <li key={x.key}>
              <button type="button" className={`stage ${stage === x.key ? 'active' : ''}`} aria-pressed={stage === x.key} onClick={() => setStage(x.key)}>
                <span className="stage-n">{n + 1}</span><span className="stage-title">{x.title}</span>
              </button>
            </li>
          ))}
        </ol>

        <div className="stage-panel" aria-live="polite">
          <div className="stage-head">
            <h2>{i + 1}. {s.title}</h2>
            {emails.length ? (
              <select className="input select" value={id} onChange={(e) => setId(e.target.value)} aria-label="Show this step for an analyzed email">
                <option value="">General explanation</option>
                {emails.map((e) => <option key={e.id} value={e.id}>{e.subject.slice(0, 56)}</option>)}
              </select>
            ) : null}
          </div>
          <p className="stage-text">{s.text}</p>
          {detail ? <Observation stage={s} d={detail} /> : null}
          {detail && (s.checks.length || s.key === 'decide') ? (
            <Disclosure title="Technical details"><Technical stage={s} r={detail.result} /></Disclosure>
          ) : null}
        </div>
      </Panel>

      <Panel>
        <Disclosure title="Safeguards, privacy and limitations">
          <div className="spl">
            <div>
              <p className="reason-title">Safeguards</p>
              <ul className="plain">
                <li>Newsletters can only soften weak findings, never authentication failures.</li>
                <li>Quoted, described or ruled-out requests are not treated as requests.</li>
                <li>Missing information is marked unavailable; it never raises the risk.</li>
              </ul>
            </div>
            <div>
              <p className="reason-title">Privacy</p>
              <ul className="plain">
                <li>Emails go only to your own MailLens backend, which makes no outside calls.</li>
                <li>History keeps subject, sender and result for 30 days, never the body.</li>
                <li>Dashboard links work once and contain no credentials. No new Gmail permissions.</li>
              </ul>
            </div>
            <div>
              <p className="reason-title">Limitations</p>
              <ul className="plain">
                <li>A well-made attack from a new, authenticated sender can look clean.</li>
                <li>Attachment contents and text in images are not read; no reputation lookups.</li>
                <li>Requests are recognized in English only.</li>
              </ul>
            </div>
          </div>
        </Disclosure>
      </Panel>
    </>
  );
}

/** One genuine observation from the selected email for the current stage. */
function Observation({ stage, d }) {
  const r = d.result;
  let body;
  if (stage.key === 'examine') {
    body = <>Examined “{d.subject}” from {splitSender(d.sender).name}.</>;
  } else if (stage.key === 'decide') {
    body = <><VerdictBadge verdict={r.verdict} /> {r.decision_explanation}</>;
  } else if (stage.key === 'explain') {
    body = <>“{r.headline}”{r.actions[0] ? <> Next step: {r.actions[0].title}.</> : null}</>;
  } else {
    const f = r.findings.find((x) => stage.checks.includes(x.signal));
    body = f ? <><b>{f.title}.</b> {f.summary} <span className="basis">{BASIS[f.basis]}</span></> : 'No warning signs at this step.';
  }
  return <p className="observation"><span className="obs-label">This email</span>{body}</p>;
}

function Technical({ stage, r }) {
  if (stage.key === 'decide') {
    return <dl className="kv"><div><dt>Rule</dt><dd>{r.gate_explanation}</dd></div><div><dt>Evidence vector</dt><dd className="mono">{r.vector}</dd></div></dl>;
  }
  const checks = r.checks.filter((c) => stage.checks.includes(c.id));
  const found = [...r.findings, ...r.also_observed].filter((f) => stage.checks.includes(f.signal));
  return (
    <dl className="kv">
      {checks.map((c) => <div key={c.id}><dt>{c.label || c.name}</dt><dd>{c.state === 'ran' ? 'Ran' : c.state === 'unavailable' ? 'Unavailable' : 'Not applicable'}{c.note ? ` (${c.note})` : ''}</dd></div>)}
      {found.map((f, n) => <div key={n}><dt>{f.signal}</dt><dd>{f.title}, strength {f.level}/3</dd></div>)}
    </dl>
  );
}
