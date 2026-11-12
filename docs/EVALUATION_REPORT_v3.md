# HISTORICAL (v3): MailLens evaluation, engine `c7ffff5` on the v3 holdout

> **Superseded as the primary result** by the v4 benchmark in [EVALUATION_REPORT.md](EVALUATION_REPORT.md). Kept unchanged.
> v3 was later used as **development data** for the action-in-context layer.

> **Synthetic, balanced (100/100), self-authored data. These are not real-world accuracy estimates.**
> Real mail is overwhelmingly benign, so real-world precision at the same false-positive rate would be
> far lower. Categories hold 6–10 cases each.
>
> History: [v2 report](EVALUATION_REPORT_v2.md) · [v1 report](EVALUATION_REPORT_v1.md).

## 1. Protocol (each step committed in git, in this order)

| Round | Engine (frozen before its holdout was written) | Holdout | Use afterwards |
|---|---|---|---|
| v1 | `00bb9d1` | 200 cases, labels `26e28ca`, run `1c6df19` | development data |
| v2 | `97f93f8` | 200 new cases, labels `138ab48`, run `7bf59ca` | development data |
| **v3** | **`c7ffff5`** | **200 new cases, labels `3f9c896`, run `073bf0a`** | **primary result** |

- **Labels** come from each scenario's intent and are committed before the run; none were ever edited.
- **Alert policy**, unchanged since v1: Suspicious or High = detected; Low = not detected; Inconclusive
  reported separately (there were none).
- **v3 content:** a new organization (`vantorbio.example`) and attack types absent from v1 and v2:
  callback phishing, fake legal notices, fake vendor onboarding, fake audit confirmations,
  board-member data requests, fake IT agents, tax-refund scams, job/check scams, charity scams,
  calendar-invite phishing, refund scams, vendor thread hijacks and executive pivots to SMS.
- **v3 legitimate look-alikes:** real auditor confirmations, procurement approvals, courier customs
  invoices, internal IT rollouts, approval requests, awareness emails about these same scams.
- **Independence:** nearest-neighbour similarity to any v1 or v2 case is at most 0.55 (median 0.26).
- **Intervals:** 95% Wilson.

## 2. Primary results: v3 holdout, frozen engine `c7ffff5`

| | Alert | No alert |
|---|---|---|
| **Malicious (100)** | TP **40** | FN **60** |
| **Legitimate (100)** | FP **0** | TN **100** |

| Metric | Value | 95% CI |
|---|---|---|
| Precision | **1.00** | 0.912–1.00 |
| Recall | **0.40** | 0.309–0.498 |
| F1 | 0.571 | – |
| False-positive rate | **0.00** | 0.00–0.037 |

### Did this round's improvements generalize? Same holdout, both engines frozen

| Engine on v3 | TP | FP | Recall |
|---|---|---|---|
| v2 engine `97f93f8` | 37 | 0 | 0.37 |
| **v3 engine `c7ffff5`** | **40** | **0** | **0.40** |

The gain is +3 on unseen data (all fake-charity appeals): no detection lost, no false positive added.
On its development data (v2), the same changes raised detections from 47 to 79.

## 3. The central finding: development gains don't transfer to new attack types

| Round | Gain on development data | Gain on the new holdout (same-holdout comparison) |
|---|---|---|
| v1 → v2 engine | +17 TP, −9 FP (v1) | **+5 TP, +1 FP** (v2) |
| v2 → v3 engine | +32 TP, ±0 FP (v2) | **+3 TP, ±0 FP** (v3) |

**58 of the 60 v3 misses have no finding and no recognized request.** Six attack types score 0/8:
callback phishing, fake legal notices, fake onboarding forms, tax refunds, job/check scams and
calendar invites.

MailLens flags emails that **contradict themselves** (identity, links, headers, thread history) or ask
for a request type it knows. New attack *types* from self-consistent, authenticated, unfamiliar
infrastructure present neither. Each round of pattern additions covered the previous holdout's
types, and the next holdout introduced new ones.

**Precision stayed at 0.98–1.00 with an FPR of 0–1%** across both holdouts. The conservative design
(High needs corroboration, unknown never escalates) keeps false alarms rare, which is the deliberate
trade-off.

### Per-category detection (v3)

| Detected well | Partly detected | Not detected (0/8) |
|---|---|---|
| Board-member data request 6/6 · executive pivot to SMS 8/8 · fake IT agent 6/8 · fake audit confirmation 6/8 · vendor thread hijack 6/8 | Charity appeal 4/6 · refund/tech-support scam 4/8 | Callback phishing · fake legal notice · fake onboarding form · tax refund · job/check scam · calendar-invite phishing |

## 4. What changed in engine `c7ffff5` (development work on v1/v2)

- **Context-aware request intents** (directive verb plus sensitive object in one sentence, with the
  described/quoted/negated guards): MFA approval, password disclosure, sensitive-data export, crypto or
  advance fees, a new payment channel or QR payment, and payment through a portal.
- **A general negation guard** ("never share your password").
- **Combosquatting** now includes organization words (hr, people, it, escrow…) and hyphen-insensitive names.
- **A known contact sharing a document via an unrelated, never-seen, non-file-sharing domain → Suspicious.**
- **Legitimate look-alike regression tests** for every new intent.

## 5. Limitations and recommended direction

- **Same author** wrote the engine and all three datasets; balanced classes; small categories;
  template-based variation; simulated relationship context.
- **A closed request taxonomy doesn't generalize to new attack types.** More patterns would raise the next
  development score, not real-world recall. The structural next steps:
  1. **Destination and intent novelty** for *any* call to action (link, phone number, attachment) from an
     unfamiliar sender, with an organization allow-list. This is the signal most v3 misses share.
  2. **A learned or LLM-assisted intent classifier** behind strict guardrails: classification only, never
     a verdict on its own, with prompt-injection-resistant input handling. Validate it on a new holdout.
  3. **Threat-intelligence / domain-age reputation** for never-seen domains (currently out of scope).
- **v3 is now spent as a holdout,** like v1 and v2.

## 6. Reproduce

```bash
python3 eval/v3/generate.py                       # identical dataset (seeded)
cd backend && uv run python ../eval/run.py v3     # checks the frozen engine hash, then evaluates
```

Machine-readable: `eval/metrics.json` (primary v3 plus the v2/v1 history, dashboard-ready),
`eval/v3/results.jsonl`, `eval/v3/metrics.json`, `eval/v3/results_v2_engine.json`.
