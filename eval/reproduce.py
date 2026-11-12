"""Reproduce the primary (latest) benchmark with the CURRENT engine and compare it with the committed results.

Usage:  cd backend && uv run python ../eval/reproduce.py      (or: python ../eval/reproduce.py inside a venv)

It runs every email of the committed dataset through backend/app/engine.py, recomputes the metrics
(Suspicious or High = alert), and checks them, and every per-email verdict, against eval/metrics.json and
the committed per-case results. Exit code 0 = identical. Nothing is written.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("MAILLENS_API_KEY", "x" * 40)

from app.engine import analyze  # noqa: E402
from app.schemas import AnalyzeRequest  # noqa: E402

metrics = json.loads((ROOT / "eval" / "metrics.json").read_text())
bench = metrics["primary_evaluation"]
committed = metrics[bench]["overall"]
cases = [json.loads(line) for line in (ROOT / "eval" / bench / "dataset.jsonl").open()]
retained = metrics[bench]["engine"].split()[0]
per_case = json.loads((ROOT / "eval" / bench / "results.json").read_text())
expected = {r["id"]: r["verdict"] for r in next(v for k, v in per_case.items() if k.endswith(retained))}

ALERT = {"SUSPICIOUS", "HIGH"}
tp = fn = fp = tn = 0
mismatches = []
for c in cases:
    verdict = analyze(AnalyzeRequest.model_validate(c["input"]), c["id"])[0].verdict
    if verdict != expected[c["id"]]:
        mismatches.append((c["id"], expected[c["id"]], verdict))
    hit = verdict in ALERT
    if c["label"] == "Malicious":
        tp, fn = tp + hit, fn + (not hit)
    else:
        fp, tn = fp + hit, tn + (not hit)

now = {"TP": tp, "FN": fn, "FP": fp, "TN": tn, "precision": round(tp / (tp + fp), 3), "recall": round(tp / (tp + fn), 3),
       "fpr": round(fp / (fp + tn), 3)}
same = all(now[k] == committed[k] for k in now) and not mismatches
print(f"benchmark {bench}: {len(cases)} emails ({sum(c['label'] == 'Malicious' for c in cases)} malicious)")
print(f"current engine : TP {tp}  FN {fn}  FP {fp}  TN {tn}  precision {now['precision']}  recall {now['recall']}  FPR {now['fpr']}")
print(f"committed      : TP {committed['TP']}  FN {committed['FN']}  FP {committed['FP']}  TN {committed['TN']}  "
      f"precision {committed['precision']}  recall {committed['recall']}  FPR {committed['fpr']}")
print(f"per-email verdicts identical: {not mismatches}" + (f" ({len(mismatches)} differ, e.g. {mismatches[:3]})" if mismatches else ""))
print("REPRODUCED" if same else "DIFFERENT")
sys.exit(0 if same else 1)
