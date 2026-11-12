# MailLens: Phase 3 Security & QA Report

Date: 2026-11-11, updated 2026-11-12 (Phase 3b) · Scope: add-on (Apps Script), backend (FastAPI), configuration, data flow, demo mailbox.
Builds tested: add-on **production build** (no developer tools) pushed at 15:56; backend at commit `a1b5c03`+.

## 1. Executive summary

MailLens passed the Phase 3 review with **no open critical or high-severity issues**. The review
found and fixed **7 defects** (F-01 to F-07), two of them Medium:
- request quotes showed live, potentially clickable phishing URLs
- quotes glued the Subject onto the Body and cut words in half, misrepresenting the evidence

**Detection behaves as specified:**
- All 10 demo scenarios produce the expected verdict **in real Gmail**.
- In a new 28-case edge suite, 16 of 17 hard negatives stay Low and all 9 attacks reach their expected level.
- The one false positive (a newsletter *describing* a bank-detail scam is rated Suspicious) is documented
  and awaits an owner decision.

**Before the demo, these residual items remain:**
- switch the backend to production mode
- choose stable hosting (this also unblocks the outbound URL allow-list)
- accept that an occasional Gmail API stall, observed once at 32.5 s, can still exceed Gmail's 30 s limit

| Severity | Found | Fixed | Open |
|---|---|---|---|
| Critical | 0 | 0 | 0 |
| High | 0 | 0 | 0 |
| Medium | 5 | 2 | 3 (residual or pending a decision) |
| Low | 8 | 5 | 3 (F-10 accepted, F-13 residual, F-16 pending a decision) |
| Informational | 4 | – | accepted, documented |

## 2. Methodology and scope

| Method | What it covers | Evidence type |
|---|---|---|
| Code review | Every place untrusted data enters a widget or the backend; OAuth scopes; outbound fetches; logging; dev-only paths | Manual |
| Backend automated tests (pytest) | Signals, decision invariants, scenarios, presentation, grounding, adversarial input, API security | **Automated, mocked input** |
| Add-on automated tests (node) | Card rendering through a strict CardService double, escaping, Variant C isolation, failure paths, payload limits | **Automated, mocked Gmail** |
| Contract test | The real add-on payload builder (mocked Gmail) posted to the **live** backend, on both permission paths | **Replayed integration** |
| Public-endpoint checks | `curl` against the Cloudflare tunnel | **Real network** |
| Real Gmail | Analyses, probes and status checks from Google's servers, evidenced by backend logs and owner screenshots | **Real Gmail** |

Real-Gmail claims below are made **only** where the backend log shows a request from Google's
address ranges, the owner observed the card, or the developer probe reported it.

