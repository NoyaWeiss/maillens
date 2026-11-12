"""Internal evidence model shared by all signals."""

from dataclasses import dataclass, field
from email.utils import getaddresses, parseaddr

from .domains import is_freemail, registrable
import re

from .htmltext import FORWARD_MARKER, Link, ParsedBody, links_from_text, parse_html
from .schemas import AnalyzeRequest, Basis, CheckState, Group
from .signals.auth import AuthResult, parse_topmost


@dataclass(frozen=True)
class Finding:
    signal: str
    group: Group
    entity: str      # dedup key, e.g. "domain:acmesupp1y.example", "file:a.exe", "body"
    level: int       # 1 weak, 2 strong, 3 deliberate construct
    basis: Basis
    claim: str
    reality: str
    excerpt: str = ""
    # Presentation key (e.g. "reply_mid_thread"): selects the user-facing title and summary.
    # Never used by sorting, deduplication or any decision.
    kind: str = ""

    @classmethod
    def of(cls, kind: str, *args, **kwargs) -> "Finding":
        return cls(*args, kind=kind, **kwargs)


@dataclass
class Address:
    display: str
    address: str
    domain: str
    reg: str  # registrable domain

    @classmethod
    def parse(cls, header: str | None) -> "Address":
        name, addr = parseaddr(header or "")
        addr = addr.strip().lower()[:320]
        domain = addr.rsplit("@", 1)[1] if "@" in addr else ""
        return cls(" ".join(name.split())[:200], addr, domain, registrable(domain) if domain else "")


@dataclass
class SignalResult:
    findings: list[Finding] = field(default_factory=list)
    state: CheckState = CheckState.RAN
    notes: list[str] = field(default_factory=list)  # guard notes ("suppressed: bulk mail")


@dataclass
class Context:
    req: AnalyzeRequest
    sender: Address
    reply_to: Address | None
    auth: AuthResult
    is_bulk: bool
    body: ParsedBody
    links: list[Link]
    dkim_regs: frozenset[str]
    familiarity: str  # "0" established, "1" unfamiliar, "?" unknown
    # Phase 5b (F-18): a known, authenticated sender forwarding a message (e.g. a phish reported to IT).
    # Links and requests AFTER the forwarded-message marker are treated as reported content.
    trusted_forward: bool = False

    @property
    def relationship_available(self) -> bool:
        return self.req.relationship is not None

    @property
    def known_regs(self) -> frozenset[str]:
        rel = self.req.relationship
        return frozenset(registrable(d) for d in rel.known_domains) if rel else frozenset()

    @classmethod
    def build(cls, req: AnalyzeRequest) -> "Context":
        m = req.message
        sender = Address.parse(m.from_header)
        reply_to = Address.parse(m.reply_to) if m.reply_to else None
        auth = parse_topmost(m.auth_results)
        is_bulk = m.list_unsubscribe or (m.precedence or "").strip().lower() in {"bulk", "list", "junk"}
        body = parse_html(m.html_body) if m.html_body else ParsedBody(visible_text=m.text_body[:100_000])
        links = body.links if m.html_body else links_from_text(m.text_body)
        dkim_regs = frozenset(registrable(d) for d in auth.dkim_domains)
        fam = _familiarity(req, sender)
        visible = body.visible_text or m.text_body
        is_fwd = bool(re.match(r"^\s*(?:fwd?|fw)\s*:", m.subject or "", re.IGNORECASE)) and bool(FORWARD_MARKER.search(visible))
        return cls(req, sender, reply_to, auth, is_bulk, body, links, dkim_regs, fam,
                   trusted_forward=is_fwd and fam == "0" and auth.passed)


def _familiarity(req: AnalyzeRequest, sender: Address) -> str:
    rel = req.relationship
    if rel is None:
        return "?"
    if rel.sender_sent_count > 0:
        return "0"
    known = {registrable(d) for d in rel.known_domains}
    # A known *organization* domain counts as established; a shared freemail domain does not.
    if sender.reg in known and not is_freemail(sender.domain):
        return "0"
    return "1"


def addresses(header: str | None) -> list[str]:
    return [a.lower() for _, a in getaddresses([header or ""]) if a]
