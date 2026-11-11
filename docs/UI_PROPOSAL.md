# Phase 2: card redesign proposal, v2

Status: **proposal v2, awaiting owner approval.** v1 (compact variant, commit `3ba2f43`) was
reviewed in real Gmail and not approved: cluttered, weak hierarchy, red overused, and broken
English text direction in Hebrew (RTL) Gmail. Phase 2 stays open until the owner visually
approves the result in Gmail.

## 1. Verified platform constraints

From the official CardService and widget documentation (checked 2026-11-11):

| Need | What CardService offers | Consequence for the design |
|---|---|---|
| Headings | `CardSection.setHeader()` (one fixed style) | Every block gets a short section heading; this is our only "heading" typography |
| Emphasis | `<b>`, `<i>`, `<u>`, `<s>`, `<font color>`, `<br>` in text; **labels are plain text only** | Three text levels: **bold title**, regular explanation, small grey label (metadata) |
| Font size, fonts, CSS | none | Hierarchy comes from heading, bold, grey labels and spacing |
| Alignment / direction | **none** (no `dir`, no alignment for text widgets) | Direction can only be influenced with Unicode control characters (see section 4) |
| Side-by-side layout | Columns are not supported in the Gmail message sidebar | Single vertical column |
| Icons | Material icons (any Google Font icon); colour not settable | Icons mark meaning by shape; never the only signal |
| Persistent buttons | `FixedFooter` (primary FILLED, secondary OUTLINED) | Technical evidence and Re-analyze are always visible |
| Card header | optional | **Removed**: Gmail already shows "MailLens" above the card (fixes the duplicate branding) |
| Render-time rules (learned) | Empty sections or labels make Gmail reject the card | Enforced by the strict card test for every state |

## 2. Main card structure (always the same order)

1. **Risk assessment:** verdict word + score, attack category (hedged), one-sentence summary.
2. **Why was this flagged?** At most two findings: **bold label**, one-sentence explanation, grey evidence-type tag.
3. **Potential impact:** one sentence on what happens if the user complies (High/Suspicious/Inconclusive only).
4. **Recommended action:** one or two actions, each a **bold action** plus one sentence.
5. Fixed footer: **Technical evidence** · **Re-analyze**.

No raw email addresses, URLs or header text on the main card; those live in Technical evidence.

### High risk (T5)

```
 ┌ Gmail sidebar ─────── MailLens ─┐   ← Gmail's own title; no second "MailLens"
 │ Risk assessment                 │   section heading
 │ ⛔ High risk · 75/100           │   bold; only the words "High risk" in red
 │    ▰▰▰▰▰▰▰▰▱▱                   │   red bar
 │    Likely vendor account takeover│   grey label, hedged ("Likely")
 │ Someone may be using your        │   neutral text, one sentence
 │ conversation with this vendor to │
 │ redirect a payment.              │
 │                                  │
 │ Why was this flagged?            │
 │ ↩  Unusual reply address         │   bold label
 │    Replies would go to a         │   neutral explanation
 │    different address than earlier│
 │    messages from this vendor.    │
 │    Observed in this email        │   grey tag (evidence type)
 │ 🏦 Bank-detail change request    │
 │    The email asks you to send    │
 │    payment to a new account.     │
 │    Detected from the wording     │   grey tag (heuristic)
 │                                  │
 │ Potential impact                 │
 │ If this is fraud, a payment would│
 │ go to the attacker and is usually│
 │ unrecoverable.                   │
 │                                  │
 │ Recommended action               │
 │ ✓  Verify with the vendor        │   bold action
 │    Call a number you already     │
 │    trust before changing payment │
 │    details.                      │
 │ ✓  Don't reply to this email     │
 │    Report it to your finance or  │
 │    security team.                │
 ├──────────────────────────────────┤
 │ [Technical evidence] [Re-analyze]│   fixed footer, neutral brand colour
 └──────────────────────────────────┘
```

### Suspicious (T6)

```
 Risk assessment
 ⚠  Suspicious · 40/100                 amber; bar ▰▰▰▰▱▱▱▱▱▱
    Possible payment redirection
 A known sender asks for an irreversible change. Nothing else looks wrong.

 Why was this flagged?
 🏦 Bank-detail change request
    The email asks you to send future payments to a new bank account.
    Detected from the wording · sender is known to you

 Potential impact
 If the request is fraudulent, payments would go to the attacker.

 Recommended action
 ✓  Verify by phone
    Use contact details you already have, not ones in this email.
 ✓  Hold payments
    Don't pay the new account until the change is confirmed.
```

### Low risk (T2: asks you to sign in)

```
 Risk assessment
 ✓  Low risk · 8/100                    green; bar ▰▱▱▱▱▱▱▱▱▱
    12 checks ran
 No signs of deception were found.

 Recommended action                     (only when the email asks for something)
 ↗  Sign in directly
    If you need to act, open the site yourself instead of using the link.
```
A Low email that asks for nothing (T1, T3) shows only the Risk assessment block.

### Inconclusive (T9)

