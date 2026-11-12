"""Read-only view of the latest committed evaluation (eval/metrics.json) for the dashboard.

Nothing is recomputed or hardcoded here: values come from the committed artifacts. Only the primary
(latest) benchmark is returned in full; earlier rounds are returned as labelled history."""

import json
import os
from functools import lru_cache
from pathlib import Path

EVAL_DIR = Path(os.environ.get("MAILLENS_EVAL_DIR", Path(__file__).resolve().parents[2] / "eval"))


def _split(table: dict) -> list[dict]:
    out = []
    for key, frac in table.items():
        label, name = key.split("|", 1)
        k, n = (int(x) for x in frac.split("/"))
        out.append({"label": label, "name": name, "alerts": k, "n": n})
    return out


@lru_cache
def load() -> dict:
    m = json.loads((EVAL_DIR / "metrics.json").read_text())
    primary = m["primary_evaluation"]
    p = m[primary]
    return {
        "benchmark": primary,
        "engine": p.get("engine", ""),
        "note": m.get("note", ""),
        "overall": p["overall"],
        "by_category": _split(p["by_category"]),
        "by_difficulty": _split(p["by_difficulty"]),
        "baseline": m.get(f"{primary}_engine_comparison", {}),
        "history": [{"benchmark": k, "label": v.get("label", ""), "metrics": v.get("metrics", {})}
                    for k, v in m.get("history", {}).items()],
    }
