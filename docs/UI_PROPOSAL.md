# Phase 2: card redesign proposal, v3 (information architecture)

Status: **v3 main card implemented and APPROVED by the owner in real Gmail (2026-11-11); preserve it.**
Detailed analysis and Welcome screens: proposal v4 below, awaiting approval.

Previous status: proposal v3, awaiting owner approval of the structure. The v1 card (commit `3ba2f43`)
and the v2 proposal were not approved. Phase 2 closes only when the owner approves both this
hierarchy and the actual result in Hebrew-language Gmail.

Owner decisions so far:
- **Variant C** (LRI … PDI isolation, U+2066 / U+2069) for English and mixed-direction text, chosen
  from the real Hebrew-Gmail direction test. That test also shows Gmail preserves these characters
  (C rendered differently from the plain variant A).
- **Option 1:** the backend's template layer (`narrative.py`) produces all presentation text.
  Presentation only: verdicts, scores, gates and vectors must not change (regression-tested).

## Main card: fixed hierarchy, headings adapted per verdict

| # | Block | High | Suspicious | Inconclusive | Low |
|---|---|---|---|---|---|
| 1 | Assessment | **Risk assessment** | **Risk assessment** | **Risk assessment** | **Risk assessment** |
| 2 | Reasons (≤2) | **Why this email is suspicious** | **Why this needs a second look** | **Why we can't be sure** | (omitted) |
| 3 | Consequence | **What could happen?** | **What could happen?** | **What could happen?** | (omitted) |
| 4 | Action (1, optional 2nd) | **What should you do?** | **What should you do?** | **What should you do?** | **Before you act** (only if the email asks for something) |
| 5 | Detail | [View detailed analysis] · Re-analyze | same | same | same |

Each block is its own CardSection. Its heading is a **bold line** (a guaranteed-bold text widget;
the native section-header style is small and grey). Every reason and action is one row: an
**icon + bold title** with one short neutral sentence directly below, and for reasons a small grey
evidence-type tag.

### High risk (T5)

```
 Risk assessment
 ⛔ High risk · 75/100
    ▰▰▰▰▰▰▰▰▱▱
    Likely vendor account takeover
 A reply in a vendor thread asks you to
 send money to new bank details.

 Why this email is suspicious
 ↩  Reply address changed
    Replies now go to a different address
    than earlier messages in this thread.
    Seen in this email
 🏦 Asks to change bank details
    It asks you to pay a new account.
    Based on the wording

 What could happen?
 If this is fraud, a payment could go to the
 attacker and is usually not recoverable.

 What should you do?
 ☎  Verify with the vendor
    Call a number you already trust before
    changing any payment details.
 ✋ Don't reply to this email
    Replies may reach the attacker.

 [ View detailed analysis ]   Re-analyze
```

### Suspicious (T6)

```
 Risk assessment
 ⚠  Suspicious · 40/100
    ▰▰▰▰▱▱▱▱▱▱
    Possible payment redirection
 A known sender asks for a payment change
 that is hard to undo.

 Why this needs a second look
 🏦 Asks to change bank details
    It asks you to pay a new account.
    Based on the wording
 👤 Sender is known to you
    Nothing else in the email looks wrong.
    From your email history

 What could happen?
 If the request is not genuine, payments
 could go to the wrong account.

 What should you do?
 ☎  Verify by phone
    Use contact details you already have,
    not ones in this email.

 [ View detailed analysis ]   Re-analyze
```

### Inconclusive (T9)

```
 Risk assessment
 ?  Inconclusive · no score
    Sender could not be verified
 We can't confirm who sent this, and it
 asks you to sign in.

 Why we can't be sure
 🔒 Sender can't be verified
    No authentication results were found.
    This is common for forwarded mail.
    Limited evidence
 🔑 Asks you to sign in
    It links to a sign-in page.
    Based on the wording

 What could happen?
 If this is phishing, a password entered on
 that page could be stolen.

 What should you do?
 ✓  Confirm with the sender
    Use a channel you already trust before
    signing in.

 [ View detailed analysis ]   Re-analyze
```

### Low risk (T2: asks you to sign in; T1/T3: asks nothing)

```
 Risk assessment
 ✓  Low risk · 8/100
    ▰▱▱▱▱▱▱▱▱▱
    12 checks ran
 Nothing in this email contradicts what it
 claims.

 Before you act                        ← T2 only; T1/T3 omit this block
 ↗  Go to the site directly
    Open the site yourself instead of using
    the link in the email.

 [ View detailed analysis ]   Re-analyze
```

### Error