## 3. Security findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| F-01 | Medium | Request quotes contained **live URLs and host names** (e.g. `https://evil.example/login`); Gmail may render URLs in card text as links, so the tool could hand the user the phishing link | **Fixed:** all quoted text is defanged (`hxxps://evil[.]example`); test `test_nothing_rendered_is_a_live_link` |
| F-02 | Medium | Quotes were cut from "subject + body" with a fixed 40-char window: subject glued onto body, words cut ("INV-22", "Please si"), and matches in the subject quoted as body text | **Fixed:** quote = whole sentence(s) from **one** source, labelled Subject/Body, word-boundary truncation, body preferred; test `test_quote_is_verbatim_from_one_source` |
| F-03 | Low | Evidence labelled "Sender" when it concerned the Reply-To; ambiguous for an analyst | **Fixed:** labels are From / Reply-To / Display name / Earlier messages from this From address |
| F-04 | Low | OAuth scope `userinfo.email` declared but never used | **Fixed:** removed; live manifest now has 5 scopes |
| F-05 | Low | Dev-only handlers (probe, direction test, render tests) had no build guard | **Fixed:** each returns "not available" outside dev builds |
| F-06 | Low | Rate limiter kept one entry per client address forever (memory growth) | **Fixed:** bounded at 10,000 clients with idle and least-recent eviction; test added |
| F-07 | Low | Data placed in **plain-text labels** (category, evidence tags, detail labels) was not sanitized, relying on undocumented renderer behaviour | **Fixed:** angle brackets stripped from label data; test renders every response with hostile strings in **every** field and asserts no markup survives |
| F-08 | Medium | Backend currently runs in **dev mode**: the probe-report endpoint is enabled (API key still required) and logs carry demo labels and client timings | **Open, action before demo:** `MAILLENS_ENV=prod scripts/dev.sh` (implemented and tested) |
| F-09 | Medium | Manifest has no `urlFetchWhitelist`, so the add-on could fetch any HTTPS URL entered in settings | **Open:** needs the stable backend hostname (hosting decision) |
| F-10 | Low | API key is in the generated, gitignored `Secrets.js`, pushed to the **private** Apps Script project; anyone with edit access to that project can read it | **Accepted for the prototype.** Production: per-user property only, or a per-deployment secret |
| F-11 | Info | Only the topmost `Authentication-Results` from `mx.google.com` is trusted. That's correct for Gmail-delivered mail, but inserted or imported mail (our demo mailbox) can carry a sender-written header in that position | **Documented:** demo mailbox headers are simulated (README disclosure) |
| F-12 | Medium | A Gmail API call in a **required** step was once measured at **32,481 ms**; Apps Script can't time-bound it, and Gmail stops at ~30 s ("Unable to load content") | **Residual risk:** "Try again" on the error card; warm-up before the demo; see RELIABILITY.md |
| F-13 | Low | `UrlFetchApp` has no configurable timeout, so a hung backend would hit Gmail's 30 s limit | **Residual:** backend is stateless and responds in ms |
| F-14 | Info | The per-user Google cache holds the last analysis result (10 min) and the message token (5 min) | **Accepted:** user-scoped; needed for "View detailed analysis" and "Re-analyze" |
| F-15 | Info | Rate limiting is keyed by source IP; all add-on traffic arrives from Google egress addresses | **Accepted for the prototype** |
| F-16 | Low | Detection false positive: a newsletter *describing* a scam → Suspicious (A=3) | **Fixed in Phase 3b** (RC5): described, quoted-example or negated requests are ignored, but **never** when the sentence also addresses the reader directly; abuse-resistance tests included; not tied to bulk headers |
| F-17 | Info | Git commits carry the author's personal email, which becomes public on publish | **Owner decision before publishing:** switch to a GitHub noreply address |

### Verified controls (PASS)

