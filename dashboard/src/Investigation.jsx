import { useEffect, useState } from 'react';
import { BASIS, Disclosure, Panel, RiskIndex, State, VERDICTS, VerdictBadge, fmtDate, splitSender } from './ui.jsx';

// Selected email inside Overview: Assessment -> Why -> What to do. Everything comes from the stored analysis.
const WHY_TITLE = {
  HIGH: 'Why was it flagged?',
  SUSPICIOUS: 'Why was it flagged?',
  INCONCLUSIVE: "Why can't MailLens be sure?",
  LOW: 'What did MailLens find?',
};

export default function EmailAssessment({ id, source, onBack }) {
  const [state, setState] = useState({ status: 'loading' });
  useEffect(() => {
    let live = true;
    setState({ status: 'loading' });
    source.loadDetail(id).then((d) => live && setState({ status: 'ready', d }))
      .catch((e) => live && setState({ status: 'error', message: e.status === 404 ? 'This email is not in your history.' : e.message }));
    return () => { live = false; };
  }, [id, source]);

  return (
    <>
      <button type="button" className="back" onClick={onBack}><span aria-hidden="true">←</span> All emails</button>
      {state.status === 'loading' ? <Panel><State kind="loading" title="Loading assessment…" /></Panel> : null}
      {state.status === 'error' ? <Panel><State kind="error" title="Couldn't open this email">{state.message}</State></Panel> : null}
      {state.status === 'ready' ? <Assessment d={state.d} /> : null}
    </>
  );
}

function Assessment({ d }) {
  const r = d.result;
  const s = splitSender(d.sender);
  const tone = (VERDICTS[r.verdict] || {}).tone;

  // Up to three plain-English reasons: strongest findings first, then the request wording if any.
  const reasons = r.findings.map((f) => ({ title: f.title, text: f.summary, basis: BASIS[f.basis] }));
  const req = r.request && r.request.level >= 2 ? r.request : null;
  if (req) {
    const rr = (r.reasons || []).find((x) => x.basis === 'Based on the wording');
    reasons.push({ title: rr ? rr.title : req.label, text: rr ? rr.summary : '', quote: req.excerpt, basis: 'Based on the wording' });
  }
  const top = reasons.slice(0, 3);

  return (
    <>
      <Panel className={`assess tone-${tone}`}>
        <h1 className="eyebrow">Email assessment</h1>
        <div className="assess-top">
          <VerdictBadge verdict={r.verdict} size="lg" />
          <RiskIndex score={r.score} verdict={r.verdict} />
        </div>
        <h2 className="assess-subject">{d.subject}</h2>
        <p className="assess-sender">{s.name}{s.address && s.address !== s.name ? <span className="mono"> · {s.address}</span> : null}
          <span className="muted"> · {fmtDate(d.received_at || d.analyzed_at)}</span></p>
        <p className="assess-headline">{r.headline}</p>
      </Panel>

      <Panel title={WHY_TITLE[r.verdict]}>
        {top.length ? (
          <ol className="reasons">
            {top.map((x, i) => (
              <li key={i}>
                <p className="reason-title">{x.title}</p>
                {x.text ? <p className="reason-text">{x.text}</p> : null}
                {x.quote ? <blockquote className="quote">“{x.quote}”</blockquote> : null}
                <span className="basis">{x.basis}</span>
              </li>
            ))}
          </ol>
        ) : <p className="reason-text">Nothing in this email contradicted what it claims to be.</p>}
        {r.limitations && r.limitations.length ? <p className="caveat">{r.limitations.join(' ')}</p> : null}
        <Disclosure title="View technical evidence">
          <TechnicalEvidence r={r} />
        </Disclosure>
      </Panel>

      <Panel title="What should I do?">
        {r.actions.length ? (
          <ul className="todo">{r.actions.map((a, i) => <li key={i}><p className="reason-title">{a.title}</p><p className="reason-text">{a.detail}</p></li>)}</ul>
        ) : <p className="reason-text">No action is needed.</p>}
        {r.verdict === 'LOW' ? <p className="caveat">Low risk isn&apos;t a guarantee. If a request seems unusual, confirm it through a channel you already trust.</p> : null}
      </Panel>
    </>
  );
}

function TechnicalEvidence({ r }) {
  const ran = r.checks.filter((c) => c.state === 'ran').length;
  return (
    <div className="tech">
      {r.findings.map((f, i) => (
        <div key={i} className="tech-block">
          <p className="reason-title">{f.title} <span className="muted">· strength {f.level}/3</span></p>
          <dl className="kv">
            {(f.details || []).map((x, j) => <div key={j}><dt>{x.label}</dt><dd className="mono">{x.value}</dd></div>)}
            {!(f.details || []).length ? <><div><dt>Claim</dt><dd>{f.claim}</dd></div><div><dt>Reality</dt><dd>{f.reality}</dd></div></> : null}
          </dl>
        </div>
      ))}
      {r.findings.length > 3 ? <p className="muted">Showing all {r.findings.length} findings; the summary above lists the top three.</p> : null}
      <dl className="kv">
        {r.also_observed.length ? <div><dt>Also noticed</dt><dd>{r.also_observed.map((a) => a.title).join(', ')} (counted once)</dd></div> : null}
        <div><dt>Decision rule</dt><dd>{r.gate_explanation}</dd></div>
        <div><dt>Checks</dt><dd>{ran} of {r.checks.length} ran{r.checks.filter((c) => c.state === 'unavailable').map((c) => `; ${c.label || c.name} unavailable`).join('')}</dd></div>
        {r.safeguards.length ? <div><dt>Safeguards applied</dt><dd>{r.safeguards.join(' ')}</dd></div> : null}
      </dl>
    </div>
  );
}
