# MailLens roadmap (source of truth)

Agreed with the project owner on 2026-11-11. Priority: a reliable, polished Gmail add-on
over optional additions. Each phase ends with a verified status report.

| Phase | Scope | Status |
|---|---|---|
| 1. Reliability & performance | Measured latency, stall analysis, budgets, fallbacks, risks | Implemented and verified in Gmail; documented in [RELIABILITY.md](RELIABILITY.md) |
| 2. UI/UX refinement | CardService redesign: prominent verdict + score, concise reason, 2–3 findings, Claim vs. Reality, actions, Technical Evidence separate | **Next.** Layout proposal awaiting owner approval before implementation |
| 3. Quality & security verification | Gmail scenario re-verification, false-positive checks, tests, OAuth and secret-handling review, limitations | Not started (partially covered by existing tests) |
| 4. Interactive security dashboard | Standalone React dashboard, aggregate threat activity, 1H/24H/7D/30D selector, privacy-conscious storage | **Plan only, do not build yet** |
| 5. Detection performance evaluation | Independent synthetic dataset (300–500 cases), precision/recall/F1/FPR, confusion matrix, per-attack-type results, labelled synthetic | **Plan only, do not build yet** |
| 6. Final submission | README, architecture, threat model, stable hosting, GitHub repo, interview demo | Drafts allowed now; kept current as the product evolves |

## Standing rules

- No billing enabled and no paid resources created without explicit owner approval.
- The GitHub repository is not published without explicit owner approval.
- No broader OAuth scope without probe evidence and an owner decision.
- Nothing is called "working" without verification in real Gmail where it matters.
- Local commits are fine; secrets and the assignment documents never enter git.
