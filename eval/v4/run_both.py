"""Single run of the baseline (c7ffff5) and candidate (20f0e5e) engines on the v4 benchmark, each from its own
temporary git worktree (unchanged code). Writes eval/v4/results.json and eval/v4/metrics.json."""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_engines as ce

ce.DATASETS = ["v4"]
ce.RUNNER = ce.RUNNER.replace('"verdict": r.verdict}', '"verdict": r.verdict, "gate": r.gate, "difficulty": c["difficulty"], "origin": c["origin"]}')
ENGINES = {"baseline_c7ffff5": "c7ffff5", "candidate_20f0e5e": "20f0e5e"}
res = {k: ce.run_engine(c)["v4"] for k, c in ENGINES.items()}
det = lambda r: r["verdict"] in {"SUSPICIOUS", "HIGH"}

def breakdown(rows, key):
    out = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        k = f'{r["label"]}|{r[key]}'
        out[k][0] += det(r); out[k][1] += 1
    return {k: f"{a}/{n}" for k, (a, n) in sorted(out.items())}

M = {k: {"overall": ce.metrics(v), "by_category": breakdown(v, "category"), "by_difficulty": breakdown(v, "difficulty"),
         "by_origin": breakdown(v, "origin")} for k, v in res.items()}
Path(__file__).with_name("results.json").write_text(json.dumps(res, indent=1))
Path(__file__).with_name("metrics.json").write_text(json.dumps(M, indent=1))
