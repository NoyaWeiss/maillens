import { useEffect, useState } from 'react';
import { api } from './api.js';
import { Disclosure, Panel, SectionHeader, Segmented, State } from './ui.jsx';

// Why specific attack types are missed (from docs/EVALUATION_REPORT.md); shown only if the category is a miss.
const MISS_REASON = {
  'crypto wallet drainer': '"Connect your wallet" is not one of the recognized sensitive actions.',
  'voicemail notification lure': "The sign-in link points to the sender's own new domain, so there's no independent warning sign.",
  'fake legal / compliance threat': '"Review the evidence" and "download the filing" are not recognized actions.',
};

const pct = (x) => `${Math.round(x * 1000) / 10}%`;
const ci = (c) => (c ? `95% CI ${pct(c[0])}–${pct(c[1])}` : '');

export default function Performance() {
  const [state, setState] = useState({ status: 'loading' });
  const [view, setView] = useState('Malicious');
  useEffect(() => {
    api.evaluation().then((d) => setState({ status: 'ready', d })).catch((e) => setState({ status: 'error', message: e.message }));
  }, []);

  return (
    <>
      <SectionHeader title="Verified Evaluation" subtitle="How accurately MailLens detects threats in our latest synthetic benchmark." />
      {state.status === 'loading' ? <Panel><State kind="loading" title="Loading evaluation results…" /></Panel> : null}
      {state.status === 'error' ? <Panel><State kind="error" title="Evaluation results unavailable">{state.message}</State></Panel> : null}
      {state.status === 'ready' ? <Body d={state.d} view={view} setView={setView} /> : null}
    </>
  );
}

