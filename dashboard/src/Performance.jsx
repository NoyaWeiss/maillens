import { useEffect, useState } from 'react';
import { api } from './api.js';
import { Panel, SectionHeader, Segmented, State } from './ui.jsx';

const pct = (x) => `${Math.round(x * 1000) / 10}%`;
const ciTitle = (c) => (c ? `95% confidence interval ${pct(c[0])}–${pct(c[1])}` : undefined);

export default function Performance() {
  const [state, setState] = useState({ status: 'loading' });
  useEffect(() => {
    api.evaluation().then((d) => setState({ status: 'ready', d })).catch((e) => setState({ status: 'error', message: e.message }));
  }, []);
  const d = state.d;
  const n = d ? { mal: d.overall.TP + d.overall.FN, leg: d.overall.FP + d.overall.TN } : null;
  return (
    <>
      <SectionHeader title="Detection Performance"
        subtitle={n ? `How MailLens performs on ${n.mal + n.leg} synthetic emails: ${n.mal} malicious and ${n.leg} legitimate.` : 'How MailLens performs on its synthetic benchmark.'} />
      {state.status === 'loading' ? <Panel><State kind="loading" title="Loading results…" /></Panel> : null}
      {state.status === 'error' ? <Panel><State kind="error" title="Results unavailable">{state.message}</State></Panel> : null}
      {state.status === 'ready' ? <Body d={d} n={n} /> : null}
    </>
  );
}

/** Five representative attack categories: two strongest, one middle, two weakest. */
function representative(cats) {
  const sorted = [...cats].sort((a, b) => b.alerts / b.n - a.alerts / a.n || a.name.localeCompare(b.name));
  if (sorted.length <= 5) return sorted;
  const mid = Math.floor(sorted.length / 2);
  return [sorted[0], sorted[1], sorted[mid], sorted[sorted.length - 2], sorted[sorted.length - 1]];
}

function Body({ d, n }) {
  const o = d.overall;
  const [view, setView] = useState('attack');
  const [all, setAll] = useState(false);
  const mal = d.by_category.filter((c) => c.label === 'Malicious');
  const leg = d.by_category.filter((c) => c.label === 'Legitimate');
  const fpCats = leg.filter((c) => c.alerts > 0);

  let shown;
  if (view === 'attack') shown = all ? [...mal].sort((a, b) => b.alerts / b.n - a.alerts / a.n || a.name.localeCompare(b.name)) : representative(mal);
  else shown = all ? [...leg].sort((a, b) => b.alerts - a.alerts || a.name.localeCompare(b.name)) : fpCats;
  const total = view === 'attack' ? mal.length : leg.length;

  return (
    <>
      <div className="metrics">
        <Metric name="Precision" value={pct(o.precision)} help="Alerts that were real attacks" title={ciTitle(o.precision_ci95)} />
        <Metric name="Recall" value={pct(o.recall)} help="Attacks that were caught" title={ciTitle(o.recall_ci95)} />
        <Metric name="F1 score" value={o.f1.toFixed(2)} help="Balance of precision and recall" />
        <Metric name="False positive rate" value={pct(o.fpr)} help="Legitimate emails wrongly flagged" title={ciTitle(o.fpr_ci95)} />
      </div>

      <div className="perf-grid">
        <Panel title="Confusion matrix">
          <div className="matrix" role="table" aria-label="Confusion matrix">
            <div role="row" className="m-row m-head"><span role="columnheader" /><span role="columnheader">Flagged</span><span role="columnheader">Not flagged</span></div>
            <div role="row" className="m-row"><span role="rowheader">Malicious</span>
              <Cell n={o.TP} label="Caught" tone="good" /><Cell n={o.FN} label="Missed" tone="bad" /></div>
            <div role="row" className="m-row"><span role="rowheader">Legitimate</span>
              <Cell n={o.FP} label="False alarms" tone="bad" /><Cell n={o.TN} label="Correctly cleared" tone="good" /></div>
          </div>
        </Panel>
        <Panel title="What this means">
          <div className="meaning">
            <p>Of the {n.mal} malicious emails, MailLens flagged <b>{o.TP}</b> and missed <b>{o.FN}</b>.</p>
            <p>Of the {n.leg} legitimate emails, it correctly cleared <b>{o.TN}</b> and raised <b>{o.FP}</b> false {o.FP === 1 ? 'alarm' : 'alarms'}.</p>
            <p className="meaning-takeaway">When MailLens raises an alert, it is almost always a real attack. The trade-off is that
              {' '}{o.FN / n.mal >= 0.3 ? `about ${Math.round((10 * o.FN) / n.mal)} in 10` : `${o.FN} of ${n.mal}`} attacks in this benchmark pass without an alert.</p>
          </div>
        </Panel>
      </div>

      <Panel title="By category" aside={
        <Segmented label="Category type" value={view} onChange={(v) => { setView(v); setAll(false); }}
          options={[{ value: 'attack', label: 'Attacks' }, { value: 'legit', label: 'Legitimate' }]} />}>
        {shown.length ? (
          <ul className="cat-list">
            {shown.map((c) => {
              const rate = c.alerts / c.n;
              const tone = view === 'attack' ? (rate === 1 ? 'good' : rate === 0 ? 'bad' : 'mid') : (c.alerts ? 'bad' : 'good');
              return (
                <li key={c.name} className="cat">
                  <span className="cat-name">{c.name}</span>
                  <span className="cat-bar" aria-hidden="true"><span className={`cat-fill fill-${tone}`} style={{ width: `${Math.max(rate * 100, 2)}%` }} /></span>
                  <span className="cat-num">{c.alerts}/{c.n} {view === 'attack' ? 'caught' : 'flagged'}</span>
                </li>
              );
            })}
          </ul>
        ) : <p className="muted">No legitimate category had a false alarm.</p>}
        <div className="cat-foot">
          <p className="muted small">{view === 'attack'
            ? (all ? `All ${total} attack types.` : 'Five representative attack types: strongest, middle and weakest.')
            : (all ? `All ${total} legitimate types.` : `Only the ${fpCats.length} legitimate types with false alarms.`)}</p>
          <button type="button" className="btn btn-ghost" onClick={() => setAll(!all)} aria-expanded={all}>{all ? 'Show fewer' : `View all ${total}`}</button>
        </div>
      </Panel>

      <p className="method-note">Results are based on {n.mal + n.leg} balanced synthetic emails. Category samples are small, and performance may differ on real-world email.</p>
    </>
  );
}

function Metric({ name, value, help, title }) {
  return (
    <div className="metric" title={title}>
      <span className="metric-name">{name}</span>
      <span className="metric-value">{value}</span>
      <span className="metric-help">{help}</span>
    </div>
  );
}

function Cell({ n, label, tone }) {
  return <span role="cell" className={`m-cell m-${tone}`}><b>{n}</b><span>{label}</span></span>;
}
