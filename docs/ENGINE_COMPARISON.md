# Engine comparison: v1, v2 and v3 engines on the v1, v2 and v3 datasets

> **Retrospective analysis, not a new benchmark.** Each frozen engine was rerun unchanged on each fixed
> dataset (per-case results in `eval/engine_comparison.json`). The three
> original pre-registered runs (each engine on its own holdout) reproduce **exactly**, case by case.
> All data is synthetic and balanced (100/100), so these aren't real-world accuracy figures.

Engines: v1 = `00bb9d1` (original), v2 = `97f93f8`, v3 = `c7ffff5` (latest).

## How to read each cell

| Status | Meaning |
|---|---|
| **DEV** | The engine was **tuned using this dataset**. Inflated by design; not evidence of generalization |
| **HOLDOUT** | The dataset was written **after** this engine was frozen, and was never used to tune it. Valid unseen-data evidence. The ★ cells are the original pre-registered runs; the others are retrospective reruns on data the engine never saw |

## Results (precision / recall / F1 / FPR; confusion matrix as TP/FN/FP/TN)

| Engine ↓ / dataset → | v1 dataset | v2 dataset | v3 dataset |
|---|---|---|---|
| **v1 engine** | ★ HOLDOUT · 0.863 / **0.69** / 0.767 / 0.11 · 69/31/11/89 (1 Inconclusive) | HOLDOUT · 1.00 / **0.42** / 0.592 / 0.00 · 42/58/0/100 | HOLDOUT · 1.00 / **0.37** / 0.540 / 0.00 · 37/63/0/100 |
| **v2 engine** | DEV · 0.977 / 0.86 / 0.915 / 0.02 · 86/14/2/98 | ★ HOLDOUT · 0.979 / **0.47** / 0.635 / 0.01 · 47/53/1/99 | HOLDOUT · 1.00 / **0.37** / 0.540 / 0.00 · 37/63/0/100 |
| **v3 engine** | DEV · 0.978 / 0.88 / 0.926 / 0.02 · 88/12/2/98 | DEV · 0.988 / 0.79 / 0.878 / 0.01 · 79/21/1/99 | ★ HOLDOUT · **1.00 / 0.40 / 0.571 / 0.00** · 40/60/0/100 |

## Like-for-like differences on identical cases (held-out cells only)

| Comparison (same dataset, both engines unseen) | Recall | FPR | Detections gained / lost | New false positives |
|---|---|---|---|---|
| v1 → v2 engine on **v2** | 0.42 → 0.47 | 0.00 → 0.01 | +5 / −0 | +1 |
| v1 → v2 engine on **v3** | 0.37 → 0.37 | 0.00 → 0.00 | 0 / 0 | 0 |
| v2 → v3 engine on **v3** | 0.37 → 0.40 | 0.00 → 0.00 | +3 / −0 | 0 |
| **v1 → v3 engine on v3** (cleanest overall comparison) | **0.37 → 0.40** | **0.00 → 0.00** | **+3 / −0** | **0** |

For contrast, the same engine changes measured on the data they were tuned on: v1 → v3 on the v1 dataset,
recall 0.69 → 0.88 and FPR 0.11 → 0.02; v1 → v3 on the v2 dataset, recall 0.42 → 0.79.

## What improved and what regressed (v1 engine → v3 engine, per dataset)

| Dataset | Improved | Regressed |
|---|---|---|
| v1 (DEV for v3) | 6 false positives removed on forwarded phish reports and 3 on account notices; more detections of brand-impersonation phishing (+5), compromised known contacts (+5), look-alike vendors (+4), attachments (+2), evasion (+2), payment redirection (+1) | none |
| v2 (DEV for v3) | fake invoice portal/QR (+6), MFA fatigue (+6), compromised partner (+6), investment scam (+6), HR-policy phishing (+5), notification lures (+4), escrow fraud (+3), new attachment types (+1) | **+1 false positive**: an internal IT notice whose sign-in link goes to an SSO domain |
| v3 (HOLDOUT for all three engines) | fake charity appeal (+3) | none |

**No engine version ever lost a detection that an earlier version had.** The only regression across all
600 case comparisons is one false positive on v2 data.

## Conclusions

1. **The engines did improve on the attack and look-alike types they were developed against.** That's
   real, permanent coverage: payment redirection variants, MFA approval, password disclosure,
   sensitive-data requests, combosquatting, forwarded reports.
2. **The improvement barely generalizes to attack types none of them were built for.** On the only
   dataset unseen by all three engines (v3), recall moved 0.37 → 0.37 → 0.40.
3. **Precision and FPR stayed excellent throughout** (1.00 / 0.00 on v3 for every engine). The changes
   added coverage without trading away false-positive control.
4. Therefore, **the honest headline is "a precise, explainable detector whose recall on genuinely novel
   attack types is about 40%"**, not "recall rose from 0.69 to 0.88". The latter is a development-data
   number.

The comparison ran each engine from a temporary checkout of its original commit. Those commit IDs no longer
exist after the author-email rewrite (contents unchanged), so the committed per-case results are the record.
The latest engine can be re-checked with `eval/reproduce.py`.
