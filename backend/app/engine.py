"""Orchestration: context -> signals -> decision core -> narrative -> response."""

from .decision import Decision, decide, explain_gate
from .model import Context, Finding, SignalResult
from . import presentation
from .narrative import ARCHETYPES, archetype, story
from .schemas import (ActionOut, AnalyzeRequest, AnalyzeResponse, Basis, CheckOut, CheckState, DetailOut,
                      FindingOut, Group, ReasonOut, RequestOut)
from .signals import auth as s1
from .signals.ask import s13_s14
from .signals.dest import known_contact_offsite_share, offsite_links, s9_link_deception, s10_url_construction
from .signals.identity import s2_reply_to, s3_display_name, s4_name_collision, s5_lookalike, s7_thread, sender_entity
from .signals.payload import s11_attachments, s12_obfuscation

CHECK_NAMES = {
    "S1": "Authentication (Google's topmost result)", "S2": "Reply-To divergence", "S3": "Display-name deception",
    "S4": "Known-contact name collision", "S5": "Look-alike domain", "S6": "Sender familiarity",
    "S7": "Thread anomaly", "S9": "Link deception", "S10": "Deceptive URL construction",
    "S11": "Risky attachment (metadata)", "S12": "Hidden content / scanner targeting",
    "S13": "High-impact request", "S14": "Pressure and secrecy",
}
OUT_OF_SCOPE = ["URL reputation / threat-intelligence lookups", "Attachment contents (no sandbox)",
                "Sender IP reputation", "Text inside images", "Non-English request patterns"]
ASSUMPTIONS = [
    "Authentication is read only from the topmost Authentication-Results header written by mx.google.com.",
    "\"Known\" means you sent mail to that address or domain recently; it is not a statistical model.",
    "The bulk-mail flag (List-Unsubscribe/Precedence) only downgrades weak findings; it never hides "
    "level-3 or authentication findings.",
    "The risk index (0-100) is a position within the verdict band, not a probability that the email is malicious.",
]


def _s1(ctx: Context) -> SignalResult:
    r = SignalResult()
    if not ctx.auth.trusted:
        r.state = CheckState.UNAVAILABLE
        r.notes.append("S1 unavailable: no Authentication-Results from mx.google.com (e.g. forwarded or imported mail)")
        return r
    lvl = s1.level(ctx.auth)
    if lvl:
        a = ctx.auth
        r.findings.append(Finding.of("auth_failed", 
            "S1", Group.AUTH, sender_entity(ctx), lvl, Basis.OBSERVED,
            claim=f"Sent by {ctx.sender.domain or 'the From domain'}",
            reality=f"Authentication failed: DMARC {a.dmarc or 'none'} (policy {a.dmarc_policy or 'none'}), "
                    f"SPF {a.spf or 'none'}, DKIM {a.dkim or 'none'}"))
    elif ctx.auth.spf in {"fail", "softfail"}:
        r.notes.append("S1 SPF failure ignored: DKIM/DMARC pass (typical of forwarding)")
    return r


SIGNALS = [("S1", _s1), ("S2", s2_reply_to), ("S3", s3_display_name), ("S4", s4_name_collision),
           ("S5", s5_lookalike), ("S7", s7_thread), ("S9", s9_link_deception), ("S10", s10_url_construction),
           ("S11", s11_attachments), ("S12", s12_obfuscation)]


def _out(f: Finding, ctx: Context) -> FindingOut:
    title, summary = presentation.finding_text(f)
    return FindingOut(signal=f.signal, group=f.group, entity=f.entity, level=f.level, basis=f.basis,
                      claim=f.claim[:300], reality=f.reality[:300], excerpt=f.excerpt[:160],
                      title=title, summary=summary,
                      details=[DetailOut(label=a, value=b) for a, b in presentation.evidence_details(f, ctx)])


def analyze(req: AnalyzeRequest, request_id: str) -> tuple[AnalyzeResponse, Decision]:
    ctx = Context.build(req)
    findings: list[Finding] = []
    notes: list[str] = []
    states: dict[str, CheckState] = {}
    for sid, fn in SIGNALS:
        res = fn(ctx)
        findings += res.findings
        notes += res.notes
        states[sid] = res.state
    states["S6"] = CheckState.UNAVAILABLE if ctx.familiarity == "?" else CheckState.RAN

    ask = s13_s14(ctx)
    states["S13"] = states["S14"] = CheckState.RAN
    if ask.note:
        notes.append(ask.note)

    from .signals.action import action_in_context
    from .signals.ask import _scan_text
    aic, _action, _contexts = action_in_context(ctx, _scan_text(ctx), any(f.signal == "S11" for f in findings))
    d = decide(findings, ask.level, ask.pressure, ctx.familiarity, auth_available=states["S1"] is CheckState.RAN,
               action_in_context=aic,
               pretext_secrecy=ask.pretext_secrecy,
               credential_offsite=bool((ask.pattern and ask.pattern.id == "credentials" and offsite_links(ctx))
                                       or known_contact_offsite_share(ctx)))
    arch = archetype(d, ask)

    ran = sum(1 for s in states.values() if s is CheckState.RAN)
    unavailable = sum(1 for s in states.values() if s is CheckState.UNAVAILABLE)
    if states["S1"] is CheckState.UNAVAILABLE or any(states[s] is CheckState.UNAVAILABLE for s in ("S4", "S5", "S6")):
        confidence = "Limited"
    elif unavailable:
        confidence = "Partial"
    else:
        confidence = "Full"

    pres = presentation.build(d, ask, arch, ran)
    resp = AnalyzeResponse(
        request_id=request_id, verdict=d.verdict, score=d.score, headline=pres["summary"],
        category=pres["category"], archetype=ARCHETYPES[arch], pathway=d.pathway, gate=d.gate, gate_explanation=explain_gate(d),
        vector=d.vector, confidence=confidence, coverage_ran=ran, coverage_applicable=ran + unavailable,
        findings=[_out(f, ctx) for f in sorted(d.kept, key=lambda f: (-f.level, f.signal))],
        also_observed=[_out(f, ctx) for f in d.also_observed],
        suppressed=list(dict.fromkeys(notes))[:30],
        request=RequestOut(level=ask.level, label=ask.pattern.label, excerpt=ask.excerpt[:240], source=ask.source)
        if ask.pattern else None,
        pressure_cues=ask.cues or [],
        reasons=[ReasonOut(title=r.title, summary=r.summary, basis=r.basis) for r in pres["reasons"]],
        impact=pres["impact"], story=story(d, ask, arch),
        actions=[ActionOut(title=a.title, detail=a.detail) for a in pres["actions"]],
        checks=[CheckOut(id=k, name=CHECK_NAMES[k], state=states[k], label=presentation.CHECK_LABEL[k],
                         note=presentation.check_note(k, states[k])) for k in CHECK_NAMES],
        out_of_scope=OUT_OF_SCOPE, assumptions=ASSUMPTIONS,
        decision_explanation=presentation.decision_explanation(d),
        safeguards=presentation.safeguards(notes),
        limitations=presentation.email_limitations(ctx, {k: getattr(v, 'value', v) for k, v in states.items()}),
    )
    return resp, d
