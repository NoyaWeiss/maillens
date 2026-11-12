"""Main-card wording rules (owner refinements, Phase 2 v3)."""

import re
from pathlib import Path

import pytest

from app.presentation import _FINDING_TEXT, _REQUEST_TEXT
from app.signals.ask import REQUEST_PATTERNS
from tests.dump_responses import CASES
from tests.test_scenarios import run

RESP = {}
for name, case in CASES.items():
    c = dict(case)
    RESP[name] = run(c.pop("key"), **c)

RAW = re.compile(r"@|https?://|hxxp|\[\.\]|\.example\b")
OBSERVED_FACT_CATEGORIES = {"Look-alike sender domain", "Risky attachment"}


def main_card_text(r):
    parts = [r.headline, r.category, r.impact]
    parts += [x for reason in r.reasons for x in (reason.title, reason.summary, reason.basis)]
    parts += [x for a in r.actions for x in (a.title, a.detail)]
    return parts


@pytest.mark.parametrize("name", RESP)
def test_main_card_rules(name):
    r = RESP[name]
    assert len(r.reasons) <= 2 and len(r.actions) <= 2
    for text in main_card_text(r):
        assert not RAW.search(text), f"{name}: raw address/URL on main card: {text!r}"
    for reason in r.reasons:
        assert len(reason.title.split()) <= 6, reason.title
    if r.verdict == "LOW":
        assert r.reasons == [] and r.impact == ""
        assert len(r.actions) == (1 if r.request and r.request.level >= 2 else 0)
    else:
        assert r.actions, f"{name}: needs a recommended action"
        assert re.search(r"\b(could|may|might)\b", r.impact), f"{name}: impact must be cautious: {r.impact!r}"
    if r.verdict in {"HIGH", "SUSPICIOUS"}:
        assert r.category.startswith("Possible") or r.category in OBSERVED_FACT_CATEGORIES, r.category


def test_owner_examples():
    assert RESP["t5"].category == "Possible vendor impersonation"
    assert RESP["t5"].impact == ("Payment could be redirected to an attacker-controlled account and may be "
                                 "difficult to recover.")
    assert [r.title for r in RESP["t5"].reasons] == ["Reply address changed", "Asks to change bank details"]
    assert [r.title for r in RESP["t6"].reasons] == ["Asks to change bank details", "Sender is known to you"]
    assert len(RESP["t6"].actions) == 1                       # second action only when it adds value
    assert RESP["t9"].reasons[0].title == "Sender can't be verified"
    assert RESP["t9"].category == "Sender could not be verified"


def test_every_finding_kind_and_request_pattern_has_wording():
    src = "".join(p.read_text() for p in Path("app").rglob("*.py"))
    kinds = set(re.findall(r'Finding\.of\("([a-z_]+)"', src))
    assert kinds and kinds <= set(_FINDING_TEXT), kinds - set(_FINDING_TEXT)
    elevated = {p.id for p in REQUEST_PATTERNS if p.level >= 2}
    assert elevated <= set(_REQUEST_TEXT), elevated - set(_REQUEST_TEXT)


def test_findings_carry_titles():
    for r in RESP.values():
        for f in r.findings + r.also_observed:
            assert f.title and f.summary and not RAW.search(f.title + f.summary)


# ---------------------------------------------------------------- Detailed analysis (v4)
INTERNAL = re.compile(r"\b(?:H-[ABC]|S-[AD]|INC|S\d{1,2}|D\d|A\d|E\d|N[01?])\b")


@pytest.mark.parametrize("name", RESP)
def test_detailed_analysis_fields(name):
    r = RESP[name]
    assert r.decision_explanation and not INTERNAL.search(r.decision_explanation)
    for c in r.checks:
        assert c.label and not INTERNAL.search(c.label)
        if c.state != "ran":
            assert c.note, f"{name}: {c.id} {c.state} needs a plain reason"
    for s in r.safeguards:
        assert not INTERNAL.search(s), s
    for f in r.findings:
        assert f.details, f"{name}: {f.signal} has no evidence values"
        assert all(d.label and d.value for d in f.details)


def test_evidence_values_are_exact():
    t5 = {d.label: d.value for d in RESP["t5"].findings[0].details}
    assert t5 == {"From": "billing@acmesupply.example", "Reply-To": "acme.supply.accounts@gmail.example",
                  "Earlier messages from this From address": "no Reply-To or a different one"}
    t7 = {d.label: d.value for f in RESP["t7"].findings if f.signal == "S5" for d in f.details}
    assert t7 == {"Resembles": "acmesupply.example", "From domain": "acmesupp1y.example"}
    t8 = {d.label: d.value for f in RESP["t8"].findings if f.signal == "S9" for d in f.details}
    assert t8 == {"Link text shows": "northwindbank[.]example", "Link opens": "login[.]northwind-verify[.]example"}


def test_safeguards_and_privacy_wording():
    assert any("sending-platform" in s for s in RESP["t1"].safeguards)
    assert any("preview line" in s for s in RESP["t3"].safeguards)
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()   # general limitations moved here
    assert "when you allow it" in readme and "read access to your mailbox" in readme
    assert RESP["t1"].limitations == []
    assert {c.id: c.note for c in RESP["t9"].checks}["S1"].startswith("no authentication results")


def test_consent_phishing_is_not_described_as_a_sign_in_request():
    from tests.factory import run as frun
    r = frun("Google Docs <docs.share.notify@gmail.com>",
             html='<p><a href="https://accounts.google.com/o/oauth2/v2/auth?client_id=1&scope=https://mail.google.com/">Open</a></p>')
    assert r.category == "Possible consent phishing"
    assert "sign in" not in r.headline.lower() and "access to your email" in r.headline
    assert [a.title for a in r.actions][0] == "Don't grant access"


def test_deceptive_link_without_sign_in_request_says_so_precisely():
    from tests.factory import run as frun
    r = frun("Shop <x@shop.example>", html='<p><a href="https://evil.example/x">bank.example</a></p>')
    assert r.verdict in {"SUSPICIOUS", "HIGH"} and "sign in" not in r.headline.lower()


def test_detailed_analysis_shows_only_email_specific_limitations():
    from tests.test_scenarios import run
    assert run("t1").limitations == []                                        # complete analysis: nothing to caveat
    assert any("Mailbox access is off" in x for x in run("t6", relationship=False).limitations)
    assert any("attachment" in x for x in run("t7").limitations)
    assert any("authentication results" in x for x in run("t9").limitations)
