"""Phase 3: user-facing text must be grounded in extracted evidence and never overstate it."""

import json
import re

import pytest

from app.engine import analyze
from app.htmltext import parse_html, strip_quotes_and_signature
from tests.dump_responses import CASES
from tests.mailbox import demo_messages, request_for
from tests.test_scenarios import SENT, run

M = demo_messages()
CASE_RESP, CASE_REQ = {}, {}
for name, case in CASES.items():
    c = dict(case)
    key = c.pop("key")
    CASE_REQ[name] = request_for(M[key]["raw"], thread_raws=[M[k]["raw"] for k in c.get("thread", ())],
                                 sent_raws=SENT, relationship=c.get("relationship", True))
    CASE_RESP[name] = analyze(CASE_REQ[name], "t")[0]

LIVE_LINK = re.compile(r"\b(?:https?|ftp)://|\bwww\.[a-z0-9-]+\.[a-z]", re.IGNORECASE)
INFERENCE = re.compile(r"fraud|attacker|compromis|impersonat|scam|phishing|malicious", re.IGNORECASE)


def undefang(s: str) -> str:
    return s.replace("[.]", ".").replace("hxxp", "http")


def norm(s: str) -> str:
    return " ".join(s.split())


@pytest.mark.parametrize("name", CASE_RESP)
def test_quote_is_verbatim_from_one_source(name):
    r, q = CASE_RESP[name], CASE_REQ[name]
    if not r.request:
        return
    assert r.request.source in {"Subject", "Body"}
    body = strip_quotes_and_signature(parse_html(q.message.html_body).visible_text or q.message.text_body)
    source_text = norm(q.message.subject if r.request.source == "Subject" else body)
    quoted = norm(undefang(r.request.excerpt).replace("…", " "))
    for fragment in [f for f in quoted.split("  ") if f.strip()]:
        assert norm(fragment) in source_text, f"{name}: quote not verbatim from {r.request.source}: {fragment!r}"
    if r.request.source == "Body":
        assert not quoted.startswith(norm(q.message.subject)), f"{name}: subject glued onto a body quote"
    assert re.search(r"[.!?:]$|…$|\w$", r.request.excerpt.strip()), "quote must end cleanly"


@pytest.mark.parametrize("name", CASE_RESP)
def test_nothing_rendered_is_a_live_link(name):
    r = CASE_RESP[name]
    texts = [r.request.excerpt] if r.request else []
    texts += [d.value for f in r.findings + r.also_observed for d in f.details if d.label not in {"From", "Reply-To"}
              and "address" not in d.label.lower()]
    texts += [r.headline, r.impact] + [x.summary for x in r.reasons]
    for t in texts:
        assert not LIVE_LINK.search(t), f"{name}: live link in {t!r}"


@pytest.mark.parametrize("name", CASE_RESP)
def test_observed_statements_contain_no_inference(name):
    r = CASE_RESP[name]
    for reason in r.reasons:
        if reason.basis == "Seen in this email":
            assert not INFERENCE.search(reason.title + " " + reason.summary), reason
    for f in r.findings:
        assert not INFERENCE.search(f.title + " " + f.summary), f.title
        assert not any(d.label == "Sender" for d in f.details), "use From / Reply-To, never the ambiguous 'Sender'"


@pytest.mark.parametrize("name", CASE_RESP)
def test_risk_index_is_never_a_probability(name):
    blob = json.dumps(CASE_RESP[name].model_dump(mode="json"))
    assert "%" not in blob.replace("98%", "")  # T9's own email text mentions "98%"; that's quoted email content
    for m in re.finditer(r"probabilit\w*", blob, re.IGNORECASE):
        assert "not a probability" in blob[max(0, m.start() - 12): m.end()], "probability may only be denied"


def test_reply_to_evidence_matches_headers():
    r, q = CASE_RESP["t5"], CASE_REQ["t5"]
    d = {x.label: x.value for x in r.findings[0].details}
    assert d["From"] in q.message.from_header and d["Reply-To"] in q.message.reply_to
    earlier = [t for t in q.thread if "billing@acmesupply.example" in t.from_header]
    assert earlier and all(t.reply_to is None for t in earlier), "claim about earlier messages must hold"
