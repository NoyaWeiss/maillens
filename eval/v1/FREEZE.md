# Phase 5 engine freeze

- Frozen engine commit: `00bb9d1e041b0e9761c4ee28eb37741a2a576d0a`
- SHA-256 (first 16 hex) of `backend/app/*.py` + `backend/app/signals/*.py`: `8ef706999ca4add2`
- Frozen on 2026-11-12, before the evaluation dataset was generated or run.
- Alert policy (fixed now): **Suspicious or High = detected (alert); Low = not detected.**
  **Inconclusive** is reported separately; primary metrics treat it as *not detected*, and a
  sensitivity view excludes it.
- No detection rule, threshold or label may change after the first evaluation run.
  `eval/run.py` checks the hash above and refuses to report if the engine changed.
