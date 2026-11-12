# Phase 5b engine freeze (v2 holdout)

- Frozen engine commit: `97f93f84225aca525ac4cc4ead7d6a6918b7627a`
- Engine hash (eval/run.py engine_hash, first 16 hex): `7a2e86f11ccd96f5`
- Frozen on 2026-11-12, after the improvements and BEFORE the v2 holdout was written.
- Alert policy (unchanged from v1): Suspicious or High = detected; Low = not detected; Inconclusive is
  reported separately (primary metrics treat it as not detected).
- No rule, threshold or label may change after the first v2 run.
