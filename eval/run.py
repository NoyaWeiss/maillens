"""Phase 5 blind evaluation of the FROZEN engine on eval/dataset.jsonl.

Usage (from repo root):  cd backend && uv run python ../eval/run.py
Outputs: eval/results.jsonl (per case), eval/metrics.json (aggregate, dashboard-ready),
         docs/EVALUATION_REPORT.md (generated sections). Refuses to run if the engine changed since the freeze.
"""

import collections
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("MAILLENS_API_KEY", "x" * 40)

from app.engine import analyze  # noqa: E402
from app.schemas import AnalyzeRequest  # noqa: E402

DETECTED = {"SUSPICIOUS", "HIGH"}


def engine_hash() -> str:
    files = sorted((ROOT / "backend/app").glob("*.py")) + sorted((ROOT / "backend/app/signals").glob("*.py"))
    # Same concatenation order as the shell command used for the freeze record (glob order per directory).
    data = b"".join(f.read_bytes() for f in files)
    return hashlib.sha256(data).hexdigest()[:16]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


def metrics(rows, inconclusive_as="not_detected"):
    rows = [r for r in rows if not (inconclusive_as == "exclude" and r["verdict"] == "INCONCLUSIVE")]
    det = lambda r: r["verdict"] in DETECTED
    tp = sum(1 for r in rows if r["label"] == "Malicious" and det(r))
    fn = sum(1 for r in rows if r["label"] == "Malicious" and not det(r))
    fp = sum(1 for r in rows if r["label"] == "Legitimate" and det(r))
    tn = sum(1 for r in rows if r["label"] == "Legitimate" and not det(r))
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else float("nan")
    fpr = fp / (fp + tn) if fp + tn else float("nan")
    return {"n": len(rows), "TP": tp, "FN": fn, "FP": fp, "TN": tn,
            "precision": round(prec, 3), "precision_ci95": wilson(tp, tp + fp),
            "recall": round(rec, 3), "recall_ci95": wilson(tp, tp + fn),
            "f1": round(f1, 3), "fpr": round(fpr, 3), "fpr_ci95": wilson(fp, fp + tn),
            "accuracy": round((tp + tn) / len(rows), 3) if rows else float("nan")}


def main():
    freeze = (ROOT / "eval/FREEZE.md").read_text()
    frozen = re.search(r"`([0-9a-f]{16})`", freeze).group(1)
    if engine_hash() != frozen:
        sys.exit(f"Engine changed since the freeze ({engine_hash()} != {frozen}); refusing to report.")

    cases = [json.loads(l) for l in (ROOT / "eval/dataset.jsonl").read_text().splitlines()]
    rows = []
    for c in cases:
        r = analyze(AnalyzeRequest.model_validate(c["input"]), c["id"])[0]
        rows.append({"id": c["id"], "label": c["label"], "category": c["category"], "family": c["family"],
                     "difficulty": c["difficulty"], "verdict": r.verdict, "score": r.score, "gate": r.gate, "vector": r.vector,
                     "signals": sorted({f.signal for f in r.findings}), "request": r.request.label if r.request else None,
                     "request_level": r.request.level if r.request else 0, "headline": r.headline,
                     "outcome": ("TP" if c["label"] == "Malicious" and r.verdict in DETECTED else
                                 "FN" if c["label"] == "Malicious" else
                                 "FP" if r.verdict in DETECTED else "TN"),
                     "inconclusive": r.verdict == "INCONCLUSIVE"})
    assert len(rows) == 200, len(rows)
    (ROOT / "eval/results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    primary = metrics(rows)
    excl = metrics(rows, "exclude")
    assert primary["TP"] + primary["FN"] == 100 and primary["FP"] + primary["TN"] == 100

    def by(key):
        out = {}
        for k in sorted({r[key] for r in rows}):
            rs = [r for r in rows if r[key] == k]
            lab = rs[0]["label"] if len({r["label"] for r in rs}) == 1 else "mixed"
            d = sum(r["verdict"] in DETECTED for r in rs)
            out[k] = {"label": lab, "n": len(rs), "alerts": d, "alert_rate": round(d / len(rs), 3),
                      "alert_rate_ci95": wilson(d, len(rs)), "inconclusive": sum(r["inconclusive"] for r in rs),
                      "verdicts": dict(collections.Counter(r["verdict"] for r in rs))}
        return out

    cats, diff = by("category"), {}
    for lab in ("Malicious", "Legitimate"):
        for dlev in ("easy", "medium", "hard"):
            rs = [r for r in rows if r["label"] == lab and r["difficulty"] == dlev]
            if rs:
                d = sum(r["verdict"] in DETECTED for r in rs)
                diff[f"{lab}/{dlev}"] = {"n": len(rs), "alerts": d, "alert_rate": round(d / len(rs), 3)}
    verdicts = {lab: dict(collections.Counter(r["verdict"] for r in rows if r["label"] == lab)) for lab in ("Malicious", "Legitimate")}
    gates = {lab: dict(collections.Counter(str(r["gate"]) for r in rows if r["label"] == lab and r["verdict"] in DETECTED))
             for lab in ("Malicious", "Legitimate")}
    out = {"engine_commit_frozen": re.search(r"`([0-9a-f]{40})`", freeze).group(1), "engine_hash": frozen,
           "alert_policy": "SUSPICIOUS/HIGH = detected; LOW = not detected; INCONCLUSIVE reported separately",
           "primary_inconclusive_as_not_detected": primary, "sensitivity_inconclusive_excluded": excl,
           "verdict_distribution": verdicts, "alert_gates": gates, "by_category": cats, "by_difficulty": diff,
           "inconclusive_total": sum(r["inconclusive"] for r in rows)}
    (ROOT / "eval/metrics.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("primary_inconclusive_as_not_detected", "sensitivity_inconclusive_excluded",
                                          "verdict_distribution", "inconclusive_total")}, indent=0))


if __name__ == "__main__":
    main()