```
 Analysis unavailable
 ⚠  No verdict
    MailLens couldn't analyze this email.
 The analysis service can't be reached.

 [ Try again ]
 Step: call backend
```

### Buttons

`FixedFooter` requires a FILLED primary button, which would make one button loud on every card.
Instead, block 5 is an in-card row at the end:
- **View detailed analysis**: FILLED_TONAL (clearly a button, not loud).
- **Re-analyze**: BORDERLESS (visually secondary).

## Detailed analysis (separate card)

```
 Detailed analysis                       title; subtitle "Request 1a2b3c"

 How the verdict was reached
 A strong finding together with an
 irreversible request makes this High.
 Rule H-B · Signals D2 · A3 · E1 · P0 · N0
 (legend, grey)

 Evidence
 Reply address changed
   Claimed: a reply in your thread with
   ⁦billing@acmesupply.example⁩
   Observed: replies go to
   ⁦acme.supply.accounts@gmail.example⁩
   S2 · strong · seen in this email
 Asks to change bank details
   Quote: "…wire the INV-2207 payment to
   our new account…"
   S13 · irreversible · based on the wording

 Coverage and confidence
 Full confidence · 10 of 10 applicable checks ran
 Not applicable: links, URL construction, attachments   (collapsed)

 Limits and assumptions                     (collapsed)
 Safeguards applied                         (collapsed: false-positive guards)
 Developer                                  (dev builds only: probe, direction test)
```
The separate Attack Story section is **removed**: its claim/observed lines are the Evidence
block, and its consequence is "What could happen?". `story` stays in the API for compatibility.

## Variant C: how it is applied

- One helper `ltr_(text)` returns `U+2066 + text + U+2069`. **Every** English string passes through
  it at render time, after HTML-escaping: headings, titles, explanations, labels, scores, bars,
  button text and technical lines.
- **Each line is isolated separately.** Where a widget has several lines (`<br>`), each line gets its
  own isolate, so no isolate spans a line break.
- Addresses, domains, scores and the signal vector inside technical lines get an **inner isolate**,
  so long tokens keep their internal order when they wrap.
- A unit test asserts that every string rendered into a card is isolated, and that none contains
  unsupported markup.

## Limitations that remain, and how the design copes

| Limitation | Effect in Hebrew Gmail | Design response |
|---|---|---|
| No alignment control | Text stays right-aligned; wrapped English lines are ragged on the left | Short lines: titles ≤ 5 words, explanations one short sentence, no paragraphs |
| No direction attribute | Card chrome (icons, button order, section order) mirrors to RTL | Icons sit on the right of rows, which is natural in RTL; meaning never depends on position |
| No font sizes | Hierarchy only via bold, regular and grey | Three levels used consistently: bold heading / bold title, neutral sentence, grey tag |
| Labels are plain text | No bold or colour in tags | Tags are short grey metadata only |
| Long tokens wrap anywhere | Addresses could break mid-word | No addresses on the main card; isolated in Detailed analysis |

## Presentation content (Option 1, backend)

New response fields, generated by `narrative.py` from the existing decision; no detection change:
- `assessment`: `{category}` hedged ("Likely …" for High, "Possible …" for Suspicious, a reason phrase
  for Inconclusive, the checks-ran line for Low).
- `reasons`: ≤2 items `{title, summary, basis}`. Ordered: strongest finding, then the request or
  context (e.g. "Sender is known to you", "Sender can't be verified").
- `impact`: one cautious sentence ("could", "if this is …"), or empty for Low.
- `actions`: 1–2 items `{title, detail}`, specific to the threat type.

Regression guard: a test runs every scenario and fixture and asserts that verdict, score, gate,
vector and findings are byte-identical to the current backend.

## Verification plan

1. Automated: backend regression + new text tests; strict card test for every state (13 real
   responses + errors), extended to check headings per verdict, ≤2 reasons and actions, no raw
   addresses on the main card, and Variant C applied to every string.
2. Push to the existing project; the owner reviews T5, T7, T8 (High), T6 (Suspicious),
   T1, T2, T3 (Low), T9 (Inconclusive) and an error state in Hebrew Gmail on the side panel.
3. Phase 2 closes on the owner's visual approval.

---

# v4 proposal: Detailed analysis and Welcome screens (awaiting approval)

The approved main card is unchanged. All developer-facing information (request IDs, rule IDs,
signal vectors, probe, direction and render tests) leaves the user interface. It moves to an
explicitly isolated **Developer tools** screen that exists only in dev builds; production builds
contain none of it.

## Detailed analysis (pushed card)