```
 Risk assessment
 ?  Inconclusive · no score             grey; no bar (a score would be false precision)
    Sender could not be verified
 We can't confirm who sent this, and it asks you to sign in.

 Why was this flagged?
 🔒 Sender can't be verified
    No authentication results were available, which is common for forwarded mail.
    Limited confidence
 🔑 Sign-in request
    The email asks you to sign in through a link.
    Detected from the wording

 Potential impact
 If this is phishing, a password entered on the linked page could be stolen.

 Recommended action
 ✓  Confirm another way
    Check with the sender through a channel you already trust.
```

### Error

```
 Analysis unavailable
 ⚠  No verdict
    MailLens couldn't analyze this email.
 The analysis service is unreachable.
 [ Try again ]
 Step: call backend                     grey; dev builds add the raw error
```

## 3. Technical evidence (separate, pushed card)

```
 Technical evidence                     header title; subtitle "Request 1a2b3c"
 Decision
 High via H-B: a strong finding (S2) plus an irreversible request (S13).
 Vector D2 · A3 · E1 · P0 · N0          (legend in grey below)
 Confidence: full · 10 of 10 checks ran

 Evidence (2)
 S2 Reply-To divergence · strong · observed
   Claim: a reply in your thread with billing@acmesupply.example
   Reality: replies go to acme.supply.accounts@gmail.example
 S13 Request · irreversible · heuristic
   "…kindly wire the INV-2207 payment to our new account…"

 Attack story              (collapsed, first line visible)
 Checks                    (collapsed) Ran 10 · Unavailable 0 · Not applicable 3
 False-positive guards     (collapsed)
 Limits and assumptions    (collapsed)
 Developer                 (dev builds only: probe, direction test)
```
Exact addresses, excerpts and headers appear only here, each wrapped in the chosen
direction-safe form (section 4).

## 4. RTL/LTR approach

**What the platform allows:** nothing structural. Text widgets have no `dir` and no alignment,
and labels are plain text. In Hebrew Gmail the card is laid out right to left and every text
block gets an RTL base direction. English punctuation and leading numbers are then reordered by
the Unicode bidi algorithm, which is exactly the "period on the wrong side, `1.` on the wrong side" problem.

**The only tool available:** Unicode direction control characters inside the text. Candidates,
being tested now on a developer card in real Hebrew Gmail:

| Variant | Characters | Expected effect if Gmail keeps them |
|---|---|---|
| A | none | today's broken ordering (baseline) |
| B | LRM (U+200E) at start and end | trailing punctuation stays with the English text |
| C | LRI … PDI (U+2066 … U+2069), an isolate | whole string ordered left to right, isolated from surroundings (the modern recommendation) |
| D | LRE … PDF (U+202A … U+202C), an embedding | like C, older mechanism |

Alignment will remain right-aligned in Hebrew Gmail whatever we do; only the *order* inside each
line can be fixed. So the design also stays direction-safe on its own, as a second layer:
- Main-card titles are short noun phrases **without trailing punctuation**; explanations are single sentences.
- **No numbered lists:** each action has an icon and a bold title instead of "1." / "2.".
- **No raw addresses or URLs on the main card.** In Technical evidence each is isolated individually.
- The score is "75/100" inside the same isolated run as the verdict word, so it can't drift.

The winning variant is applied in one helper used for every string, so the choice is
centralized and testable (a unit test asserts every rendered string is wrapped).

## 5. Colour and evidence-type system

| Element | Colour | Also conveyed by (not colour alone) |
|---|---|---|
| Verdict word + score bar | High red `#d93025`, Suspicious amber `#b06000`, Low green `#188038`, Inconclusive grey `#5f6368` | word, icon shape (⛔ ⚠ ✓ ?), bar length |
| Finding labels, explanations, impact, actions | default text colour (neutral) | — |
| Evidence-type tags, metadata | grey labels | wording |
| Footer primary button | one neutral brand colour (not verdict red) | — |

Evidence type is stated in words on every finding, so inference is never shown as fact:
"Observed in this email" (observed), "From your email history" (mailbox inference),
"Detected from the wording" (heuristic). Attack categories are hedged: "Likely …" for High,
"Possible …" for Suspicious, none for Low or Inconclusive.

## 6. Content changes needed (presentation only)

The main card needs address-free finding titles and explanations, an impact sentence and
titled actions. Two ways to provide them:

- **Option 1 (recommended): presentation fields from the backend.** Each finding gains `title` and
  `summary`; the response gains `impact` and `actions: [{title, detail}]`, all produced by the
  existing template layer (`narrative.py`). Detection, scoring, gates, permissions and privacy are
  untouched, and a regression test asserts that every scenario's verdict, score, gate and vector
  are identical before and after. Text stays testable in Python next to the logic it describes.
- **Option 2: an add-on-side mapping** from signal ID to title and text. No backend change, but the
  wording drifts from the detection logic and the explanations can't be specific (for example,
  "earlier messages from this vendor" vs. "a personal mailbox").

## 7. Verification plan

1. Owner checks the direction test card in Hebrew Gmail; we pick the variant from that evidence.
2. Implement; the strict card test covers every state (13 real responses + error variants), and new
   tests assert there are no raw addresses on the main card, wrapped strings, no numbered lists, and
   unchanged verdicts.
3. Push; owner reviews High (T5, T7, T8), Suspicious (T6), Low (T1, T2, T3), Inconclusive (T9) and
   an error state in Hebrew Gmail on the narrow side panel.
4. Phase 2 closes only on the owner's visual approval.
