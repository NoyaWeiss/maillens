"""Writes real engine responses for every demo scenario to addon/tests/fixtures/responses.json,
so the add-on's card tests render exactly what the backend returns. Run: uv run python -m tests.dump_responses"""

import json
import os
from pathlib import Path

os.environ.setdefault("MAILLENS_API_KEY", "x" * 40)

from tests.test_scenarios import run  # noqa: E402

CASES = {
    "h2": dict(key="h2", thread=("h1",)), "h4": dict(key="h4", thread=("h3",)),
    "t1": dict(key="t1"), "t2": dict(key="t2"), "t3": dict(key="t3"), "t4b": dict(key="t4b"),
    "t5": dict(key="t5", thread=("h3", "h4")), "t6": dict(key="t6"), "t7": dict(key="t7"),
    "t8": dict(key="t8"), "t9": dict(key="t9"),
    "t6_no_relationship": dict(key="t6", relationship=False), "t1_no_relationship": dict(key="t1", relationship=False),
}

if __name__ == "__main__":
    out = {}
    for name, case in CASES.items():
        c = dict(case)
        out[name] = json.loads(run(c.pop("key"), **c).model_dump_json())
    path = Path(__file__).resolve().parents[2] / "addon" / "tests" / "fixtures" / "responses.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"wrote {len(out)} responses to {path}")
