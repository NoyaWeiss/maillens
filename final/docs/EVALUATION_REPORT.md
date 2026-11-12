# MailLens: Detection Evaluation (primary result: v4 benchmark)

> **A balanced (100/100), synthetic, self-authored benchmark. Not a real-world accuracy estimate.**
> Real mail is overwhelmingly benign, so real-world precision at the same false-positive rate would be
> much lower. Families hold 5 cases each, so per-family numbers are indicative only.
>
> History: [v3](EVALUATION_REPORT_v3.md) · [v2](EVALUATION_REPORT_v2.md) · [v1](EVALUATION_REPORT_v1.md) ·
> [retrospective engine comparison](ENGINE_COMPARISON.md).

## 1. Protocol (each step committed in git, in this order)

| Step | Commit |
|---|---|
| Candidate engine (action-in-context layer) designed on v1/v2/v3 + Phase 3 cases only, then **frozen** | `20f0e5e` |
| Freeze record with the **keep/revert rule fixed in advance**; v4 dataset written afterwards; labels committed; no engine run yet | `2b171d6` |
| **Single run** of both frozen engines (baseline `c7ffff5`, candidate `20f0e5e`), each from its own git worktree | this commit |

- **Order:** the engine was frozen *before* the dataset was written, so the dataset couldn't shape the rules.
- **Decision rule (from `eval/v4/FREEZE.md`):** keep only if recall rises at least 5 points, FPR rises at
  most 3 points, and no category collapses.
- **Alert policy, unchanged:** Suspicious or High = detected; Inconclusive = not detected (there were none).

### Dataset composition (`eval/v4/DATASET_CHECK.txt`)

| | Malicious | Legitimate |
|---|---|---|
| Families × cases | 20 × 5 | 20 × 5 |
| Difficulty (easy / medium / hard) | 25 / 48 / 27 | 30 / 45 / 25 |
| Type origin (v1-like / v2-like / v3-like / novel) | 50 / 20 / 15 / 15 | 35 / 30 / 25 / 10 |

How v4 differs from earlier datasets:
- **v1–v3 each emphasized one era** of attack types; **v4 mixes all of them** with novel types: wallet
  drainers, fake domain renewals, permission abuse, and fake-counsel acquisition wires.
- **Hard look-alikes for the new layer** are deliberately included: vendor support emails with phone
  numbers, Sign-in-with-Google signups, internal MFA guidance, awareness emails quoting the scams, and
  outreach containing "congratulations" and a phone number.
- **Everything is new:** organization (`corvalis.example`), people, domains and wording. Nearest-neighbour
  similarity to any v1–v3 case is median 0.30 and max 0.74; one case is above 0.6, a generic short
  colleague email.

## 2. Results: same 200 cases, both engines frozen

| | Baseline `c7ffff5` | **Candidate `20f0e5e`** |
|---|---|---|
| Confusion (TP / FN / FP / TN) | 51 / 49 / 2 / 98 | **63 / 37 / 2 / 98** |
| Recall (95% CI) | 0.51 (0.41–0.61) | **0.63 (0.53–0.72)** |
| Precision (95% CI) | 0.962 (0.87–0.99) | **0.969 (0.90–0.99)** |
| F1 | 0.667 | **0.764** |
| FPR (95% CI) | 0.02 (0.006–0.07) | **0.02 (0.006–0.07)** |

**Paired, case by case: 12 attacks gained, 0 lost, 0 new false positives** (exact McNemar p ≈ 0.0005).

### By difficulty and type origin (malicious detected)

| | Baseline | Candidate |
|---|---|---|
| Easy / medium / hard | 13/25 · 22/48 · 16/27 | 17/25 · 27/48 · 19/27 |
| v1-like / v2-like / v3-like / novel | 43/50 · 6/20 · 0/15 · 2/15 | 44/50 · 8/20 · **8/15** · 3/15 |

There were no false positives on any easy or medium legitimate case, for either engine.

### By attack family (malicious detected, baseline → candidate)

| Improved | Unchanged, strong | Unchanged, weak |
|---|---|---|
| callback phishing 0→4 · refund/benefits lure 0→4 · fake invoice/QR 2→3 · evasion 2→3 · fake domain renewal 0→1 · fake-counsel wire 0→1 | brand look-alike 5 · spoofed own domain 5 · gift cards 5 · OAuth consent 5 · compromised contact 5 · payroll diversion 5 · thread hijack 4 · vendor look-alike 4 · MFA theft 4 | **wallet drainer 0** · **voicemail lure 0** · **legal threat 0** · permission abuse 2 · malicious attachment 3 |

### False positives (identical in both engines, gate S-A; none are new)
- `W147` internal MFA guidance ("If you get an MFA prompt you didn't start, deny it…")
- `W155` awareness email about gift-card scams

### Why the remaining misses are missed
- **Wallet drainers:** "connect your wallet" or "sign the approval" isn't one of the action classes.
- **Voicemail and legal lures:** the sign-in or download link points to the sender's own (attacker-registered)
  domain, so there's no *independent* context. That's deliberate; it's what keeps the false-positive rate flat.
- **Legal threats:** "review the evidence" and "download the filing" don't match an action class.

## 3. Decision: **KEEP** the candidate (`20f0e5e`)

The pre-registered rule is met on every count:

| Criterion | Required | Result |
|---|---|---|
| Recall | +5 points or more | **+12 points** |
| FPR | at most +3 points | **+0 points** |
| No category collapses | | **0 detections lost** |

**Honest caveats on generalization:**
- **Most of the gain (8 of 12) comes from v3-like types.** The layer was designed after seeing v3's misses
  (callback, refund). It transfers to new wording and new organizations of those types, not broadly to
  unseen types: novel attack types went from 2 to only 3 of 15.
- **The confidence intervals overlap** (0.41–0.61 vs 0.53–0.72). The paired comparison is the stronger
  evidence: 12 gained, 0 lost.
- **The same author** wrote the engine and every dataset, aware of what the engine detects. Freezing first
  limits but can't remove this bias.

## 4. What the action-in-context layer does (gate S-X, Suspicious only, never High)

It fires only when **all three** hold:
1. **A sensitive action:**
   - credentials or MFA
   - payment
   - permission (install, enable, grant access)
   - disclosure of financial or identity data
   - out-of-band contact via a phone number in the email
2. **A verified-unfamiliar, non-bulk sender.**
3. **At least one independent context:**
   - a link to an unrelated domain (brand-owned domains excluded)
   - a call-back number
   - a risky attachment
   - pressure or threat wording
   - a financial lure

The existing quoted, described and negated guards apply. Unit tests cover legitimate look-alikes in
`backend/tests/test_signals.py`. On development data it changed: v1 88→93 TP, v3 40→65 TP, Phase 3
18→19, with false positives unchanged everywhere.

## 5. Limitations
- Synthetic, balanced, small families, template variation, simulated relationship context, same author.
- **v4 is now spent as a holdout.** Any further change needs a new benchmark.
- The structural gaps remain:
  - **Intent beyond a fixed action vocabulary** (wallets, "review the evidence")
  - **Reputation of never-seen domains**, which is out of scope with no outbound calls
  - A guarded learned classifier would be the next step, validated on new data.

## 6. Reproduce
```bash
python3 eval/v4/generate.py      # identical dataset (seeded)
python3 eval/v4/run_both.py      # both frozen engines from temporary worktrees -> eval/v4/results.json, metrics.json
```
Dashboard-ready: `eval/metrics.json` (primary v4 plus v3/v2/v1 history, labelled synthetic).
