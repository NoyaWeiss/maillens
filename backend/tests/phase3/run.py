"""Runs the pre-registered Phase 3 cases and scores them with the fixed evaluation policy.

Usage: uv run python -m tests.phase3.run <label>   (writes docs/phase3/<label>.json and prints a table)
Ground truth comes only from tests/phase3/cases.py; this script never modifies it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("MAILLENS_API_KEY", "x" * 40)

from app.engine import analyze  # noqa: E402
from tests.factory import req  # noqa: E402
from tests.phase3.cases import CASES  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "docs" / "phase3"


def outcome(label: str, verdict: str) -> str:
    """Evaluation policy fixed in docs/TESTING_PLAN.md before the baseline run."""
    if label == "Ambiguous":
        return "ambiguous"
    if verdict == "INCONCLUSIVE":
        return "inconclusive"
    detected = verdict in {"SUSPICIOUS", "HIGH"}
    if label == "Malicious":
        return "correct" if detected else "FN"
    return "FP" if detected else "correct"


def run_all() -> list[dict]:
    rows = []
    for c in CASES:
        kw = dict(c["input"])
        r = analyze(req(kw.pop("from_header"), auth=kw.pop("auth", "pass"), **kw), "phase3")[0]
        rows.append({
            "id": c["id"], "label": c["label"], "category": c["category"], "verdict": r.verdict, "score": r.score,
            "gate": r.gate, "vector": r.vector, "outcome": outcome(c["label"], r.verdict),
            "signals": sorted({f.signal for f in r.findings}),
            "request": r.request.label if r.request else None, "request_level": r.request.level if r.request else 0,
            "headline": r.headline, "category_shown": r.category,
            "reasons": [x.title for x in r.reasons],
        })
    return rows


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    rows = run_all()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{label}.json").write_text(json.dumps({"engine_commit": commit, "results": rows}, indent=1))
    for r in rows:
        print(f"{r['id']} {r['label']:10} {r['outcome']:12} {r['verdict']:12} {str(r['gate']):4} {r['vector']:27} "
              f"{','.join(r['signals']):14} {r['request'] or ''}")
    from collections import Counter
    print("\nSUMMARY", dict(Counter((r["label"], r["outcome"]) for r in rows)))
