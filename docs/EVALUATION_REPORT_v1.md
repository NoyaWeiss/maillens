# HISTORICAL BASELINE (v1): MailLens evaluation, original engine `00bb9d1`

> **Superseded as the primary result** by the v2 holdout in [EVALUATION_REPORT.md](EVALUATION_REPORT.md).
> Kept unchanged for reproducibility. v1 was later used as **development data** to guide improvements,
> so it is no longer an independent test of the current engine.

**Synthetic, balanced, self-authored data.** These numbers describe MailLens on 200 synthetic emails
with a 50/50 class balance. They are **not** real-world detection accuracy. Real mailboxes are
overwhelmingly benign, so precision on real traffic would be much lower than reported here for the
same false-positive rate.

## 1. Methodology

| Step | Evidence |
|---|---|
| Engine frozen before the dataset existed | `eval/v1/FREEZE.md`: commit `00bb9d1`, code hash `8ef706999ca4add2` checked by `eval/run.py` (it refuses to run if the engine changed) |
| Dataset and labels committed **before** any run | `26e28ca` (`eval/v1/dataset.jsonl`, `eval/v1/generate.py`) |
| One blind run, no rule changes afterwards | `1c6df19` (`eval/v1/results.jsonl`, `eval/v1/metrics.json`) |

- **Ground truth:** every label comes from the scenario's *intent* (what the sender is trying to
  achieve), written in `eval/generate.py` with a rationale per case. No label was derived from or
  edited after MailLens output.
- **Independence:** a new synthetic universe (organization `harborview.example`, new vendors, people
  and domains). There's no overlap with the demo mailbox or the 41 Phase 3 development cases, and no
  case was used to tune the engine.
- **Dataset:** 100 Malicious and 100 Legitimate emails in 24 categories, generated programmatically
  (seed 20261112). The generator uses scenario families with several hand-written phrasings, varied
  names, amounts and domains, thread history (12 cases), mailbox relationship context, attachments, link
  styles, bulk headers (18) and missing authentication results (4).
  - Quality checks before the run: 0 exact duplicates, **0** near-identical pairs (token Jaccard > 0.85),
    200/200 valid against the production request schema.
  - Families deliberately include brands, phrasings and techniques the engine has no rule for.
- **Alert policy (fixed in advance):** Suspicious or High = **detected**; Low = **not detected**.
  Inconclusive is reported separately: the primary metrics treat it as not detected, and a sensitivity
  view excludes it.
- **Intervals:** 95% Wilson score intervals.

Rerun:
```bash
python3 eval/v1/generate.py                      # regenerates the identical dataset (seeded)
git checkout 00bb9d1 && cd backend && uv run python ../eval/run.py   # (v1 layout at that commit)
```

## 2. Results

### Confusion matrix (primary: Inconclusive counted as not detected)

| | Alert (Suspicious/High) | No alert (Low/Inconclusive) |
|---|---|---|
| **Malicious (100)** | TP = **69** | FN = **31** (incl. 1 Inconclusive) |
| **Legitimate (100)** | FP = **11** | TN = **89** |

| Metric | Value | 95% CI |
|---|---|---|
| Precision | **0.863** | 0.770–0.921 |
| Recall (detection rate) | **0.690** | 0.594–0.772 |
| F1 | **0.767** | – |
| False-positive rate | **0.110** | 0.063–0.186 |
| Accuracy | 0.790 | – |

**Inconclusive impact:** 1 case (a malicious forwarded plain-text phish). Excluding it gives
recall 0.697, F1 0.771; other metrics are unchanged.

**Verdict mix:**
- Malicious: 40 High, 29 Suspicious, 30 Low, 1 Inconclusive.
- Legitimate: 89 Low, 9 High, 2 Suspicious.
- Alerts on malicious mail came mostly from H-B (33) and S-D (22).

### By category (n per category is small; read as patterns, not rates)

| Malicious category | Detected / n |
|---|---|
| BEC: executive impersonation | 10/10 |
| BEC: payroll diversion | 8/8 |
| Vendor thread hijack | 8/8 |
| OAuth consent phishing | 6/6 |
| Social engineering (MFA code / remote access) | 6/6 |
| Payment redirection | 9/10 |
| Malicious attachment | 7/10 |
| Credential phishing (brand impersonation) | 5/10 |
| Vendor impersonation (look-alike domain) | 4/8 |
| Evasion attempts | 4/10 |
| Compromised known contact | 2/8 |
| Plain-text phishing, clean infrastructure | 0/6 |

