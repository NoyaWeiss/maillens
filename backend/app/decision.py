"""The decision core (spec section 3). Pure functions only, so the invariants
(INV-1..INV-6) can be property-tested exhaustively.

Inputs  : findings (entity, group, level), A (request 0-3), P (pressure), N ("0","1","?"),
          auth_available (S1 ran).
Outputs : verdict, gate, pathway, score, dedup result, vector.
"""

from dataclasses import dataclass, field

from .model import Finding
from .schemas import Verdict

SCORE_ANCHOR = {Verdict.LOW: 8, Verdict.SUSPICIOUS: 40, Verdict.HIGH: 75}
SCORE_CAP = {Verdict.LOW: 20, Verdict.SUSPICIOUS: 60, Verdict.HIGH: 95}
ENTITY_BONUS = (4, 5, 5)  # for the 2nd, 3rd and 4th distinct entity with a finding


@dataclass
class Decision:
    verdict: Verdict
    gate: str | None
    pathway: str | None
    score: int | None
    kept: list[Finding]
    also_observed: list[Finding]
    D: int
    E: int
    A: int
    P: bool
    N: str
    W: bool
    corroborators: list[str] = field(default_factory=list)

    @property
    def vector(self) -> str:
        return f"D{self.D} · A{self.A} · E{self.E} · P{int(self.P)} · N{self.N}"


def dedup(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """R1: one finding per (entity, group), strongest kept. Deterministic regardless of input order."""
    ordered = sorted(findings, key=lambda f: (f.entity, f.group, -f.level, f.signal, f.claim, f.reality))
    kept: dict[tuple[str, str], Finding] = {}
    also: list[Finding] = []
    for f in ordered:
        key = (f.entity, f.group)
        if key in kept:
            also.append(f)
        else:
            kept[key] = f
    return list(kept.values()), also


def decide(findings: list[Finding], A: int, P: bool, N: str, auth_available: bool,
           pretext_secrecy: bool = False) -> Decision:
    kept, also = dedup(findings)
    D = max((f.level for f in kept), default=0)                         # R2: group maxima, no summing
    strong_entities = {f.entity for f in kept if f.level >= 2}
    E = len(strong_entities)                                            # R3: distinct entities
    W = any(f.level == 1 for f in findings)
    corroborators = [name for name, on in (("P", P), ("U", N == "1"), ("W", W)) if on]

    gate = pathway = None
    if D >= 3:
        verdict, gate, pathway = Verdict.HIGH, "H-A", "Deception"
    elif D >= 2 and (A >= 2 or E >= 2):
        verdict, gate, pathway = Verdict.HIGH, "H-B", "Deception"
    elif A == 3 and len(corroborators) >= 2:
        verdict, gate, pathway = Verdict.HIGH, "H-C", "Request in context"
    elif D >= 2:
        verdict, gate, pathway = Verdict.SUSPICIOUS, "S-D", "Deception"
    elif A == 3:
        verdict, gate, pathway = Verdict.SUSPICIOUS, "S-A", "Request in context"
    elif pretext_secrecy and N == "1":
        # F-19 (Phase 3b): a BEC-style pretext (unexplained favor / move off email) with explicit secrecy
        # from an unfamiliar sender. Suspicious only, never High; generic "confidential" doesn't count.
        verdict, gate, pathway = Verdict.SUSPICIOUS, "S-P", "Request in context"
    else:
        verdict = Verdict.LOW

    # The single Inconclusive rule (spec 3.5).
    if verdict is Verdict.LOW and not auth_available and (A >= 2 or W):
        verdict, gate = Verdict.INCONCLUSIVE, "INC"

    return Decision(verdict, gate, pathway, _score(verdict, kept), kept, also, D, E, A, P, N, W, corroborators)


def _score(verdict: Verdict, kept: list[Finding]) -> int | None:
    """A band position, not a probability. Never leaves its band."""
    if verdict is Verdict.INCONCLUSIVE:
        return None
    entities = len({f.entity for f in kept})
    bonus = sum(ENTITY_BONUS[: max(0, entities - 1)])
    return min(SCORE_ANCHOR[verdict] + bonus, SCORE_CAP[verdict])


def explain_gate(d: Decision) -> str:
    top = max(d.kept, key=lambda f: f.level, default=None)
    sig = f" ({top.signal})" if top else ""
    return {
        "H-A": f"High via H-A: a deliberate deception construct{sig}, which stands on its own.",
        "H-B": (f"High via H-B: a strong finding{sig} plus "
                + ("an elevated request (S13)." if d.A >= 2 else f"strong findings on {d.E} separate entities.")),
        "H-C": f"High via H-C: an irreversible request (S13) with corroboration ({', '.join(d.corroborators)}).",
        "S-D": f"Suspicious: a strong finding{sig}, without a request or second entity to corroborate it.",
        "S-A": "Suspicious: an irreversible request (S13). Verify it out-of-band, even from a known sender.",
        "S-P": "Suspicious: an unfamiliar sender asks for an unexplained favor and asks you to keep it secret.",
        "INC": "Inconclusive: the sender can't be verified (no authentication results) and the message "
               "contains an elevated request or an anomaly.",
    }.get(d.gate or "", "Low: no gate fired.")