function Body({ d, view, setView }) {
  const o = d.overall;
  const nMal = o.TP + o.FN, nLeg = o.FP + o.TN;
  const cats = d.by_category.filter((c) => c.label === view).sort((a, b) => (view === 'Malicious' ? b.alerts / b.n - a.alerts / a.n : a.alerts / a.n - b.alerts / b.n) || a.name.localeCompare(b.name));
  const mal = d.by_category.filter((c) => c.label === 'Malicious');
  const strong = mal.filter((c) => c.alerts === c.n);
  const missed = mal.filter((c) => c.alerts === 0);
  const fps = d.by_category.filter((c) => c.label === 'Legitimate' && c.alerts > 0);

  return (
    <>
      <div className="bench-banner">
        <span className="pill">Benchmark {d.benchmark}</span>
        <span>Synthetic · balanced · {nMal + nLeg} emails ({nMal} malicious, {nLeg} legitimate) · engine <span className="mono">{d.engine}</span></span>
      </div>

      <div className="metrics">
        <Metric name="Precision" value={pct(o.precision)} help="When MailLens raises an alert, how often it's a real attack." sub={ci(o.precision_ci95)} />
        <Metric name="Recall" value={pct(o.recall)} help="Share of attacks MailLens caught." sub={ci(o.recall_ci95)} />
        <Metric name="F1 score" value={o.f1.toFixed(3)} help="Balance of precision and recall (0–1)." />
        <Metric name="False positive rate" value={pct(o.fpr)} help="Share of legitimate emails wrongly flagged." sub={ci(o.fpr_ci95)} />
      </div>

      <div className="perf-grid">
        <Panel title="Confusion matrix" subtitle="Alert = Suspicious or High risk. Inconclusive counts as no alert.">
          <div className="matrix" role="table" aria-label="Confusion matrix">
            <div role="row" className="m-row m-head"><span role="columnheader" /><span role="columnheader">Alert raised</span><span role="columnheader">No alert</span></div>
            <div role="row" className="m-row"><span role="rowheader">Malicious ({nMal})</span>
              <Cell n={o.TP} label="Attacks caught" code="TP" tone="good" /><Cell n={o.FN} label="Attacks missed" code="FN" tone="bad" /></div>
            <div role="row" className="m-row"><span role="rowheader">Legitimate ({nLeg})</span>
              <Cell n={o.FP} label="False alarms" code="FP" tone="bad" /><Cell n={o.TN} label="Correctly cleared" code="TN" tone="good" /></div>
          </div>
        </Panel>
        <Panel title="Strengths and gaps" subtitle="Attack types caught every time, and those never caught.">
          <p className="ev-title">Caught in every case ({strong.length})</p>
          <p className="muted small">{strong.map((c) => c.name).join(' · ') || 'None'}</p>
          <p className="ev-title gap-top">Never caught ({missed.length})</p>
          <ul className="plain">{missed.map((c) => <li key={c.name}>{c.name}{MISS_REASON[c.name] ? <span className="muted small"> — {MISS_REASON[c.name]}</span> : null}</li>)}</ul>
          <p className="ev-title gap-top">False alarms ({o.FP})</p>
          <p className="muted small">{fps.map((c) => `${c.name} (${c.alerts}/${c.n})`).join(' · ') || 'None'}</p>
        </Panel>
      </div>

      <Panel title="Detection by category" subtitle={view === 'Malicious' ? 'Share of attacks caught in each attack type (n = cases).' : 'Share of legitimate emails wrongly flagged in each type (n = cases).'}
        aside={<Segmented label="Category type" value={view} onChange={setView} options={[{ value: 'Malicious', label: 'Attack types' }, { value: 'Legitimate', label: 'Legitimate look-alikes' }]} />}>
        <ul className="cat-list">
          {cats.map((c) => {
            const rate = c.alerts / c.n;
            const tone = view === 'Malicious' ? (rate === 1 ? 'good' : rate === 0 ? 'bad' : 'mid') : (c.alerts ? 'bad' : 'good');
            return (
              <li key={c.name} className="cat">
                <span className="cat-name">{c.name}</span>
                <span className="cat-bar" aria-hidden="true"><span className={`cat-fill fill-${tone}`} style={{ width: `${Math.max(rate * 100, 1.5)}%` }} /></span>
                <span className="cat-num">{c.alerts}/{c.n}</span>
              </li>
            );
          })}
        </ul>
        <p className="muted small">Each category has only {Math.min(...cats.map((c) => c.n))}–{Math.max(...cats.map((c) => c.n))} cases, so per-category rates are indicative, not precise.</p>
      </Panel>

      <Panel>
        <Disclosure title="What these numbers mean" hint="Read before quoting them">
          <ul className="plain">
            <li><b>Synthetic and balanced.</b> Half of the benchmark is malicious; real mail is mostly benign, so real-world precision at this false-positive rate would be lower.</li>
            <li><b>Small samples.</b> {nMal + nLeg} emails in total and 5 per category; see the confidence intervals above.</li>
            <li><b>Possible design bias.</b> The same author wrote the engine and the benchmark. The engine was frozen before the benchmark was written, which limits but doesn't remove this bias.</li>
            <li><b>Benchmark, not field results.</b> These figures describe this dataset only. They are not a measurement of real-world detection.</li>
          </ul>
        </Disclosure>
        <Disclosure title="By difficulty" hint="Attacks caught per difficulty level">
          <ul className="plain">{d.by_difficulty.filter((x) => x.label === 'Malicious').map((x) => <li key={x.name}>{x.name}: {x.alerts}/{x.n} caught</li>)}</ul>
        </Disclosure>
        <Disclosure title="Earlier benchmarks" hint="Documented history, not directly comparable">
          <p className="muted small">Each earlier benchmark used a different dataset and was later used to develop the engine, so its numbers can't be compared with this one. Full reports are in <span className="mono">docs/</span>.</p>
          <ul className="plain">{d.history.map((h) => <li key={h.benchmark}><b>{h.benchmark}</b> · {h.label}</li>)}</ul>
          {Object.entries(d.baseline || {}).filter(([k]) => k.startsWith('baseline')).map(([k, b]) => (
            <p key={k} className="muted small">Same benchmark, previous engine (<span className="mono">{k.split('_')[1]}</span>): recall {pct(b.recall)}, false-positive rate {pct(b.fpr)}.</p>
          ))}
        </Disclosure>
      </Panel>
    </>
  );
}

function Metric({ name, value, help, sub }) {
  return (
    <div className="metric">
      <span className="metric-name">{name}</span>
      <span className="metric-value">{value}</span>
      <span className="muted small">{help}</span>
      {sub ? <span className="metric-ci">{sub}</span> : null}
    </div>
  );
}

function Cell({ n, label, code, tone }) {
  return <span role="cell" className={`m-cell m-${tone}`}><b>{n}</b><span>{label}</span><span className="m-code">{code}</span></span>;
}