| Legitimate category | False alarms / n |
|---|---|
| Routine business · invoices · urgent internal requests · newsletters · **security newsletters/awareness about scams** · **legitimate payment-detail changes** · platform/ticketing/list mail · attachments · SSO invitations | **0** across 78 |
| Account / security notifications | 3/10 |
| Unfamiliar or new address (benign) | 2/6 |
| **Forwarded phish reported to IT** | **6/6** |

**By difficulty (pre-assigned):**
- Malicious detected: easy 8/12, medium 41/50, hard 20/38.
- Legitimate false alarms: easy 0/28, medium 3/44, hard 8/28.

## 3. Failure patterns

**False negatives (31):**

| Pattern | Cases | Why |
|---|---|---|
| Plain-text phishing from attacker-owned, authenticated domains | 6 (1 Inconclusive) | Documented blind spot: no contradiction to observe; no reputation data |
| Compromised known contact sending a link | 6 | Known, authenticated sender with generic link text; by design a level-2 request alone never escalates |
| Brands outside the small brand list (Zoom, Slack, Wells Fargo, Adobe Sign, Salesforce) | 5 | The display-name brand check and brand-in-subdomain URL check only know a few brands; generic link text gives the link check nothing to compare |
| **Combosquatting** (`vendorname-billing`, `vendorname-finance`) | 5 | The look-alike check catches near-spellings (edit distance ≤ 2) and confusable characters, **not** a real vendor name plus a suffix |
| Evasion: image-only instruction, fake quoted history, **attacker-added bulk headers**, URL shortener, a request split across sentences, letter-spaced words | 6 of 10 | Matching works per sentence on visible text; bulk headers downgrade link findings (abusable); no OCR |
| Macro-enabled Office files and password-protected ZIPs | 3 | Rated weak (level 1) by design to avoid false alarms on internal workbooks |
| Unusual request phrasing ("update the beneficiary on file") | (within the above) | Request patterns are a fixed English pattern list |

**False positives (11):**

| Pattern | Cases | Why |
|---|---|---|
| Colleague forwards a phish to IT | 6 | Known limitation F-18: forwarded content is evaluated as the forwarder's own |
| A legitimate service named "CloudMail" | 3 | **Collision with a demo-only brand entry** (`cloudmail` → `cloudmail.example`) in the engine's brand list; the generator reused the name. Lesson: demo fixtures must not live in the production brand list |
| A known partner writing casually from a personal Gmail | 2 | Known name from a free-mail address is strong evidence by design (it's also how payroll diversion looks) |

What worked: **zero false alarms** on security newsletters and awareness emails that quote scams,
genuine payment-detail changes, invoices, urgent internal requests and platform mail (78 cases). Every
BEC, thread-hijack, OAuth-consent and MFA/remote-access attack was detected.

## 4. Limitations of this evaluation

- **Synthetic and self-authored:** the same team wrote the engine and the dataset. Families were designed
  to include unknown techniques, but a shared mental model is unavoidable. An external or real-world
  corpus would be the next step.
- **Balanced classes:** precision does not transfer to real prevalence.
- **Small categories (4–12 each):** wide uncertainty; the intervals are given only for the overall metrics.
- **Templated variation:** families vary wording, names and structure, but cases within a family share a
  scenario.
- **Relationship context is simulated** (the facts the add-on would compute), not read from a real mailbox.
- **Single run:** the engine is deterministic, so variance comes only from dataset construction.

## 5. Future improvements (documented only; not applied, the engine stays frozen for this report)

1. Remove demo-only brands from the production brand list (fixture isolation).
2. Detect combosquatting: a known vendor or brand name plus a separator and suffix.
3. Expand the brand list, or derive brands from the user's own correspondents.
4. Handle forwarded content explicitly (F-18): attribute it to "forwarded", and explain rather than escalate.
5. Make bulk-header leniency conditional on authentication matching the List-Unsubscribe domain.
6. Match requests across sentence boundaries; normalize spaced-out letters.
7. Any change must then be evaluated on a **new** holdout, not this one.
