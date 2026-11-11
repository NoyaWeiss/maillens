"""Request/response contract between the add-on and the backend.

Every field from the add-on is untrusted (it is derived from an email an attacker
may have written), so every string and list has an explicit size limit and unknown
fields are rejected.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Short = Annotated[str, Field(max_length=1_000)]
Header = Annotated[str, Field(max_length=8_000)]
Body = Annotated[str, Field(max_length=200_000)]
Addr = Annotated[str, Field(max_length=320)]
Domain = Annotated[str, Field(max_length=253)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Attachment(Strict):
    name: Annotated[str, Field(max_length=255)]
    content_type: Annotated[str, Field(max_length=255)] = ""
    size: Annotated[int, Field(ge=0, le=100_000_000)] = 0


class ThreadEntry(Strict):
    """Digest of an EARLIER message in the open thread (no bodies)."""
    from_header: Short
    reply_to: Short | None = None
    auth_result: Header | None = None  # topmost Authentication-Results only
    participants: Annotated[list[Addr], Field(max_length=30)] = []


class Relationship(Strict):
    """Facts computed in the add-on from Sent-mail headers. Contacts' names are never sent."""
    window_days: Annotated[int, Field(ge=1, le=3650)] = 180
    known_domains: Annotated[list[Domain], Field(max_length=100)] = []
    sender_sent_count: Annotated[int, Field(ge=0, le=100_000)] = 0
    # Known-contact addresses whose display name equals the From display name.
    name_match_addresses: Annotated[list[Addr], Field(max_length=10)] = []


class MessageIn(Strict):
    from_header: Short
    reply_to: Short | None = None
    return_path: Short | None = None
    subject: Short = ""
    date: Short | None = None
    message_id: Short | None = None
    in_reply_to: Short | None = None
    references: Header | None = None
    auth_results: Annotated[list[Header], Field(max_length=20)] = []  # topmost first
    list_unsubscribe: bool = False
    precedence: Short | None = None
    html_body: Body = ""
    text_body: Body = ""
    attachments: Annotated[list[Attachment], Field(max_length=50)] = []


class AnalyzeRequest(Strict):
    schema_version: Literal[1] = 1
    message: MessageIn
    thread: Annotated[list[ThreadEntry], Field(max_length=5)] = []
    thread_message_count: Annotated[int, Field(ge=1, le=1000)] = 1
    relationship: Relationship | None = None  # None = relationship checks unavailable


class Verdict(StrEnum):
    LOW = "LOW"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH = "HIGH"
    INCONCLUSIVE = "INCONCLUSIVE"


class CheckState(StrEnum):
    RAN = "ran"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class Basis(StrEnum):
    OBSERVED = "OBSERVED"
    MAILBOX = "MAILBOX"
    HEURISTIC = "HEURISTIC"


class Group(StrEnum):
    AUTH = "AUTH"
    IDENTITY = "IDENTITY"
    DRIFT = "DRIFT"
    DEST = "DEST"
    PAYLOAD = "PAYLOAD"
    ASK = "ASK"


class FindingOut(BaseModel):
    signal: str
    group: Group
    entity: str
    level: int
    basis: Basis
    claim: str
    reality: str
    excerpt: str = ""
    title: str = ""     # presentation: short, address-free
    summary: str = ""   # presentation: one neutral sentence


class ReasonOut(BaseModel):
    title: str
    summary: str
    basis: str


class ActionOut(BaseModel):
    title: str
    detail: str


class CheckOut(BaseModel):
    id: str
    name: str
    state: CheckState
    note: str = ""


class RequestOut(BaseModel):
    level: int
    label: str
    excerpt: str = ""


class AnalyzeResponse(BaseModel):
    request_id: str
    verdict: Verdict
    score: int | None
    headline: str                       # one-sentence summary (main card)
    category: str                       # hedged attack category, or a status line for Low/Inconclusive
    archetype: str
    pathway: str | None
    gate: str | None
    gate_explanation: str
    vector: str
    confidence: Literal["Full", "Partial", "Limited"]
    coverage_ran: int
    coverage_applicable: int
    findings: list[FindingOut]          # one per (entity, group), strongest kept
    also_observed: list[FindingOut]     # deduplicated away by R1
    suppressed: list[str]               # guard notes, e.g. "S9 suppressed: bulk mail"
    request: RequestOut | None
    pressure_cues: list[str]
    reasons: list[ReasonOut]            # <=2, main card
    impact: str                         # cautious consequence sentence; empty for Low
    story: list[str]
    actions: list[ActionOut]            # <=2, main card
    checks: list[CheckOut]
    out_of_scope: list[str]
    assumptions: list[str]
