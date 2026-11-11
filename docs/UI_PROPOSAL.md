# Phase 2: CardService redesign proposal

Status: **proposal, awaiting owner approval. Nothing here is implemented yet.**

## What the platform allows in the Gmail message sidebar (researched)

| Capability | Gmail sidebar | Implication |
|---|---|---|
| Columns (side by side) | **Not supported** (compose and Calendar dialogs only) | Everything is a vertical stack |
| Chips, collapse control, overflow menu | Developer preview for add-ons | Not used: preview features are a demo risk |
| Text styling | `<b>`, `<i>`, `<font color>`, `<br>`; **no font size** | Prominence comes from colour, an icon, position and white space |
| Material icons (`MaterialIcon`) | Supported; colour not documented | Icon shape conveys meaning; colour comes from text |
| `DecoratedText` | Icon + top label + text + bottom label + one right-side control | The building block for every row |
| `FixedFooter` | Supported; primary button must be FILLED, secondary OUTLINED | Persistent "Technical evidence" + "Re-analyze" |
| `TextButton` styles | FILLED, FILLED_TONAL, OUTLINED, BORDERLESS; background colour settable | Verdict-coloured primary action |
| `Divider` | Supported | Separates blocks without section headers |
| Render-time rule (learned in Phase 1) | Empty sections and empty labels make Gmail reject the card | Every layout is rendered through the strict test double for all 13 scenarios |

## Design principles

1. **The verdict should be readable within one second**: colour, icon, verdict word, score, and one sentence.
2. **No repetition.** The current card says the same thing three times (headline, Claim vs. Reality,
   Attack Story). Each fact appears once.
3. **At most three reasons** on the main card, ordered by strength; the rest are in Technical evidence.
4. **Low-risk emails stay quiet**: a short card, no alarm vocabulary.
5. **Technical evidence is a separate card** (pushed), reached from a fixed footer button.

## Main card: High risk (example: T5)

```
┌──────────────────────────────────────────┐
│ 🛡  MailLens                              │  header (neutral; brand only)
├──────────────────────────────────────────┤
│ ⛔ HIGH RISK                     75 / 100 │  icon + red bold verdict + score
│    ▰▰▰▰▰▰▰▰▱▱                             │  red score bar (10 segments)
│    Vendor account takeover                │  archetype (bottom label)
│                                           │
│ Replies now go to a Gmail address, and    │  one-sentence explanation
│ the email asks you to change bank details.│
│ ───────────────────────────────────────── │
│ WHY                                       │  section header
│ ✉  Claims  A reply in your thread with    │  ≤3 Claim vs. Reality rows
│           billing@acmesupply.example      │  (icon by evidence type)
│    Reality Replies go to                  │
│           acme.supply.accounts@gmail…     │
│ 💳 Asks   Change of bank details          │  request row (irreversible)
│           Irreversible if fraudulent      │
│ ───────────────────────────────────────── │
│ WHAT TO DO                                │
│ 1. Don't change payment details or reply. │  2–3 actions, verdict-specific
│ 2. Call the vendor on a number you know.  │
│ 3. Report it to finance or security.      │
│ ───────────────────────────────────────── │
│ Full confidence · 10 of 10 checks ran     │  one quiet line
├──────────────────────────────────────────┤
│ [ Technical evidence ]  [ Re-analyze ]    │  fixed footer (filled / outlined)
└──────────────────────────────────────────┘
```

## Main card: Low risk (example: T2)

```
┌──────────────────────────────────────────┐
│ 🛡  MailLens                              │
├──────────────────────────────────────────┤
│ ✅ LOW RISK                        8 / 100 │  green
│    ▰▱▱▱▱▱▱▱▱▱                             │
│                                           │
│ Nothing in this email contradicts what    │
│ it claims.                                │
│ ───────────────────────────────────────── │
│ ℹ  It asks you to sign in. If you need to,│  advisory only when A≥2
│    go to the site directly.               │
│ ───────────────────────────────────────── │
│ Full confidence · 12 of 12 checks ran     │
├──────────────────────────────────────────┤
│ [ Technical evidence ]  [ Re-analyze ]    │
└──────────────────────────────────────────┘
```

## Main card: Inconclusive (T9) and Suspicious (T6)

- **Inconclusive:** grey "?" icon, "INCONCLUSIVE", **no score bar** (a score would imply false
  precision), and the explanation "We can't verify who sent this, and it asks you to sign in."
  Then 2 actions, then the confidence line: "Limited confidence · sender authentication unavailable".
- **Suspicious:** amber "⚠" icon, the same structure as High. For T6 the "Why" block is the single request row
  ("Asks: change of bank details") and the explanation "No red flags, but this request is
  irreversible. Verify it by phone."

## Error card (backend down, Gmail stall, permissions)

```
│ ⚠  NO VERDICT                              │  grey; never green
│    MailLens couldn't analyze this email.   │
│    The analysis service is unreachable.    │  plain reason, no stack text
│ [ Try again ]                              │  FILLED (Phase 1 mitigation)
│ Details: failed at "call backend"          │  small bottom label
```

## Relationship permission prompt (when gmail.readonly isn't granted)

The current full section becomes one row:
`👥 Relationship checks are off. MailLens can compare senders with people you've emailed.  [Enable]`
(DecoratedText with the button on the right.)

## Technical evidence card (pushed)

1. **Decision:** the gate in plain words, then the vector with an inline legend.
2. **All findings:** every finding with signal, level, basis, entity and defanged excerpt.
3. **Also observed** (deduplicated) and **Guards applied**, each collapsible, showing one row when collapsed.
4. **Checks:** ran / unavailable / not applicable, as three lines with counts.
5. **Limits:** out-of-scope list and assumptions, collapsed.
6. **Developer tools**: the probe button, shown only in dev mode, hidden in production.

## What changes vs. today

| Today | Proposed |
|---|---|
| Headline, Claim vs. Reality and Attack Story repeat each other | Explanation once; ≤3 reasons; the story's useful part (the consequence) becomes the request row's bottom line |
| Score is plain text | Score with a coloured 10-segment bar; none for Inconclusive |
| "Technical evidence" is a button in the body | Fixed footer, always visible |
| Error card exposes raw error text | Plain reason + "Try again"; raw step only in small print |
| Relationship prompt is a full section | One row with an "Enable" button |
| Probe button visible to every user | Developer mode only |

## Verification plan for the redesign

1. Every card for all 13 scenario responses and the error variants renders through the strict
   test double (extended for FixedFooter and icon rules).
2. Live check in Gmail on T1–T9, judged visually by the owner.
3. No changes to backend detection; the backend response gains no new fields (the layout uses existing ones).
