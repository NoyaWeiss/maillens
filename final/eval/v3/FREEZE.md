# Phase 5c engine freeze (v3 holdout)

- Frozen engine commit: `c7ffff58d833acc2d5be2326261af12f15ce650e`
- Engine hash (eval/run.py engine_hash, first 16 hex): `bfab1e9020c98132`
- Frozen on 2026-11-12, BEFORE the v3 holdout was written. v1 and v2 were used as development data.
- Alert policy (unchanged): Suspicious or High = detected; Low = not detected; Inconclusive reported separately (counted as not detected in primary metrics).
- No rule, threshold or label may change after the first v3 run.