| Control | Evidence |
|---|---|
| API key required on `/v1/analyze` and `/v1/status`; constant-time comparison | 401 without key, both locally and **over the public tunnel** |
| Rate limit checked before authentication (key guessing is throttled) | `test_rate_limit_rejects_after_quota_and_runs_before_auth` |
| Request-size cap | **413 for a 2 MB body over the public tunnel**; field and list limits return 422 |
| No API docs or schema exposed | `/docs` and `/openapi.json` return 404 **over the tunnel** |
| No stack traces or echoed input in errors | malformed JSON and types tests; validation errors list field paths only |
| No outbound network calls from the backend | every test runs with sockets blocked; the public suffix list is bundled |
| Algorithmic-complexity resistance | hostile HTML, style, header and anchor inputs each under 2 s (test suite); a 19 s nested-HTML case was found and fixed in Phase 1 |
| Prompt-injection resistance | no LLM; hidden "this email is safe / ignore instructions" text *raises* the verdict (level-3 finding); visible injection text never lowers it (`test_injected_instructions_never_lower_the_verdict`) |
| HTML/script injection into cards | every value HTML-escaped (text) or bracket-stripped (labels); hostile-field rendering test |
| Log privacy | backend logs only request ID, verdict, gate, vector and signal IDs; `test_logs_never_contain_email_content` |
| Secrets not in git | `.env`, `Secrets.js`, `.clasp.json` gitignored; staged-diff scan finds no key value before every commit |
| Least-privilege OAuth | 5 scopes; `gmail.readonly` optional with graceful fallback; `gmail.metadata` rejected on **probe evidence** (it blocks reading the open email's body) |
| Developer tools absent from the demo build | production build verified live: `"dev": false`, guarded handlers, no dev UI |

## 4. Bugs found and fixed during Phase 3

Covers F-01 to F-07 above. All fixes are covered by new regression tests. The decision snapshot test
(`test_golden.py`) still passes, so **no verdict, risk index, gate or vector changed**.

## 5. Detection correctness

| Check | Result |
|---|---|
| Spec 4.1 per-signal must-fire / must-not-fire table | PASS (automated) |
| Engine invariants INV-1..6 (exhaustive grid) | PASS (automated) |
| Spec 3.6 worked outcomes on the 13 demo emails | PASS (automated) **and** observed in real Gmail (table in section 7) |
| Weak signals alone never reach High | PASS (INV-1 plus edge-suite assertion) |
| Correlated findings not double-counted (one entity, one count) | PASS (R1/R3 tests; T7 shows one sender entity) |
| Relationship-aware cases: known contact, new address on the same domain, ambiguous name, freemail impersonation | PASS (signal tests + edge suite + live T4 backup) |
| High-impact request without links (T6, gift cards, CEO wire) | PASS: Suspicious from a known sender; High with corroboration (H-C) |
| Inconclusive only under its single rule | PASS (INV-6; T9 live) |
| Unavailable vs. not applicable distinguished | PASS (check states with plain reasons) |

### Edge-case suite (28 cases, written before the first run)

| Group | Cases | Matched expectation | Notes |
|---|---|---|---|
| Hard negatives | 17 | 16 | Contractor on personal Gmail, password reset, code delivery, calendar, mailing list, help-desk Reply-To, known vendor PDF invoice, same-domain new address, bulk shortener, DocuSign "via", IT portal, forwarded without auth, PayPal receipt, ESP-tracked link, payslip, "Re:" without references stay **Low**. **1 false positive: F-16** |
| Attacks | 9 | 9 | Gift cards (H-C), CEO wire (H-C), IP-literal link, `user@host` trick, double extension, DMARC reject fail, corporate→freemail Reply-To, MFA-code relay, `rn`→`m` look-alike all reach their expected level |
| Known blind spots | 2 | 2 (stay Low, as documented) | Plain-text phish from attacker infrastructure with clean authentication; QR-code image phish |

**False negatives (by design, documented):**
- A first-contact, plain-text credential request with valid authentication and no deceptive
  construct is Low with advice.
- Text in images is not read.
- No threat-intelligence or URL reputation lookups.

These figures are a sanity check on self-authored cases, **not** a detection-accuracy benchmark
(that's Phase 5).

## 6. Explanation and evidence integrity

| Requirement | Status | Test |
|---|---|---|
| Observed facts separate from inference (no "fraud/attacker/compromise…" in observed statements) | PASS | `test_observed_statements_contain_no_inference` |
| From and Reply-To never confused | PASS | `test_reply_to_evidence_matches_headers`, label assertions |
| Quotes verbatim from one source, never Subject+Body | PASS (fixed F-02) | `test_quote_is_verbatim_from_one_source` |
| Attack categories hedged unless an observed fact | PASS | `test_main_card_rules` |
| Risk index never presented as a probability | PASS | `test_risk_index_is_never_a_probability` |
| Coverage not presented as confidence | PASS | Detailed analysis states "completed checks show what was examined, not how certain the verdict is" |
| Presentation can't change a decision | PASS | `test_golden.py` decision snapshot |
| Exact evidence available for audit | PASS | Detailed analysis → Evidence (collapsed) |
| Detailed analysis content redesign (case-specific explanation, "what it may mean / doesn't establish") | **NOT DONE**: proposal awaiting owner approval (Phase 2 item) | – |

## 7. Real Gmail integration results

Source: backend logs (requests from Google address ranges, scenario labels in dev mode) and owner observations.

| Scenario | Expected | Observed in Gmail |
|---|---|---|
| T1 billing-platform invoice | Low | Low (4 runs) |
| T2 sign-in alert | Low | Low (2) |
| T3 newsletter | Low | Low (2) |
| T4 backup name collision | High · H-B | High · H-B (2) |
| T5 Reply-To changed mid-thread | High · H-B | High · H-B (19) |
| T6 bank change, known vendor | Suspicious · S-A | Suspicious · S-A (1) |
| T7 look-alike domain | High · H-A | High · H-A (2) |
| T8 hidden scanner text | High · H-A | High · H-A (2) |
| T9 forwarded, no authentication | Inconclusive | Inconclusive (4) |
| H2 history reply | Low | Low (1) |

- **Analyses from Google:** 56. **Welcome-screen status checks from Google:** 5, all 200.
- **Latency** (38 timed runs, Apps Script time before the backend call): median **298 ms**, p90 **564 ms**,
  max **1,635 ms**. One relationship cache miss: **1,082 ms**. Full path including the backend
  (probe G8, 5 runs): **592–844 ms**.
- **Feasibility probe (real Gmail):** G1 headers, G1b body, G2 sent-mail headers, G3 thread headers,
  G6 rendering, G7 reachability and G8 full path all PASS under the final permissions.
- **Earlier incidents seen in Gmail and fixed:**
  - empty card section → "Unable to load content" (T1)
  - `gmail.metadata` blocking body reads
  - an invalid `script.locale` setting
  - a duplicate function shadowing a card section

### NOT VERIFIED in real Gmail (covered by automated tests only)

| Behaviour | Automated coverage |
|---|---|
| Backend unreachable / 5xx / 401 / 429 error card | `errors.test.js`, strict card tests |
| Re-analyze after the 5-minute message token expires | `errors.test.js` |
| Optional permission declined, **with the current UI** | Contract test "no mailbox scope". The old UI was observed working without the permission at 13:43 |
| Very long threads, large mailboxes (relationship build with 100 sent messages) | `payload.test.js` (60-message thread); large-mailbox timing unmeasured |
| Recurrence of the Gmail API stall | Observed once; frequency unknown |
| Hebrew-Gmail rendering of the **latest** Detailed analysis and Welcome screens | Strict card tests; the owner has reviewed earlier iterations |

## 8. Automated test results (final run)

| Suite | Result |
|---|---|
| Backend (pytest) | **226 passed**, 0 failed (final, 2026-11-12) |
| Add-on (node --test) | **73 passed**, 0 failed (final, 2026-11-12) |
| Contract (real add-on payload → live backend) | 2/2 paths OK |
| Public-endpoint checks | healthz 200 · analyze/status without key 401 · docs/openapi 404 · 2 MB 413 |

## 9. Known limitations and residual risks

- **Gmail API stalls** (F-12) and the **lack of a fetch timeout** (F-13) can produce "Unable to load content".
- **Quick tunnel:** no SLA, and the URL changes on restart (hosting pending).
- **Blind spots:** plain-text phish with clean authentication; image-based content; no reputation data; English-only request patterns.
- **Relationship checks need `gmail.readonly`,** which is broad. The code reads only Sent-mail headers and the open email.
- **Demo mailbox authentication headers are simulated** (Gmail's insert API performs no checks).
- **The edge suite is self-authored**, a sanity check rather than a benchmark.

## 10. PASS / FAIL / NOT VERIFIED

| Requirement | Status |
|---|---|
| Untrusted input validated and bounded | PASS |
| Malformed, nested, oversized and unusual-encoding input handled | PASS |
| Prompt-injection content can't lower a verdict | PASS |
| No SSRF from the backend (no outbound calls) | PASS |
| Add-on outbound fetch restricted to an allow-list | **FAIL (open, F-09)**: needs stable hostname |
| HTML/script injection into cards prevented | PASS |
| API authentication enforced | PASS (incl. over the public tunnel) |
| Rate limiting and size limits | PASS |
| Secrets kept out of git and the UI | PASS |
| Log privacy | PASS |
| Least-privilege scopes | PASS (with the documented `gmail.readonly` trade-off) |
| No developer diagnostics in the demo build | PASS (add-on) / **OPEN (backend dev mode, F-08)** |
| Demo scenarios correct in real Gmail | PASS (10/10) |
| Hard negatives stay Low | PASS 17/17 (F-16 fixed in Phase 3b) |
| Explanations grounded and hedged | PASS |
| Error states in real Gmail | NOT VERIFIED |
| Hebrew-Gmail rendering of the latest Detailed analysis and Welcome screens | NOT VERIFIED (pending owner review) |

## 11. Readiness checklist (live demo)

- [x] All automated suites green
- [x] Production add-on build live, no developer tools
- [x] All 10 demo scenarios verified in real Gmail
- [x] No secrets in git
- [ ] Backend restarted with `MAILLENS_ENV=prod` (F-08)
- [ ] Stable hosting chosen; `urlFetchWhitelist` added (F-09)
- [x] F-16 fixed (Phase 3b, RC5)
- [ ] Owner decisions: F-18 (forwarded content), F-19 (pretext + secrecy rule), F-09 option A
- [ ] Owner visual approval of the Detailed analysis content (Phase 2 item) and the Welcome screen
- [ ] Optional: one real-Gmail error-state check (stop the backend, open an email, see "unreachable", restart)
- [ ] Warm-up run before presenting (open one email to populate caches)
- [ ] Before publishing: switch the commit email to a GitHub noreply address (F-17)


## 12. Phase 3b: targeted development testing (pre-registered cases)

**These 41 cases are development and regression tests, not an independent benchmark.** The fixes below
were designed from these same cases, so the improvement shows the fixes work on the patterns they
target. It is **not** an estimate of real-world accuracy (see `docs/TESTING_PLAN.md`; Phase 5).

### Protocol evidence (git)

| Step | Commit |
|---|---|
| Cases, labels, reasons and expected evidence written; evaluation policy fixed | `636c9e2` (before any run) |
| Baseline with **no rule changes** | `811445d` (`docs/phase3/baseline.json`) |
| Narrow fixes and post-fix results | `fccb27c` (`docs/phase3/postfix.json`) |

Policy: Suspicious/High = detected; Inconclusive is its own outcome, never counted as correct;
Ambiguous cases get no correctness judgement.

### Results

| | Baseline | After fixes |
|---|---|---|
| Malicious (20): detected | 11 | **15** |
| Malicious: false negatives | 9 | **5** |
| Legitimate (17): correct Low | 14 | **16** |
| Legitimate: false positives | 3 | **1** |
| Inconclusive | 0 | 0 |
| Ambiguous (4) | all Low | all Low (explanations reviewed: no overclaiming) |
| Demo-scenario decisions (snapshot test) | – | **unchanged** |

| Case | Label | Category | Baseline | After fixes |
|---|---|---|---|---|
| P3-01 | Malicious | credential phishing / brand impersonation | HIGH (correct) | HIGH (correct) |
| P3-02 | Malicious | BEC / payroll diversion | HIGH (correct) | HIGH (correct) |
| P3-03 | Malicious | malware delivery | SUSPICIOUS (correct) | SUSPICIOUS (correct) |
| P3-04 | Malicious | cousin-domain vendor fraud | HIGH (correct) | HIGH (correct) |
| P3-05 | Malicious | gift-card scam | LOW (FN) | HIGH (correct) |
| P3-06 | Malicious | vendor thread hijack (subtle) | SUSPICIOUS (correct) | HIGH (correct) |
| P3-07 | Malicious | CEO fraud pretext | LOW (FN) | LOW (FN) |
| P3-08 | Malicious | OAuth consent phishing | LOW (FN) | HIGH (correct) |
| P3-09 | Malicious | compromised known contact | LOW (FN) | LOW (FN) |
| P3-10 | Malicious | homoglyph brand domain | HIGH (correct) | HIGH (correct) |
| P3-11 | Malicious | HTML smuggling attachment | SUSPICIOUS (correct) | SUSPICIOUS (correct) |
| P3-12 | Malicious | fake reply thread | LOW (FN) | LOW (FN) |
| P3-13 | Malicious | evasion: zero-width characters in request | LOW (FN) | HIGH (correct) |
| P3-14 | Malicious | evasion: homoglyphs in request text | LOW (FN) | HIGH (correct) |
| P3-15 | Malicious | evasion: request only in an image | LOW (FN) | LOW (FN) |
| P3-16 | Malicious | evasion: reported speech hides a real request | SUSPICIOUS (correct) | SUSPICIOUS (correct) |
| P3-17 | Malicious | evasion: request hidden in fake quoted history | SUSPICIOUS (correct) | SUSPICIOUS (correct) |
| P3-18 | Malicious | prompt injection + credential phish | HIGH (correct) | HIGH (correct) |
| P3-19 | Malicious | evasion: attacker adds bulk headers | HIGH (correct) | HIGH (correct) |
| P3-20 | Malicious | plain-text credential phish (clean infrastructure) | LOW (FN) | LOW (FN) |
| P3-21 | Legitimate | internal colleague | LOW (correct) | LOW (correct) |
| P3-22 | Legitimate | order confirmation (bulk) | LOW (correct) | LOW (correct) |
| P3-23 | Legitimate | routine vendor invoice | LOW (correct) | LOW (correct) |
| P3-24 | Legitimate | developer platform notification | LOW (correct) | LOW (correct) |
| P3-25 | Legitimate | security newsletter describing BEC (F-16) | SUSPICIOUS (FP) | LOW (correct) |
| P3-26 | Legitimate | internal awareness email quoting a scam | SUSPICIOUS (FP) | LOW (correct) |
| P3-27 | Legitimate | genuine vendor bank change, known vendor | LOW (correct) | LOW (correct) |
| P3-28 | Legitimate | urgent request from a known manager | LOW (correct) | LOW (correct) |
| P3-29 | Legitimate | help-desk ticket with platform Reply-To | LOW (correct) | LOW (correct) |
| P3-30 | Legitimate | e-signature request via platform | LOW (correct) | LOW (correct) |
| P3-31 | Legitimate | internal password-expiry notice | LOW (correct) | LOW (correct) |
| P3-32 | Legitimate | employee forwards a phish to IT | HIGH (FP) | HIGH (FP) |
| P3-33 | Legitimate | first invoice from a new vendor | LOW (correct) | LOW (correct) |
| P3-34 | Legitimate | marketing with urgency and shortened links | LOW (correct) | LOW (correct) |
| P3-35 | Legitimate | colleague mobile reply with macro spreadsheet | LOW (correct) | LOW (correct) |
| P3-36 | Legitimate | HTML receipt from known merchant | LOW (correct) | LOW (correct) |
| P3-37 | Legitimate | account notice with link on own domain | LOW (correct) | LOW (correct) |
| P3-38 | Ambiguous | cold availability probe | LOW (ambiguous) | LOW (ambiguous) |
| P3-39 | Ambiguous | vendor rebrand to new domain | LOW (ambiguous) | LOW (ambiguous) |
| P3-40 | Ambiguous | forwarded delivery notice without authentication | LOW (ambiguous) | LOW (ambiguous) |
| P3-41 | Ambiguous | recruiter with password-protected archive | LOW (ambiguous) | LOW (ambiguous) |

### Root causes and fixes

| RC | Pattern | Cases | Fix (with regression tests) |
|---|---|---|---|
| RC1 | Request phrasing gaps: "I **need** … gift cards", "**updated remittance instructions**", "sign in **with your email account**" | P3-05, P3-06, (P3-09) | Patterns extended; each with should-match/should-not-match examples |
| RC2 | Invisible characters or Cyrillic look-alike letters inside words defeat matching | P3-13, P3-14 | Matching runs on a normalized copy; disguised wording is itself level-2 evidence (≥2 words; soft hyphens, emoji and real Cyrillic/Greek text excluded) |
| RC3 | A brand name on a **free-mail** address passed ("Google Docs" from gmail.com), because free-mail counted as brand-owned | P3-08 | Free-mail is never treated as an official brand sender |
| RC4 | OAuth consent links requesting mailbox access weren't recognized | P3-08 | S10 sub-check (level 2) for Google/Microsoft authorization URLs with mail scopes; identity-only SSO stays clean; new "Possible consent phishing" category |
| RC5 | Described, quoted or negated requests read as real requests (**F-16**) | P3-25, P3-26 | Reported-speech guard, overridden by any direct address to the reader in the same sentence |
| – | Misleading explanation: "asks you to sign in" for emails that don't | P3-08 | Sign-in wording only when a sign-in request was detected |

### Still wrong after the fixes, and why (not fixed in Phase 3b)

| Finding | Cases | Root cause | Proposal / decision needed |
|---|---|---|---|
| **F-18** (FP, Low) | P3-32: an employee forwards a phish to IT and gets **High** | RC6: forwarded content inside the body is evaluated as the forwarder's own | Owner decision. Discounting forwarded content would also weaken detection when a compromised colleague forwards a phish. A safer option: keep the verdict, but explain "the deceptive content is inside a forwarded message" |
| **F-19** (FN, Medium) | P3-07 CEO pretext, P3-12 fake "Re:", P3-09 compromised contact | RC7: by design a level-2 request plus weak signals never escalates (the spec removed that rule to avoid flagging real sign-in alerts) | Proposal: Suspicious only for **pretext** requests (unexplained favor, move off email) **plus secrecy plus unfamiliar sender**. P3-38 (Ambiguous, no secrecy) would stay Low. Owner decision |
| F-20 (FN, Low) | P3-17 (detected via other signals, but the request was missed) | RC8: quoted history is stripped before request matching, so an attacker can put the instruction in fabricated quoted text | Proposal: scan quoted text when the visible part points to it ("as discussed below"), capped at Suspicious |
| Documented blind spots | P3-15 (request only in an image), P3-20 (plain-text phish, clean infrastructure) | Out of scope: no OCR, no reputation data | None in Phase 3 |

## 13. Git history and publishing privacy (assessed 2026-11-12, read-only)

| Check | Result |
|---|---|
| Published | **No remote configured;** 15 local commits |
| Personal email | In **commit metadata only** (author/committer on all 15 commits); **0** occurrences in file contents |
| Test-account address in files | 0 |
| API key, OAuth tokens, private keys in any commit | **None.** Only field names in `scripts/gas_api.py`, which reads clasp's local token file at runtime |
| Sensitive files ever committed | None |

Remediation (needs owner approval and the GitHub noreply address): set the noreply email, then rewrite
the author on the 15 **unpublished** local commits before the first push. No published history is affected.

## 14. Phase 3 status

**Phase 3 is NOT complete.** Remaining:

| Item | Needs |
|---|---|
| Real-Gmail backend-unavailable test | Owner in Gmail (guided) |
| Decisions on F-18, F-19, F-09 option A | Owner |
| Backend switched to production mode (F-08) | Just before the demo (it removes the scenario labels used to verify reviews) |
| Phase 2 visual approvals (Welcome screen; Detailed analysis content proposal) | Owner (kept open; not part of Phase 3) |


## 15. Phase 3 close-out (2026-11-12)

### Incidents found during close-out and fixed

| Issue | Root cause | Fix | Verified |
|---|---|---|---|
| Gmail showed "Analysis service unavailable" | (1) Cloudflare deleted the quick tunnel overnight. (2) `dev.sh` saved "Binary file matches" instead of the URL. (3) **A URL saved earlier in Advanced settings overrode every new deployment** | Fresh tunnel; `grep -a`; deployment config now always wins over saved settings, plus a regression test | **Real Gmail:** status check 200 and analyses from Google at 11:17 |
| F-08 backend in dev mode | Developer endpoint and labels enabled | Backend restarted in production mode | Public `/v1/dev/probe-report` returns 404 |
| F-09 add-on could fetch any URL | No manifest allow-list | Top-level `urlFetchWhitelist` = Gmail API + **exact** backend host, injected per installation at push time; saved URLs can't override the deployment | Accepted by Google's manifest validator and live in the deployed manifest. **Enforcement not directly observed:** run `verifyAllowList` in the Apps Script editor to confirm |
| F-19 pretext requests | Level-2 request plus weak signals never escalated | Narrow S-P gate: pretext plus explicit concealment plus unfamiliar sender = Suspicious only | Tests; 41 cases: malicious detected 15 → **16**, false positives unchanged (1) |

### Real-Gmail verification (observed, not mocked)

| Check | Result |
|---|---|
| Welcome screen "Analysis service ready" | PASS (status checks from Google: 200) |
| T5 → High risk; Detailed analysis opens | PASS (High via H-B in the log; owner confirmed both) |
| Backend outage → no verdict; Try again fails while down | PASS (owner observed; the tunnel returned 502) |
| Recovery → Try again returns the verdict | PASS (analysis from Gmail at 11:34:44 after restart, High via H-B) |

Outage/recovery test: **PASS**, confirmed by the owner in real Gmail on 2026-11-12.

### Final automated results
- Backend: 226 passed, 1 warning in 0.77s
- Add-on: ℹ pass 73 ℹ fail 0
- Contract test: 2/2 paths
- Clean-clone install test: PASS. Covered a fresh API key (owner key rejected), all suites passing in the clone,
  a Docker backend in production mode, the reviewer's own tunnel (public status 200, analysis OK), and the per-reviewer allow-list in a dry run.

### Verdict on Phase 3
**Complete, with documented limitations.** All critical and high items are fixed, and the critical
real-Gmail checks pass. Remaining, none of them blocking:
- F-09 enforcement still to be observed once (`verifyAllowList`)
- F-18 (forwarded-content false positive) and F-20 (instruction in fake quoted history) documented as limitations
- the occasional Gmail API stall (F-12)
- quick-tunnel URL changes (reviewers re-run `setup-addon.sh`)
- Phase 2 visual approvals (Welcome screen, Detailed analysis content proposal) remain open by the owner's decision
