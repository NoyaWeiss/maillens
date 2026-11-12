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


def test_gmail_addon_message_ids_with_prefix_are_recorded_and_selectable():
    # Gmail add-on event ids are opaque and can carry a prefix and colon (e.g. "msg-f:<digits>").
    c = client()
    acct = "d" * 64
    for mid in ("msg-f:1849376123456789012", "msg-a:r-8812345", "18c3f2a9b7d41e05"):
        analyze(c, acct, mid, subject=f"S {mid}")
    h, info, _ = session(c, acct, "msg-f:1849376123456789012")
    emails = c.get("/v1/dashboard/emails", headers=h).json()["emails"]
    assert len(emails) == 3
    assert c.get(f"/v1/dashboard/emails/{info['context']}", headers=h).json()["subject"] == "S msg-f:1849376123456789012"


def test_unusable_ids_are_rejected_without_logging_values(caplog):
    c = client()
    analyze(c, "e" * 64, "bad id with spaces")
    assert "bad id" not in caplog.text and "history not recorded" in caplog.text
    r = c.post("/v1/dashboard/launch", json={"account": "e" * 64, "message": "x" * 300}, headers=KEY)
    assert r.status_code == 422


SCAN_URL = "https://script.google.com/macros/s/AKfycbx" + "A" * 40 + "/exec"


def scan_session(c, account):
    path = c.post("/v1/dashboard/launch", json={"account": account, "scan_url": SCAN_URL}, headers=KEY).json()["path"]
    r = c.post("/v1/dashboard/session", json={"code": path.split("=", 1)[1]}).json()
    assert r["scan_available"] is True
    return {"Authorization": "Bearer " + r["token"]}


def test_scan_ticket_is_bound_to_the_session_account():
    c = client()
    acct, other = "s" * 64, "o" * 64
    h = scan_session(c, acct)
    r = c.post("/v1/dashboard/scan", json={"range": "24H"}, headers=h).json()
    assert r["url"].startswith(SCAN_URL + "?t=") and acct not in r["url"]
    t = r["ticket"]
    # A different Google account (different private key) can't use this ticket.
    assert c.post("/v1/scan/start", json={"ticket": t, "account": other}, headers=KEY).status_code == 403
    assert c.post("/v1/scan/start", json={"ticket": t, "account": acct}).status_code == 401          # API key required
    assert c.post("/v1/scan/start", json={"ticket": t, "account": acct}, headers=KEY).json()["range_seconds"] == 86400
    assert c.post("/v1/scan/start", json={"ticket": t, "account": acct}, headers=KEY).status_code == 409   # starts once
    analyze(c, acct, "18c3f2a9b7d41e05", subject="already seen")
    known = c.post("/v1/scan/known", json={"ticket": t, "account": acct, "ids": ["18c3f2a9b7d41e05", "18c3f2a9b7d41e06"]}, headers=KEY).json()
    assert known["known"] == ["18c3f2a9b7d41e05"]                                                       # deduplication
    c.post("/v1/scan/progress", json={"ticket": t, "account": acct, "state": "done", "total": 2, "done": 1, "skipped": 1, "failed": 0}, headers=KEY)
    assert c.get(f"/v1/dashboard/scan/{t}", headers=h).json()["state"] == "done"
    assert c.get(f"/v1/dashboard/scan/{t}", headers=scan_session(c, other)).status_code == 404         # other account can't poll


def test_scan_requires_setup_and_valid_script_url():
    c = client()
    h, _, _ = session(c, "n" * 64)
    assert c.post("/v1/dashboard/scan", json={"range": "24H"}, headers=h).status_code == 409
    bad = c.post("/v1/dashboard/launch", json={"account": "n" * 64, "scan_url": "https://evil.example/exec"}, headers=KEY)
    assert bad.status_code == 422


def test_received_time_drives_ordering():
    c = client()
    acct = "r" * 64
    body = make_request("Shop <x@shop.example>", subject="old").model_dump(mode="json")
    c.post("/v1/analyze", json=body, headers={**KEY, "X-MailLens-Account": acct, "X-MailLens-Message": "oldmsg01",
                                              "X-MailLens-Received": str(int((__import__("time").time() - 5 * 86400) * 1000))})
    body_new = make_request("Shop <x@shop.example>", subject="new").model_dump(mode="json")
    c.post("/v1/analyze", json=body_new, headers={**KEY, "X-MailLens-Account": acct, "X-MailLens-Message": "newmsg01",
                                                  "X-MailLens-Received": str(int(__import__("time").time() * 1000))})
    h, _, _ = session(c, acct)
    e = c.get("/v1/dashboard/emails", headers=h).json()["emails"]
    assert [x["subject"] for x in e] == ["new", "old"] and e[1]["received_at"] < e[0]["received_at"] - 4 * 86400


# ------------------------------------------------------------------ received time (time filters) regressions
def test_received_time_sources_and_timezones():
    from app.main import received_time
    assert received_time("1762941600000", "Mon, 1 Jan 2024 00:00:00 +0000") == 1762941600        # Gmail's time wins
    # Date header with a timezone: 10:00 at +02:00 is 08:00 UTC.
    assert received_time(None, "Wed, 12 Nov 2025 10:00:00 +0200") == 1762934400
    assert received_time(None, "Wed, 12 Nov 2025 10:00:00 -0500") == 1762959600
    assert received_time(None, "not a date") is None and received_time(None, None) is None
    assert received_time("", "Wed, 12 Nov 2025 10:00:00") is None                                   # no timezone: unknown


def test_old_email_analyzed_today_keeps_its_received_time_and_unknown_is_never_analysis_time():
    import time as _t
    c = client()
    acct = "q" * 64
    old_ms = str(int((_t.time() - 20 * 86400) * 1000))
    body = make_request("Shop <x@shop.example>", subject="old email, analyzed now").model_dump(mode="json")
    body["message"]["date"] = None
    c.post("/v1/analyze", json=body, headers={**KEY, "X-MailLens-Account": acct, "X-MailLens-Message": "old00001", "X-MailLens-Received": old_ms})
    c.post("/v1/analyze", json=body, headers={**KEY, "X-MailLens-Account": acct, "X-MailLens-Message": "nodate01"})
    # Re-analysis without a received time must not erase the known one.
    c.post("/v1/analyze", json=body, headers={**KEY, "X-MailLens-Account": acct, "X-MailLens-Message": "old00001"})
    h, _, _ = session(c, acct)
    rows = {e["id"]: e for e in c.get("/v1/dashboard/emails", headers=h).json()["emails"]}
    by_msg = sorted(rows.values(), key=lambda e: e["received_at"] is None)
    assert abs(by_msg[0]["received_at"] - int(old_ms) / 1000) < 1 and by_msg[0]["analyzed_at"] > _t.time() - 60
    assert by_msg[1]["received_at"] is None                                                            # unknown stays unknown
