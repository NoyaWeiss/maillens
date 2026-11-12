# MailLens roadmap (source of truth)

Agreed with the project owner on 2026-11-11. Priority: a reliable, polished Gmail add-on
over optional additions. Each phase ends with a verified status report.

| Phase | Scope | Status |
|---|---|---|
| 1. Reliability & performance | Measured latency, stall analysis, budgets, fallbacks, risks | Implemented and verified in Gmail; documented in [RELIABILITY.md](RELIABILITY.md) |
| 2. UI/UX refinement | CardService redesign: prominent verdict + score, concise reason, 2–3 findings, Claim vs. Reality, actions, Technical Evidence separate | Main card **approved in Gmail**. Welcome screen built (awaiting visual approval). Detailed analysis content proposal awaiting approval |
| 3. Quality & security verification | Gmail scenario re-verification, false-positive checks, tests, OAuth and secret-handling review, limitations | See [SECURITY_QA_REPORT.md](SECURITY_QA_REPORT.md) section 15 for final status |
| 4. Interactive security dashboard | Standalone React dashboard, aggregate threat activity, time-range slider (1 hour to 1 year, received time), privacy-conscious storage | **Built, awaiting owner visual review:** served by the backend at `/dashboard/`, opened from Gmail with a one-time launch code; see README Step 8 |
| 5. Detection performance evaluation | Independent synthetic dataset (200 cases, owner-adjusted), precision/recall/F1/FPR, confusion matrix, per-attack-type results, labelled synthetic | **Done:** three rounds (v1 → v2 → v3); each holdout written after its engine was frozen. Primary: v3. See [EVALUATION_REPORT.md](EVALUATION_REPORT.md) |
| 6. Final submission | README, architecture, threat model, **reproducible local setup** (Docker + reviewer's own tunnel), GitHub repo, interview demo | README and reviewer setup done and clean-install tested; GitHub publishing awaits owner approval. **Cloud hosting cancelled (2026-11-12):** reviewers run MailLens themselves |

## Standing rules

- No billing enabled and no paid resources created without explicit owner approval.
- The GitHub repository is not published without explicit owner approval.
- No broader OAuth scope without probe evidence and an owner decision.
- Nothing is called "working" without verification in real Gmail where it matters.
- Local commits are fine; secrets and the assignment documents never enter git.
