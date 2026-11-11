"""Engine grid + invariants INV-1..INV-6 (spec 4.2)."""

import itertools
import random

from app.decision import decide
from app.model import Finding
from app.schemas import Basis, Group, Verdict

RANK = {Verdict.LOW: 0, Verdict.INCONCLUSIVE: 1, Verdict.SUSPICIOUS: 2, Verdict.HIGH: 3}
F = lambda ent, lvl, grp=Group.IDENTITY, sig="S3": Finding(sig, grp, ent, lvl, Basis.OBSERVED, "c", "r")
FINDING_SETS = [
    [], [F("a", 1)], [F("a", 2)], [F("a", 3)], [F("a", 1), F("b", 1)], [F("a", 2), F("b", 2, Group.DEST, "S9")],
    [F("a", 2), F("a", 1, Group.AUTH, "S1")], [F("a", 1), F("b", 2, Group.DEST, "S9")],
]
GRID = list(itertools.product(range(len(FINDING_SETS)), range(4), (False, True), ("0", "1", "?"), (True, False)))


def d(i, A, P, N, auth):
    return decide(FINDING_SETS[i], A, P, N, auth)


def test_inv1_no_single_weak_or_heuristic_reaches_high():
    for A, P, N in itertools.product(range(4), (False, True), ("0", "1", "?")):
        single_heuristic = sum([A > 0, P, N == "1"]) <= 1
        if single_heuristic:
            assert decide([], A, P, N, True).verdict is not Verdict.HIGH
        assert decide([F("a", 1)], 0, False, "0", True).verdict is not Verdict.HIGH


def test_inv2_monotonic():
    for i, A, P, N, auth in GRID:
        base = RANK[d(i, A, P, N, auth).verdict]
        assert RANK[d(i, min(A + 1, 3), P, N, auth).verdict] >= base
        assert RANK[d(i, A, True, N, auth).verdict] >= base
        assert RANK[decide(FINDING_SETS[i] + [F("z", 2, Group.DEST, "S9")], A, P, N, auth).verdict] >= base


def test_inv3_redundant_same_entity_finding_changes_nothing():
    for i, A, P, N, auth in GRID:
        base = d(i, A, P, N, auth)
        for f in FINDING_SETS[i]:
            weaker = Finding("S5", f.group, f.entity, 1, Basis.OBSERVED, "c2", "r2")
            same = decide(FINDING_SETS[i] + [weaker], A, P, N, auth)
            if f.level >= 2:  # a weaker duplicate of a strong finding on the same (entity, group)
                assert (same.verdict, same.score) == (base.verdict, base.score) or base.W


def test_inv4_unknown_never_escalates():
    for i, A, P, N, auth in GRID:
        known = d(i, A, P, "0", True)
        unknown = d(i, A, P, "?", False)
        if unknown.verdict is not Verdict.INCONCLUSIVE:
            assert RANK[unknown.verdict] <= RANK[known.verdict]


def test_inv5_order_independent():
    rnd = random.Random(7)
    for i, A, P, N, auth in GRID:
        fs = list(FINDING_SETS[i])
        rnd.shuffle(fs)
        a, b = decide(fs, A, P, N, auth), d(i, A, P, N, auth)
        assert (a.verdict, a.score, a.gate) == (b.verdict, b.score, b.gate)


def test_inv6_inconclusive_only_under_exact_condition():
    for i, A, P, N, auth in GRID:
        r = d(i, A, P, N, auth)
        low_without = decide(FINDING_SETS[i], A, P, N, True).verdict is Verdict.LOW
        expected = (not auth) and low_without and (A >= 2 or r.W)
        assert (r.verdict is Verdict.INCONCLUSIVE) == expected


def test_scores_stay_in_band():
    bands = {Verdict.LOW: (0, 29), Verdict.SUSPICIOUS: (30, 64), Verdict.HIGH: (65, 100)}
    for i, A, P, N, auth in GRID:
        r = d(i, A, P, N, auth)
        if r.score is not None:
            lo, hi = bands[r.verdict]
            assert lo <= r.score <= hi


def test_gate_table():
    assert decide([F("a", 3)], 0, False, "0", True).gate == "H-A"
    assert decide([F("a", 2)], 2, False, "0", True).gate == "H-B"
    assert decide([F("a", 2), F("b", 2, Group.DEST, "S9")], 0, False, "0", True).gate == "H-B"
    assert decide([], 3, True, "1", True).gate == "H-C"
    assert decide([F("a", 2)], 0, False, "0", True).gate == "S-D"
    assert decide([], 3, False, "0", True).gate == "S-A"
    assert decide([], 2, False, "1", True).verdict is Verdict.LOW
    # Same domain as sender and as link target = one entity (R3).
    one = decide([F("a", 2), F("a", 2, Group.DEST, "S9")], 0, False, "0", True)
    assert (one.E, one.verdict) == (1, Verdict.SUSPICIOUS)
