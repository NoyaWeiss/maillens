"""Retrospective comparison: every frozen engine on every fixed evaluation dataset.

Usage (repo root):  python3 eval/compare_engines.py
Creates a temporary git worktree per engine commit, runs its unchanged engine on eval/v1, v2, v3 datasets,
and writes eval/engine_comparison.json. No rule, label or dataset is modified.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINES = {"v1": "00bb9d1", "v2": "97f93f8", "v3": "c7ffff5"}
DATASETS = ["v1", "v2", "v3"]
RUNNER = r'''
import json, sys
from app.engine import analyze
from app.schemas import AnalyzeRequest
out = {}
for ds, path in json.loads(sys.argv[1]).items():
    rows = []
    for line in open(path):
        c = json.loads(line)
        r = analyze(AnalyzeRequest.model_validate(c["input"]), c["id"])[0]
        rows.append({"id": c["id"], "label": c["label"], "category": c["category"], "verdict": r.verdict})
    out[ds] = rows
print(json.dumps(out))
'''


def run_engine(commit: str) -> dict:
    tmp = Path(tempfile.mkdtemp()) / commit
    subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "-q", str(tmp), commit], check=True)
    try:
        shutil.copytree(ROOT / "backend/.venv", tmp / "backend/.venv", symlinks=True)
        paths = {d: str(ROOT / f"eval/{d}/dataset.jsonl") for d in DATASETS}
        res = subprocess.run([str(tmp / "backend/.venv/bin/python"), "-c", RUNNER, json.dumps(paths)], cwd=tmp / "backend",
                             capture_output=True, text=True, env={"MAILLENS_API_KEY": "x" * 40, "PATH": "/usr/bin:/bin"}, check=True)
        return json.loads(res.stdout)
    finally:
        subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(tmp)], check=True)


def metrics(rows):
    det = lambda r: r["verdict"] in {"SUSPICIOUS", "HIGH"}
    tp = sum(r["label"] == "Malicious" and det(r) for r in rows)
    fn = sum(r["label"] == "Malicious" and not det(r) for r in rows)
    fp = sum(r["label"] == "Legitimate" and det(r) for r in rows)
    tn = sum(r["label"] == "Legitimate" and not det(r) for r in rows)
    p = tp / (tp + fp) if tp + fp else float("nan")
    rc = tp / (tp + fn)
    return {"TP": tp, "FN": fn, "FP": fp, "TN": tn, "precision": round(p, 3), "recall": round(rc, 3),
            "f1": round(2 * p * rc / (p + rc), 3) if p + rc else 0.0, "fpr": round(fp / (fp + tn), 3),
            "inconclusive": sum(r["verdict"] == "INCONCLUSIVE" for r in rows)}


if __name__ == "__main__":
    results = {e: run_engine(c) for e, c in ENGINES.items()}
    out = {"engines": ENGINES, "metrics": {e: {d: metrics(results[e][d]) for d in DATASETS} for e in ENGINES},
           "per_case": results}
    (ROOT / "eval/engine_comparison.json").write_text(json.dumps(out, indent=1))
    json.dump(out["metrics"], sys.stdout, indent=0)
