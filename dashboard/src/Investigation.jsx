import { useEffect, useMemo, useState } from 'react';
import { BASIS, Disclosure, Panel, RiskIndex, SectionHeader, State, VERDICTS, VERDICT_ORDER, VerdictBadge, fmtTime, splitSender, timeAgo } from './ui.jsx';

export default function Investigation({ source, selected, onSelect }) {
  const { emails = [], now, mode } = source;
  const [query, setQuery] = useState('');
  const [verdict, setVerdict] = useState('ALL');
  const [detail, setDetail] = useState({ status: 'idle' });

  const list = useMemo(() => emails.filter((e) =>
    (verdict === 'ALL' || e.verdict === verdict) &&
    (!query || `${e.subject} ${e.sender}`.toLowerCase().includes(query.toLowerCase()))), [emails, query, verdict]);
  const id = selected || emails[0]?.id;

  useEffect(() => {
    if (!id || mode === 'none') { setDetail({ status: 'idle' }); return undefined; }
    let live = true;
    setDetail({ status: 'loading' });
    source.loadDetail(id).then((d) => live && setDetail({ status: 'ready', data: d }))
      .catch((err) => live && setDetail({ status: 'error', message: err.status === 404 ? 'This email is no longer in your history.' : err.message }));
    return () => { live = false; };
  }, [id, mode, source]);

  return (
    <>
      <SectionHeader title="Examine an Email" subtitle="Understand why an email was flagged and explore the evidence behind the decision." />
      {mode === 'none' ? (
        <Panel><State title="No account connected">Open the dashboard from MailLens in Gmail to examine your own analyzed emails, or explore Demo Mode.</State></Panel>
      ) : !emails.length ? (
        <Panel><State title="No analyzed emails yet">Open an email in Gmail with MailLens; it will be available to examine here.</State></Panel>
      ) : (
        <div className="investigate">
          <aside className="panel picker" aria-label="Analyzed emails">
            <p className="picker-note">{mode === 'demo'
              ? 'Synthetic demo emails, not your mailbox.'
              : `Only emails MailLens has analyzed in this account (last 30 days) are listed, not your whole inbox.`}</p>
            <input type="search" className="input" placeholder="Search subject or sender" value={query}
              onChange={(e) => setQuery(e.target.value)} aria-label="Search analyzed emails" />
            <div className="chips" role="group" aria-label="Filter by verdict">
              {['ALL', ...VERDICT_ORDER].map((v) => (
                <button key={v} type="button" aria-pressed={verdict === v} className={`chip ${verdict === v ? 'active' : ''}`}
                  onClick={() => setVerdict(v)}>{v === 'ALL' ? 'All' : VERDICTS[v].label}</button>
              ))}
            </div>
            <ul className="picker-list">
              {list.map((e) => (
                <li key={e.id}>
                  <button type="button" className={`picker-item ${e.id === id ? 'selected' : ''}`} aria-current={e.id === id ? 'true' : undefined}
                    onClick={() => onSelect(e.id)}>
                    <span className="picker-top"><VerdictBadge verdict={e.verdict} size="sm" /><span className="muted small">{timeAgo(e.analyzed_at, now)}</span></span>
                    <span className="email-subject">{e.subject}</span>
                    <span className="muted small ellipsis">{splitSender(e.sender).name}</span>
                  </button>
                </li>
              ))}
              {!list.length ? <li className="muted small pad">No emails match.</li> : null}
            </ul>
          </aside>
          <div className="case">
            {detail.status === 'loading' ? <Panel><State kind="loading" title="Loading analysis…" /></Panel> : null}
            {detail.status === 'error' ? <Panel><State kind="error" title="Couldn't load this analysis">{detail.message}</State></Panel> : null}
            {detail.status === 'ready' ? <Case data={detail.data} /> : null}
          </div>
        </div>
      )}
    </>
  );
}

