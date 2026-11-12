# Testing plan: development testing vs. independent evaluation

Adopted 2026-11-11 (owner requirement). Two strictly separated activities:

| | Phase 3: targeted development testing (now) | Phase 5: independent evaluation (later, after Phase 4) |
|---|---|---|
| Purpose | Find weaknesses, guide narrow rule fixes, prevent regressions | Estimate detection performance on unseen data |
| Size | ~30–50 labeled scenarios (+ existing scenario/edge suites) | ~300–500 new scenarios, if feasible |
| May the engine be tuned on it? | **Yes**, that's the point | **No.** Engine and thresholds are frozen before it is run |
| What results may claim | "On our development cases, before/after these fixes…" | Precision, recall, F1, FPR, confusion matrix, per-category results on **synthetic** data, with caveats |
| Location | `backend/tests/phase3/` | Separate directory, created in Phase 5; never imported by Phase 3 tests |

## Phase 3 protocol

1. **Pre-registration.** Every case is written with: ID, full synthetic input (headers, content, relationship
   history), ground-truth label (**Malicious / Legitimate / Ambiguous**), the reason for the label,
   category, and expected observable evidence. Cases and the evaluation policy are **committed to git
   before MailLens is run on them**. Labels describe the scenario's known intent and are never derived
   from MailLens output.
2. **Baseline.** Run the current engine with **no rule changes**; record the verdict, risk index, gate,
   findings and outcome for every case.
3. **Analysis.** Group failures by root cause (patterns, not single examples). Note misleading explanations too.
4. **Narrow fixes.** Propose each change with a justification, a regression test for the failure, and
   checks that it opens no important new gap. Re-run **all** suites (original scenarios, edge suite, Phase 3
   cases, decision snapshot) after each change.
5. **Reporting.** Publish baseline and post-fix results side by side, including cases still wrong.
   Results describe development cases only; **no accuracy claims**.

## Evaluation policy (fixed before the baseline run)

"Detected" means the verdict is **Suspicious or High**.

| Ground truth | LOW | SUSPICIOUS / HIGH | INCONCLUSIVE |
|---|---|---|---|
| Malicious | **False negative** (incorrect) | **Detected** (correct) | **Inconclusive** (not counted as correct) |
| Legitimate | **Correct** | **False positive** (incorrect) | **Inconclusive** (not counted as correct) |
| Ambiguous | no correctness judgement; the verdict and explanation are reviewed for honesty (no overclaiming) | same | same |

Secondary, informational only: for malicious cases with an irreversible request, note whether the
verdict reached High; for every case, note explanations that are misleading or unsupported.

A legitimate case that MailLens rates Suspicious **by design** (e.g. a genuine bank-detail change with
nothing else unusual: "verify out-of-band") still counts as a **false positive** under this policy.
The trade-off is reported, not hidden.

## Phase 5 plan (do not build yet)

- **Dataset:** 300–500 new synthetic scenarios, authored independently of the detection rules (written
  from attack and business-situation descriptions, not from signal definitions), covering diverse attack
  patterns, writing styles, sender contexts and legitimate look-alikes. No paraphrases of Phase 3 cases;
  a similarity check against Phase 3 is run before freezing.
- **Labels:** predefined, documented ground truth per case, with the reason, written before any run.
- **Freeze:** the engine version (git commit) and the verdict-to-outcome mapping above are frozen and
  recorded before the first run. No tuning on the holdout; any later engine change requires a new,
  separate holdout to report independent results.
- **Metrics:** precision, recall, F1, false-positive rate, confusion matrix (including Inconclusive as
  its own column), per-category results, and confidence intervals where counts allow.
- **Reproducibility:** one command regenerates all results from the frozen dataset and commit.
- **Caveats:** synthetic, self-authored data; not real-world detection accuracy.
- **Protecting independence now:** Phase 3 cases live only in `backend/tests/phase3/`. Phase 5 data will
  be authored in a separate directory and never used to tune the engine.
