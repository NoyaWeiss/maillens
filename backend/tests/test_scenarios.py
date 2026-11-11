"""Spec 3.6 worked outcomes, run against the exact emails seeded into the demo mailbox."""

import pytest

from app.engine import analyze
from tests.mailbox import demo_messages, request_for

M = demo_messages()
SENT = [m["raw"] for m in M.values() if "SENT" in m["labels"]]


def run(key, *, thread=(), relationship=True, raw=None):
    req = request_for(raw or M[key]["raw"], thread_raws=[M[k]["raw"] for k in thread], sent_raws=SENT,
                      relationship=relationship)
    return analyze(req, "test")[0]


@pytest.mark.parametrize("key,thread,verdict,gate", [
    ("h2", ("h1",), "LOW", None),
    ("h4", ("h3",), "LOW", None),
    ("t1", (), "LOW", None),                     # billing platform: S9 guard (DKIM d= matches)
    ("t2", (), "LOW", None),                     # sign-in alert: A=2 only -> Low + advisory
    ("t3", (), "LOW", None),                     # newsletter: preheader + bulk guards
    ("t4b", (), "HIGH", "H-B"),                  # name collision (S4=2) + favor probe (A=2)
    ("t5", ("h3", "h4"), "HIGH", "H-B"),         # Reply-To added mid-thread (S2=2) + bank change (A=3)
    ("t6", (), "SUSPICIOUS", "S-A"),             # bank change from a known vendor, nothing else
    ("t7", (), "HIGH", "H-A"),                   # confusable cousin domain (S5=3)
    ("t8", (), "HIGH", "H-A"),                   # scanner-targeting hidden text (S12=3) + S9
    ("t9", (), "INCONCLUSIVE", "INC"),           # no auth headers + credential ask
])
def test_demo_mailbox_outcomes(key, thread, verdict, gate):
    r = run(key, thread=thread)
    assert (r.verdict, r.gate) == (verdict, gate), (r.vector, [(f.signal, f.level, f.reality) for f in r.findings])


def test_t2_low_has_advisory():
    r = run("t2")
    assert r.request and r.request.level == 2
    assert "directly" in r.actions[0]


def test_t5_without_thread_degrades_to_suspicious():
    # Limitation stated in the spec: without thread history, ATO degrades to Suspicious.
    assert run("t5").verdict == "SUSPICIOUS"


def test_t5_archetype_and_story():
    r = run("t5", thread=("h3", "h4"))
    assert r.archetype == "Vendor account takeover"
    assert any("unrecoverable" in line for line in r.story)


def test_t7_one_entity_counted_once():
    r = run("t7")
    sender_findings = [f for f in r.findings if f.entity == "domain:acmesupp1y.example"]
    assert len(sender_findings) == 1 and sender_findings[0].signal == "S5"


def test_relationship_unavailable_never_escalates_and_lowers_confidence():
    r = run("t6", relationship=False)
    assert r.verdict == "SUSPICIOUS" and r.confidence == "Limited"
    assert {c.id: c.state for c in r.checks}["S4"] == "unavailable"


def test_live_t4_from_real_gmail_address():
    raw = M["t4b"]["raw"].replace("dana.cohen.northwind@gmail.example", "dana.cohen.home@gmail.com") \
        .replace("header.from=gmail.example", "header.from=gmail.com")
    r = run("t4b", raw=raw)
    assert (r.verdict, r.gate) == ("HIGH", "H-B")
    assert any("free-mail" in f.reality for f in r.findings)
