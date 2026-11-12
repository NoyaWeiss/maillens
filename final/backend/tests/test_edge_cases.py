"""Phase 3 edge-case suite (hard negatives, attacks, documented blind spots)."""

import pytest

from app.engine import analyze
from tests.edge_cases import CASES
from tests.factory import req

RANK = {"LOW": 0, "INCONCLUSIVE": 1, "SUSPICIOUS": 2, "HIGH": 3}


@pytest.mark.parametrize("name,kind,expected,kw", CASES, ids=[c[0] for c in CASES])
def test_edge_case(name, kind, expected, kw):
    kw = dict(kw)
    r = analyze(req(kw.pop("from_header"), auth=kw.pop("auth", "pass"), **kw), "t")[0]
    if kind == "attack":
        assert RANK[r.verdict] >= RANK[expected], (r.verdict, r.vector)
    else:
        assert r.verdict == expected, (r.verdict, r.gate, r.vector, [f.signal for f in r.findings])


def test_no_weak_signal_alone_reaches_high_in_suite():
    for name, kind, expected, kw in CASES:
        kw = dict(kw)
        r = analyze(req(kw.pop("from_header"), auth=kw.pop("auth", "pass"), **kw), "t")[0]
        if r.verdict == "HIGH":
            strong = [f for f in r.findings if f.level >= 2]
            assert strong or (r.request and r.request.level == 3 and len([c for c in r.vector.split(" · ") if c in ("P1", "N1")]) >= 1), name
