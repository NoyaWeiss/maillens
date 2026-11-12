"""Security Console API: account isolation, one-time launch codes, sessions, evaluation data."""

import os
import tempfile

os.environ.setdefault("MAILLENS_API_KEY", "k" * 40)
os.environ["MAILLENS_DATA_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app, get_settings  # noqa: E402
from tests.factory import req as make_request  # noqa: E402

KEY = {"X-API-Key": get_settings().api_key}
ALICE, BOB = "a" * 43, "b" * 43


def client():
    return TestClient(create_app())


def analyze(c, account, msg, subject="Invoice", sender="Shop <x@shop.example>"):
    body = make_request(sender, subject=subject, html="<p>Please wire the payment today.</p>").model_dump(mode="json")
    r = c.post("/v1/analyze", json=body, headers={**KEY, "X-MailLens-Account": account, "X-MailLens-Message": msg})
    assert r.status_code == 200
    return r.json()


def session(c, account, message=None):
    path = c.post("/v1/dashboard/launch", json={"account": account, "message": message}, headers=KEY).json()["path"]
    assert path.startswith("/dashboard/#launch=") and account not in path and (message or "@@") not in path
    code = path.split("=", 1)[1]
    r = c.post("/v1/dashboard/session", json={"code": code})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}, r.json(), code


def test_accounts_are_isolated_and_context_is_resolved_server_side():
    c = client()
    analyze(c, ALICE, "msgalice01", subject="Alice invoice")
    analyze(c, BOB, "msgbob0001", subject="Bob newsletter")
    h, info, _ = session(c, ALICE, "msgalice01")
    emails = c.get("/v1/dashboard/emails", headers=h).json()["emails"]
    assert [e["subject"] for e in emails] == ["Alice invoice"]
    assert info["context"] == emails[0]["id"]
    hb, _, _ = session(c, BOB)
    bob_emails = c.get("/v1/dashboard/emails", headers=hb).json()["emails"]
    assert [e["subject"] for e in bob_emails] == ["Bob newsletter"]
    assert c.get(f"/v1/dashboard/emails/{emails[0]['id']}", headers=hb).status_code == 404   # Bob can't read Alice's
    assert c.get(f"/v1/dashboard/emails/{emails[0]['id']}", headers=h).json()["result"]["verdict"]


def test_launch_requires_api_key_and_codes_are_single_use():
    c = client()
    assert c.post("/v1/dashboard/launch", json={"account": ALICE}).status_code == 401
    _, _, code = session(c, ALICE)
    assert c.post("/v1/dashboard/session", json={"code": code}).status_code == 401
    assert c.get("/v1/dashboard/emails").status_code == 401
    assert c.get("/v1/dashboard/emails", headers={"Authorization": "Bearer forged"}).status_code == 401


def test_reanalysis_updates_one_row_and_clear_only_affects_own_account():
    c = client()
    analyze(c, ALICE, "msgalice02"); analyze(c, ALICE, "msgalice02"); analyze(c, BOB, "msgbob0002")
    h, _, _ = session(c, ALICE)
    rows = [e for e in c.get("/v1/dashboard/emails", headers=h).json()["emails"] if e["times_analyzed"] == 2]
    assert len(rows) == 1
    assert c.delete("/v1/dashboard/history", headers=h).json()["deleted"] >= 1
    assert c.get("/v1/dashboard/emails", headers=h).json()["emails"] == []
    hb, _, _ = session(c, BOB)
    assert c.get("/v1/dashboard/emails", headers=hb).json()["emails"]


def test_no_history_without_account_header_and_no_body_stored():
    c = client()
    body = make_request("Shop <x@shop.example>", html="<p>SECRET-BODY-TEXT wire it</p>").model_dump(mode="json")
    assert c.post("/v1/analyze", json=body, headers=KEY).status_code == 200
    analyze(c, "c" * 43, "msgcarol01")
    raw = open(os.path.join(os.environ["MAILLENS_DATA_DIR"], "history.sqlite3"), "rb").read()
    assert b"SECRET-BODY-TEXT" not in raw and b"c" * 43 not in raw and b"msgcarol01" not in raw


def test_evaluation_endpoint_serves_committed_primary_benchmark():
    import json
    from pathlib import Path
    m = json.loads((Path(__file__).resolve().parents[2] / "eval" / "metrics.json").read_text())
    r = client().get("/v1/dashboard/evaluation")
    assert r.status_code == 200 and r.headers["content-security-policy"].startswith("default-src 'self'")
    d = r.json()
    assert d["benchmark"] == m["primary_evaluation"] and d["overall"]["recall"] == m[d["benchmark"]]["overall"]["recall"]
    assert sum(x["n"] for x in d["by_category"]) == 200
