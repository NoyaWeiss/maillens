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
