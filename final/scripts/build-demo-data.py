"""Builds dashboard/src/demo.json: SYNTHETIC Demo Mode data for the Security Console.

Runs the real engine on the synthetic demo-mailbox scenarios (backend/tests, .example domains) and stores
their actual results. Times are offsets ("minutes ago") so the demo chart has activity at any date.
Never mixed with real account history: the dashboard shows it only in a labelled Demo Mode.
Usage: cd backend && uv run python ../scripts/build-demo-data.py
"""
import email
import json
import os
from email.header import decode_header, make_header
from pathlib import Path

os.environ.setdefault("MAILLENS_API_KEY", "x" * 40)
import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.engine import analyze  # noqa: E402
from tests.dump_responses import CASES  # noqa: E402
from tests.mailbox import request_for  # noqa: E402
from tests.test_scenarios import M, SENT  # noqa: E402

OFFSETS = [12, 38, 95, 180, 420, 900, 1500, 2900, 4300, 7200, 11000, 19000, 33000]  # minutes ago
out = []
for i, (name, case) in enumerate(CASES.items()):
    if name.endswith("_no_relationship"):  # same emails as t1/t6; avoid duplicates in the demo list
        continue
    c = dict(case)
    key = c.pop("key")
    raw = M[key]["raw"]
    req = request_for(raw, thread_raws=[M[k]["raw"] for k in c.get("thread", ())], sent_raws=SENT,
                      relationship=c.get("relationship", True))
    msg = email.message_from_string(raw)
    res = analyze(req, f"demo-{name}")[0].model_dump(mode="json")
    out.append({"id": f"demo-{name}", "minutes_ago": OFFSETS[i % len(OFFSETS)], "subject": str(make_header(decode_header(msg["Subject"] or ""))),
                "sender": str(make_header(decode_header(msg["From"] or ""))), "result": res})
dest = Path(__file__).resolve().parents[1] / "dashboard" / "src" / "demo.json"
dest.write_text(json.dumps({"synthetic": True, "source": "MailLens synthetic demo mailbox (.example domains)", "emails": out}, indent=1))
print(f"wrote {len(out)} synthetic demo emails to {dest}")
