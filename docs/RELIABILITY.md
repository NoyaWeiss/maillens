# Reliability and performance (Phase 1)

All numbers below were measured in real Gmail on the test account on 2026-11-11, from the
add-on's own step timer (`client_ms`, logged by the backend in dev mode only) and from the
developer feasibility probe. They are a small sample from one account and one network, not
a benchmark.

## Budget we design against

Gmail stops an add-on execution at about **30 seconds**. When that happens the user sees a
spinner and then "Unable to load content", and Gmail may retry. Our target is a verdict in
**under 2 seconds** in the normal case, and the design rule is that **only required steps may
delay the verdict**.

| Step | Required? | Budget behaviour |
|---|---|---|
| Open message (current-message token) | yes | none possible |
| Read headers of the open message (`format=metadata`) | yes | none possible |
| Read body + attachment metadata of the open message | yes | none possible |
| Thread digest (earlier messages' headers) | optional | skipped if the run has used more than 6 s |
| Relationship profile (Sent-mail headers) | optional | cached 1 h per user; skipped if the run has used more than 6 s |
| Backend call | yes | errors become a clear "no verdict" card |
| Render card | yes | validated offline by a strict CardService test double |

## Measured latency (9 analyses, scenarios T1–T9)

Time inside Apps Script **before** the backend call:

| Step | Median (ms) | Max (ms) |
|---|---|---|
| open message | 54 | 621 |
| headers (`format=metadata`) | 73 | 119 |
| thread digest | 91 | 180 |
| body + attachments | 51 | 685 |
| relationship (cache hit) | 31 | 42 |
| **total before backend** | **291** | **1,635** |

The full path including the backend round trip, measured by the probe's G8 check on five
emails: **592–844 ms**. The backend health round trip through the tunnel: 350–565 ms (nine samples).

## The observed 32.5-second stall

One probe run on T1 measured a single Gmail API call (`users.messages.get`, `format=metadata`)
at **32,481 ms**. The same call took 54–121 ms in every other measurement (11 samples), before
and after. It happened inside the developer probe, not in an analysis, so the user-facing card
was not affected that time.

What it means:
- It was a delay inside Google's Gmail API, not in MailLens code: the same call was fast seconds earlier and later.
- Apps Script offers **no timeout** for a single Gmail service call, so a stall in a *required*
  step cannot be cut short. If it hit the analysis, the execution would exceed 30 s and Gmail
  would show "Unable to load content".
- With one occurrence in about 20 calls we cannot estimate its frequency.

## Root cause of the earlier "Unable to load content" on T1 (fixed)

Not latency. T1 has no findings but a level-1 request, and the card built an empty
"Claim vs. Reality" section. Gmail rejects an empty section **at render time, after our code
returns**, so our error handling never saw it, and Gmail retried repeatedly. Fixed by never adding
empty sections or empty labels. A strict CardService test double now renders every card for all
13 real backend responses and fails on any such defect. Verified afterwards in Gmail: T1 renders,
and the retry loop is gone.

## Practical mitigations (low complexity)

| Mitigation | Effect on the stall | Cost | Status |
|---|---|---|---|
| Optional checks skipped after 6 s | stall in an optional step cannot block the verdict | none | done |
| Relationship profile cached 1 h | removes the largest optional cost from most runs | none | done |
| **"Try again" button on the error card** | one click recovers from a transient stall or backend hiccup | small | proposed for Phase 2 |
| Warm-up before a demo (open one email first) | caches and tokens are fresh | none | demo checklist |
| Read open-message headers via GmailApp first, API as fallback | only helps if the API path is the one that stalls; a fallback cannot interrupt a stall already in progress | small | not justified by one sample; revisit if it recurs |

## Remaining risks

- A Gmail API stall in a required step still produces "Unable to load content" (see above).
- The first email after the cache expires pays the relationship build (one list call plus up to
  100 header fetches, done in parallel); not yet measured on a large mailbox.
- The backend currently runs behind a Cloudflare quick tunnel; its URL changes on restart and it
  has no uptime guarantee (cloud hosting is out of scope; see the README).
