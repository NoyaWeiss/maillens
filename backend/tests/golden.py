"""Decision snapshot used to prove that presentation-only changes never alter decisions.

`python -m tests.golden write` records the current decisions; test_golden.py compares against it.
Only decision fields are recorded (no wording), so text can evolve freely."""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MAILLENS_API_KEY", "x" * 40)

from tests.dump_responses import CASES  # noqa: E402
from tests.test_scenarios import run  # noqa: E402

PATH = Path(__file__).with_name("golden_decisions.json")


def decisions() -> dict:
    out = {}
    for name, case in CASES.items():
        c = dict(case)
        r = run(c.pop("key"), **c)
        out[name] = {
            "verdict": r.verdict, "score": r.score, "gate": r.gate, "vector": r.vector, "pathway": r.pathway,
            "confidence": r.confidence, "coverage": [r.coverage_ran, r.coverage_applicable],
            "findings": sorted([f.signal, f.group, f.entity, f.level, f.basis] for f in r.findings),
            "also_observed": sorted([f.signal, f.entity, f.level] for f in r.also_observed),
            "request_level": r.request.level if r.request else 0,
            "checks": {c.id: c.state for c in r.checks},
        }
    return out


if __name__ == "__main__" and sys.argv[1:] == ["write"]:
    PATH.write_text(json.dumps(decisions(), indent=1, sort_keys=True))
    print(f"wrote {PATH}")