function Case({ data }) {
  const r = data.result;
  const sender = splitSender(data.sender);
  const facts = r.findings.filter((f) => f.basis !== 'HEURISTIC');
  const wording = r.findings.filter((f) => f.basis === 'HEURISTIC');
  const req = r.request && r.request.level >= 2 ? r.request : null;
  const reqReason = (r.reasons || []).find((x) => x.basis === 'Based on the wording');
  const by = (s) => r.checks.filter((c) => c.state === s);

  return (
    <>
      <Panel className={`case-head tone-${(VERDICTS[r.verdict] || {}).tone}`}>
        <div className="case-title">
          <div>
            <p className="eyebrow">{r.category}</p>
            <h2 className="case-subject">{data.subject}</h2>
            <p className="muted small">{sender.name} · <span className="mono">{sender.address}</span> · analyzed {fmtTime(data.analyzed_at)}</p>
          </div>
          <div className="case-verdict">
            <VerdictBadge verdict={r.verdict} size="lg" />
            <RiskIndex score={r.score} verdict={r.verdict} />
          </div>
        </div>
        <p className="case-headline">{r.headline}</p>
        <p className="muted small">{r.decision_explanation}</p>
      </Panel>

      <div className="case-grid">
        <Panel title="What MailLens observed" subtitle="Facts checked in the email and your email history.">
          {facts.length ? (
            <ul className="evidence">
              {facts.map((f, i) => (
                <li key={i}>
                  <span className="tag tag-fact">{BASIS[f.basis]}</span>
                  <p className="ev-title">{f.title}</p>
                  <p className="muted small">{f.summary}</p>
                </li>
              ))}
            </ul>
          ) : <p className="muted">Nothing contradicted what the email claims.</p>}
        </Panel>

        <Panel title="What it may indicate" subtitle="Suspected risk inferred from the facts and the wording.">
          {r.verdict === 'LOW' && !req && !wording.length ? <p className="muted">No suspected threat was identified.</p> : (
            <ul className="evidence">
              {r.archetype && r.verdict !== 'LOW' ? <li><span className="tag tag-inferred">Suspected</span><p className="ev-title">{r.archetype}</p>
                {r.impact ? <p className="muted small">{r.impact}</p> : null}</li> : null}
              {req ? <li><span className="tag tag-inferred">Based on the wording</span><p className="ev-title">{reqReason ? reqReason.title : req.label}</p>
                {req.excerpt ? <blockquote className="quote">“{req.excerpt}”</blockquote> : null}</li> : null}
              {wording.map((f, i) => <li key={i}><span className="tag tag-inferred">Based on the wording</span><p className="ev-title">{f.title}</p><p className="muted small">{f.summary}</p></li>)}
              {r.pressure_cues.length ? <li><span className="tag tag-inferred">Pressure</span><p className="muted small">{r.pressure_cues.join(' · ')}</p></li> : null}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Recommended actions">
        {r.actions.length ? (
          <ul className="actions">{r.actions.map((a, i) => <li key={i}><p className="ev-title">{a.title}</p><p className="muted small">{a.detail}</p></li>)}</ul>
        ) : <p className="muted">No specific action is needed.</p>}
        {r.verdict === 'LOW' ? <p className="note">Low risk is not a guarantee that an email is safe. If a request seems unusual, confirm it through a channel you already trust.</p> : null}
        {r.limitations && r.limitations.length ? (
          <div className="note note-warn"><p className="ev-title">What may affect this result</p><ul>{r.limitations.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
        ) : null}
      </Panel>

      <Panel>
        <Disclosure title="Technical evidence" hint="Values behind each finding and the decision path">
          {r.findings.length ? r.findings.map((f, i) => (
            <div key={i} className="tech-block">
              <p className="ev-title">{f.title} <span className="muted small">· {BASIS[f.basis]} · strength {f.level}/3</span></p>
              <dl className="kv">
                {(f.details || []).map((d, j) => <div key={j}><dt>{d.label}</dt><dd className="mono">{d.value}</dd></div>)}
                {!(f.details || []).length ? <><div><dt>Claim</dt><dd>{f.claim}</dd></div><div><dt>Reality</dt><dd>{f.reality}</dd></div></> : null}
              </dl>
            </div>
          )) : <p className="muted small">No findings.</p>}
          {r.also_observed.length ? <p className="muted small">Also noticed (counted once, not added): {r.also_observed.map((a) => a.title).join(', ')}</p> : null}
          <dl className="kv decision-kv">
            <div><dt>Decision rule</dt><dd>{r.gate_explanation}</dd></div>
            <div><dt>Evidence vector</dt><dd className="mono">{r.vector}</dd></div>
          </dl>
          {r.safeguards.length ? <><p className="ev-title">False-alarm safeguards applied</p><ul className="plain">{r.safeguards.map((s, i) => <li key={i}>{s}</li>)}</ul></> : null}
        </Disclosure>
        <Disclosure title="Analysis coverage" hint={`${by('ran').length} completed · ${by('not_applicable').length} not applicable · ${by('unavailable').length} unavailable`}>
          <div className="coverage">
            {[['ran', 'Completed'], ['not_applicable', 'Not applicable'], ['unavailable', 'Unavailable']].map(([s, label]) => (
              <div key={s}>
                <p className="ev-title">{label}</p>
                <ul className="plain">{by(s).length ? by(s).map((c) => <li key={c.id}>{c.label || c.name}{c.note ? <span className="muted"> ({c.note})</span> : null}</li>) : <li className="muted">None</li>}</ul>
              </div>
            ))}
          </div>
          <p className="muted small">Completed checks show what was examined, not how certain the verdict is.</p>
        </Disclosure>
      </Panel>
    </>
  );
}
