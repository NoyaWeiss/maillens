# Phase 5d freeze (v4 benchmark)

- CANDIDATE engine (frozen): `20f0e5ef3ca974d12dd25b05e4d682784435fd04`, engine hash `08a5c374ad604dc1`
- BASELINE engine (previous frozen): `c7ffff58d833acc2d5be2326261af12f15ce650e`
- Both frozen BEFORE the v4 dataset was written (the candidate was designed only on v1, v2, v3 and the Phase 3 cases).
- Alert policy (unchanged): Suspicious or High = detected; Low = not detected; Inconclusive separate (counted as not detected).
- Decision rule (fixed now): keep the candidate only if recall gain >= 5 points with FPR increase <= 3 points and no category-level collapse; otherwise revert to the baseline.
- No rule, threshold, label or dataset change after the first v4 run.
