# HISTORICAL (v2): MailLens evaluation, engine `97f93f8` on the v2 holdout

> **Superseded as the primary result** by the v3 holdout in [EVALUATION_REPORT.md](EVALUATION_REPORT.md). Kept unchanged.
> v2 was later used as **development data**, so it no longer tests the current engine independently.

> **Synthetic, balanced (100/100), self-authored data. These are not real-world accuracy estimates.**
> Real mail is overwhelmingly benign, so real-world precision at the same false-positive rate would be
> far lower. Category sizes are small (6–10).
>
> Historical baseline (original engine, v1 dataset): [EVALUATION_REPORT_v1.md](EVALUATION_REPORT_v1.md).

## 1. What was done, in order (git evidence)

| Step | Commit |
|---|---|
| v1 evaluation of the original engine (`00bb9d1`): recall 0.69, FPR 0.11 | `1c6df19` |
| v1 preserved under `eval/v1/`; v1 then used **as development data** | `219fea0` |
| Generalizable improvements from v1 failure patterns, verified on development sets | `97f93f8` |
| **Engine frozen**, then a **new 200-case holdout written**, labels committed before any run | `138ab48` |
| Single run of the frozen engine on the holdout | `7bf59ca` |

**The v2 holdout:** a new organization (`lattice-dynamics.example`), new people and vendors, and new
scenario types. These include escrow wire fraud, W-2 data theft, MFA push fatigue, fax/voicemail/chat
lures, HR-policy phishing, OneNote/VHD/CHM/RTL-override files, investment scams, internal-domain
look-alikes and fake invoice portals. Legitimate look-alikes include escrow notices that say "we only
give wiring instructions by phone", IT notices linking to the company's identity provider, and
colleagues forwarding vendor letters.
- **Not a paraphrase of v1:** the nearest-neighbour token similarity to any v1 case is at most 0.56
  (median 0.25); no case exceeds 0.6.
- **Quality checks:** within-v2 near-duplicates capped at 0.85; 200/200 valid against the production schema.

**Ground truth** comes from each scenario's intent and was committed before the run. **Alert policy**
(unchanged): Suspicious or High = detected; Low = not detected; Inconclusive reported separately
(there were none). Intervals are 95% Wilson intervals.

## 2. Primary results: v2 holdout, frozen engine `97f93f8`

| | Alert | No alert |
|---|---|---|
| **Malicious (100)** | TP **47** | FN **53** |
| **Legitimate (100)** | FP **1** | TN **99** |

| Metric | Value | 95% CI |
|---|---|---|
| Precision | **0.979** | 0.891–0.996 |
| Recall | **0.47** | 0.375–0.567 |
| F1 | 0.635 | – |
| False-positive rate | **0.01** | 0.002–0.054 |

### Did the improvements generalize? Same holdout, both engines frozen

| Engine | TP | FP | Recall | Precision | FPR |
|---|---|---|---|---|---|
| Original `00bb9d1` | 42 | 0 | 0.42 | 1.000 | 0.00 |
| Improved `97f93f8` | **47** | 1 | **0.47** | 0.979 | 0.01 |

**Yes, but modestly:** 5 more attacks detected on unseen data, none lost, and 1 new false positive.

The development-set gain was much larger. On v1 (now development data), the engine went from 69 to
86 detections and from 11 to 2 false positives. Most of that gain was specific to the patterns the
fixes targeted. **This gap between development and holdout performance is the central finding.**

### By category (v2; detections / n, with the original engine in brackets)

| Malicious | New (original) |
|---|---|
| CFO wire request | 8/8 (8) |
| W-2 / payroll data theft | 6/6 (6) |
| Internal-domain look-alike | 8/8 (8) |
| Escrow wire fraud | 6/9 (6) |
| Notification lure (fax / voicemail / chat) | **6/10 (2)** |
| Malicious attachment, new file types | 5/8 (4) |
| Evasion, new techniques | 4/7 (4) |
| Vendor email compromise (real mailbox) | 4/8 (4) |
| HR-policy phishing | 0/8 (0) |
| MFA push fatigue | 0/6 (0) |
| Compromised partner mailbox | 0/8 (0) |
| Fake invoice portal / QR | 0/8 (0) |
| Investment / prize scam | 0/6 (0) |

**Legitimate:** 0 false alarms in 11 of 12 categories, including legitimate escrow notices, security
awareness emails that quote attacks, executives' urgent requests, colleagues forwarding mail, and cold
outreach. The single false alarm: an internal IT notice whose sign-in link goes to a SaaS
identity-provider domain (the S-L rule). This risk was predicted when the rule was added.

## 3. Failure patterns (v2)

1. **Request-type coverage (dominant):** in **45 of 53 misses no request was detected at all.** The
   fixed English pattern list doesn't cover approving MFA prompts, sending crypto or "processing fees",
   paying through a portal, acknowledging an HR policy, or simply opening a shared file. New attack
   *types* defeat a closed taxonomy, even when the wording is ordinary.
2. **Self-consistent attacker infrastructure:** fake portals and HR pages are hosted on the sender's own
   authenticated domain, so there's no observable contradiction, which is the engine's core signal.
3. **Compromised real mailboxes** (partner 0/8, vendor 4/8): authentication and history are genuine; only
   the request or link destination differs.
4. **Imitations of the company's own domain using neutral words** (`-hr`, `-people`) aren't in the
   combosquatting word list.

## 4. What was improved (engine `97f93f8`; details in the commit)

- **Brand list:** demo-only brands removed (they caused false positives); commonly impersonated brands
  added; the brand must lead the display name.
- **New detections:** combosquatting (a known name plus a risk word); link text showing a brand domain is
  no longer excused by an own-domain or bulk-mail guard.
- **Attachment rule:** macro documents and password-protected archives are strong only from unfamiliar
  or unauthenticated senders.
- **Forwarded content (F-18):** content forwarded by known, authenticated colleagues is treated as reported.
- **Sign-in link rule (S-L):** a sign-in request with a link to an unrelated, never-seen domain is
  Suspicious only.
- **Request phrasing:** "update the beneficiary", two-sentence bank changes, single spaced-out words.

## 5. Limitations

- **Same author for engine and both datasets:** shared blind spots are possible. v2 was written after
  the freeze, with new scenario types, to reduce this, but an external or real corpus is the real test.
- **Balanced classes; small categories; template-based variation; simulated relationship context.**
- **v2 is now spent as a holdout:** any further tuning informed by these results must be validated on
  yet another new holdout.

## 6. Recommended next steps (not applied; v2 must stay an untouched holdout)

1. A broader, intent-based request taxonomy (approvals, fees, portals, acknowledgements), validated on a
   new holdout.
2. Destination novelty for *any* call to action, not only sign-in requests, with an allow-list of the
   organization's identity providers to avoid the observed false positive.
3. Add organization-specific words (`hr`, `people`, `it`) to the combosquatting check.

## 7. Reproduce

```bash
python3 eval/v2/generate.py                       # identical dataset (seeded)
cd backend && uv run python ../eval/run.py v2     # checks the frozen engine hash, then evaluates
```

Machine-readable: `eval/metrics.json` (primary, dashboard-ready, includes the historical v1 summary),
`eval/v2/results.jsonl`, `eval/v2/metrics.json`, `eval/v2/results_original_engine.json`.
