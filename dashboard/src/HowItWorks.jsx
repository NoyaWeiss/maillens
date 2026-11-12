import { useState } from 'react';
import { Disclosure, Panel, SectionHeader, VerdictBadge } from './ui.jsx';

// Written from the implementation: backend/app/engine.py (checks S1-S14), signals/*, decision.py, presentation.py.
const STAGES = [
  { key: 'examine', title: 'Examine', text: [
    'When you open an email, the Gmail add-on collects its headers (sender, reply address, Google’s authentication result), subject, text, links and attachment names and types. Attachments themselves are never opened.',
    'With your permission, it also summarizes who you have emailed in the last 180 days and the earlier messages in the thread.',
    'Everything is sent only to your own MailLens backend. If a piece of information is missing, the related checks are marked unavailable instead of guessed.',
  ] },
  { key: 'identity', title: 'Identity', text: [
    'MailLens reads Google’s SPF, DKIM and DMARC result to see whether the sending domain is authentic.',
    'It looks for look-alike domains (for example a digit swapped for a letter), display names that claim a different company or address, reply addresses that send your answer somewhere else, and names that match a contact but come from a new address.',
    'Impersonation is behind most payment and credential fraud, so a deliberate look-alike domain is strong enough on its own for High risk.',
  ] },
  { key: 'relationship', title: 'Relationship', text: [
    'MailLens compares the sender with people and domains you have emailed recently, and checks whether the thread’s earlier messages came from the same sender with the same reply address.',
    'A first-time sender is one of the corroborating signs that can lift a risky request to High risk, and a known contact sharing a file through an unrelated site is treated as suspicious.',
    'Without mailbox access the sender is treated as unknown, never as unfamiliar, so missing history can’t make an email look riskier.',
  ] },
  { key: 'content', title: 'Content', text: [
    'MailLens checks whether link text and link destinations disagree, whether URLs are built to deceive (such as hidden real domains or shorteners), whether attachment types are risky, and whether hidden text targets security scanners.',
    'These are concrete, observable tricks, so they count as evidence rather than suspicion.',
    'Newsletters and other bulk mail can only soften weak findings here; they never hide authentication failures.',
  ] },
  { key: 'request', title: 'Request', text: [
    'MailLens recognizes requests for sensitive actions: changing payment details, wiring money, buying gift cards, entering a password or code, approving a sign-in, sharing data, installing software or calling a number.',
    'It also notes pressure and secrecy wording. Requests that are quoted, described or ruled out (as in a security warning) do not count.',
    'A request alone is not proof of an attack, but combined with an unfamiliar sender or another warning sign it becomes a strong signal.',
  ] },
  { key: 'decide', title: 'Decision', text: [
    'Each thing examined (the sender, a domain, a link) counts once, at its strongest finding, and findings are never added up. That stops one problem from being counted several times.',
    'Fixed, ordered rules then choose the verdict. High needs strong deception, or a risky request backed by independent evidence. Suspicious covers a single strong warning sign, a high-impact request such as new bank details, or a sensitive request in a suspicious context. Inconclusive is used when authentication data is missing for an otherwise risky email. Everything else is Low.',
    'The risk index (0–100) shows where an email sits within its verdict; it is not a probability.',
  ], verdicts: true },
  { key: 'explain', title: 'Explanation', text: [
    'The decision becomes a one-sentence summary, a short list of reasons in plain English, and practical next steps.',
    'Each reason is labelled as seen in the email, taken from your email history, or based on the wording, so facts are kept apart from inferences.',
    'Any limitation that affects this particular email, such as an unopened attachment or missing mailbox access, is shown with the result.',
  ] },
];

export default function HowItWorks() {
  const [stage, setStage] = useState('identity');
  const i = STAGES.findIndex((x) => x.key === stage);
  const s = STAGES[i];
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
          <h2>{i + 1}. {s.title}</h2>
          {s.text.map((t, n) => <p key={n} className="stage-text">{t}</p>)}
          {s.verdicts ? (
            <div className="verdict-row" aria-hidden="true">
              <VerdictBadge verdict="HIGH" /><VerdictBadge verdict="SUSPICIOUS" /><VerdictBadge verdict="INCONCLUSIVE" /><VerdictBadge verdict="LOW" />
            </div>
          ) : null}
        </div>
      </Panel>

      <Panel>
        <Disclosure title="Safeguards, privacy and limitations">
          <div className="spl">
            <div>
              <p className="reason-title">Safeguards</p>
              <ul className="plain">
                <li>Bulk mail can only soften weak findings, never authentication failures.</li>
                <li>Quoted, described or ruled-out requests are not treated as requests.</li>
                <li>Missing information is marked unavailable; it never raises the risk.</li>
              </ul>
            </div>
            <div>
              <p className="reason-title">Privacy</p>
              <ul className="plain">
                <li>Emails go only to your own MailLens backend, which makes no outside calls.</li>
                <li>History keeps subject, sender and result for up to a year, never the body; you can clear it anytime.</li>
                <li>Dashboard links work once and contain no credentials. No extra Gmail permissions.</li>
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