```
 ← Detailed analysis                    CardHeader title
   High risk · risk index 75/100        subtitle (context, no IDs)

 How was this decision made?            bold heading
 A strong warning sign appeared together
 with a request that is hard to undo.
 Together, they make this High risk.
 The risk index shows where this email
 sits within its risk level. It is not
 a probability.                         grey

 Evidence found
 ↩  Reply address changed               bold title (icon)
    Replies now go to a different
    address than earlier messages in
    this thread.
    Seen in this email                  grey tag
    Sender                              grey key
    billing@acmesupply.example          value, grey, isolated
    Replies go to
    acme.supply.accounts@gmail.example
 ─────────────────────────────────────  divider between findings only
 🏦 Asks to change bank details
    It asks you to pay a new account.
    Based on the wording
    Quoted from the email
    "…kindly wire the INV-2207 payment
    to our new account…"

 Analysis coverage
 10 checks completed · 3 not applicable
 · 0 unavailable
 Completed checks show what was
 examined, not how certain the verdict
 is.                                    grey
   ▸ Show details                       collapsible
     Completed: Sender authentication,
     Reply address, Display name, Known
     contacts, Look-alike domains, Sender
     familiarity, Thread consistency,
     Hidden content, Request wording,
     Pressure language
     Not applicable: Links and URLs (none
     in this email), Attachments (none)
     False-alarm safeguards: none needed

 Limitations
 MailLens examines this email and your
 email history only.
   ▸ Show details
     • No threat-intelligence or website
       reputation lookups
     • Attachments are not opened, only
       their names and types are checked
     • Text inside images is not read
     • Request detection is English-only
     • "Known contact" means someone you
       emailed recently
     • A well-made attack from a new,
       authenticated sender can look clean
```

Inconclusive differs only in content: "Unavailable: Sender authentication (no results found,
common for forwarded mail)", and a decision sentence that explains why Low would be misleading.
Low shows "No check found a contradiction…" and "Evidence found: Nothing contradicted the email's claims."

## Welcome screen (homepage)

```
 [🛡] Welcome to MailLens                CardHeader with a circular shield image
      Email risk analysis               subtitle

 MailLens checks whether an email is
 what it claims to be, and explains any
 risk in plain language.

 ✓  Protection ready                    green bold; shown ONLY after a successful
    Connected to the analysis service   authenticated check (see below)

 ✉  Open an email to analyze it
    The result appears here
    automatically.

                    Advanced settings   borderless button
```
Other states, same layout:
- **Analysis service unavailable** (amber, cloud-off icon): "MailLens can't reach its analysis service right now."
- **Setup required** (grey): "MailLens isn't connected yet." with an **Open advanced settings** button.

## Advanced settings (pushed; also the ⋮ menu action)

```
 ← Advanced settings
 Analysis service
   Service URL       [ https://… ]       text input (URL is not a secret)
   API key           [            ]      empty; "A key is saved. Enter a new one to replace it."
   [ Save ]
   Status: Connected                     after a successful check
 Relationship checks
   On / Off  · [Enable]
 Developer tools                         dev builds ONLY: probe last email, direction
                                         and render tests, last request ID
```
The API key is never displayed or echoed back, only replaced.

## How it is built (CardService)

| Element | Widget |
|---|---|
| Bold headings | TextParagraph `<b>…</b>` (as on the approved main card) |
| Finding title + sentence + tag | DecoratedText: Material icon, text = bold title + sentence, bottomLabel = tag |
| Evidence key/value | DecoratedText: topLabel = key (plain), text = value in grey, isolated |
| Divider between findings | `CardService.newDivider()` |
| Expandable details | CardSection `setCollapsible(true)`, `setNumUncollapsibleWidgets(2)` (heading + summary stay visible) |
| Welcome logo | CardHeader `setImageUrl` (Google-hosted shield icon) + `ImageStyle.CIRCLE` |
| Status row | DecoratedText with icon and coloured bold text; not colour-only (word + icon) |
| Settings | TextInput (URL, key), TextButton Save, notification on save |
| Direction | Variant C `ltr_()` on every line; addresses get their own isolate |

## Backend support (presentation only, protected by the decision snapshot test)

1. `decision_explanation`: one plain-language paragraph per gate, with no rule IDs.
2. Per finding `details: [{label, value}]` (e.g. Sender / Replies go to), set where the evidence
   is created, so addresses are shown as labelled values instead of buried in sentences.
3. Friendly check names with a reason for "not applicable" and "unavailable", plus plain-language
   safeguards and limitations.
4. A tiny authenticated `GET /v1/status` (API key required, rate-limited, returns only `{"status":"ok"}`)
   so "Protection ready" means the service is reachable **and** the key is accepted. `/healthz`
   alone can't tell whether the key is valid.
