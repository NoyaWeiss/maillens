"""Identity and thread signals: S2, S3, S4, S5, S7. Each has an explicit false-positive guard."""

import re

from ..domains import (BRANDS, base_label, edit_distance, is_freemail, is_mixed_script, normalize_domain,
                       registrable, skeleton)
from ..model import Address, Context, Finding, SignalResult, addresses
from ..schemas import Basis, CheckState, Group
from .auth import parse_topmost


def sender_entity(ctx: Context) -> str:
    return f"domain:{ctx.sender.reg or ctx.sender.domain or 'unknown'}"


# ---------------------------------------------------------------- S2 Reply-To divergence
def s2_reply_to(ctx: Context) -> SignalResult:
    r = SignalResult()
    rt, s = ctx.reply_to, ctx.sender
    if not s.address:
        r.state = CheckState.UNAVAILABLE
        return r

    # Mid-thread change: the same sender's earlier messages in this thread had a different Reply-To.
    earlier_same_sender = [t for t in ctx.req.thread if Address.parse(t.from_header).address == s.address]
    if earlier_same_sender and rt and rt.reg != s.reg:
        earlier_regs = {Address.parse(t.reply_to).reg if t.reply_to else s.reg for t in earlier_same_sender}
        if rt.reg not in earlier_regs:
            if ctx.is_bulk:
                r.notes.append("S2 mid-thread change capped at level 1: bulk mail")
            r.findings.append(Finding(
                "S2", Group.IDENTITY, sender_entity(ctx), 1 if ctx.is_bulk else 2, Basis.OBSERVED,
                claim=f"A reply in your existing thread with {s.address}",
                reality=f"Replies now go to {rt.address}; earlier messages from this sender in the thread "
                        f"had no such Reply-To", excerpt=rt.address))
            return r

    if not rt or not rt.address or rt.reg == s.reg:
        return r
    if not is_freemail(s.domain) and is_freemail(rt.domain):
        if ctx.is_bulk:
            r.notes.append("S2 corporate-to-freemail Reply-To capped at level 1: bulk mail")
        r.findings.append(Finding(
            "S2", Group.IDENTITY, sender_entity(ctx), 1 if ctx.is_bulk else 2, Basis.OBSERVED,
            claim=f"Sent by {s.domain}",
            reality=f"Your reply would go to a personal mailbox: {rt.address}", excerpt=rt.address))
    else:
        r.findings.append(Finding(
            "S2", Group.IDENTITY, sender_entity(ctx), 1, Basis.OBSERVED,
            claim=f"Sent by {s.domain}", reality=f"Replies go to a different domain: {rt.domain}",
            excerpt=rt.address))
        r.notes.append("S2 different-domain Reply-To kept at level 1 (common for helpdesks)")
    return r


# ---------------------------------------------------------------- S3 Display-name deception
_EMBEDDED_ADDR = re.compile(r"[a-z0-9._%+-]{1,64}@([a-z0-9.-]{1,253}\.[a-z]{2,63})", re.IGNORECASE)
_VIA = re.compile(r"\((?:via|on behalf of)\b|\bvia\s+\S", re.IGNORECASE)
_ROLE_ONLY = re.compile(
    r"^(?:the\s+)?(?:it|i\.t\.)?\s*(?:support|help\s*desk|helpdesk|service\s*desk|administrator|admin|"
    r"security(?:\s+team)?|mail\s*(?:admin|administrator)|it\s+department|payroll|hr|accounts?\s+payable)"
    r"(?:\s+team)?$", re.IGNORECASE)


def s3_display_name(ctx: Context) -> SignalResult:
    r = SignalResult()
    name, s = ctx.sender.display, ctx.sender
    if not name:
        r.state = CheckState.NOT_APPLICABLE
        return r
    if _VIA.search(name):
        r.notes.append("S3 ignored 'via' platform display name")
        return r
    ent = sender_entity(ctx)

    if m := _EMBEDDED_ADDR.search(name):
        emb = registrable(m.group(1))
        if emb != s.reg and emb not in ctx.dkim_regs:
            r.findings.append(Finding(
                "S3", Group.IDENTITY, ent, 2, Basis.OBSERVED,
                claim=f"Display name shows the address {m.group(0)}",
                reality=f"The real sender is {s.address}", excerpt=name))
            return r

    lowered = " ".join(name.casefold().split())
    for brand, owned in BRANDS.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(brand)}(?![a-z0-9])", lowered) and s.reg not in owned:
            r.findings.append(Finding(
                "S3", Group.IDENTITY, ent, 2, Basis.OBSERVED,
                claim=f"Display name presents the sender as {brand.title()}",
                reality=f"The message comes from {s.reg}, which is not a {brand.title()} domain", excerpt=name))
            return r

    if _ROLE_ONLY.match(lowered):
        r.findings.append(Finding(
            "S3", Group.IDENTITY, ent, 1, Basis.OBSERVED,
            claim=f"Display name is a role title only (\"{name}\")",
            reality=f"No person or organization is named; the sender is {s.address}", excerpt=name))
    return r


# ---------------------------------------------------------------- S4 Known-contact name collision
def s4_name_collision(ctx: Context) -> SignalResult:
    r = SignalResult()
    rel = ctx.req.relationship
    if rel is None:
        r.state = CheckState.UNAVAILABLE
        return r
    tokens = ctx.sender.display.split()
    if len(tokens) < 2:
        if ctx.sender.display:
            r.notes.append("S4 skipped: display name has fewer than 2 tokens")
        return r
    named = {a.lower() for a in rel.name_match_addresses}
    if not named or ctx.sender.address in named:  # no collision, or the sender IS the known contact
        return r
    matches = named
    s, ent = ctx.sender, sender_entity(ctx)
    match_regs = {registrable(a.rsplit("@", 1)[-1]) for a in matches}
    known = ", ".join(sorted(matches)[:2])
    if len(matches) >= 2:
        level, why = 1, "the name matches several known contacts, so this is ambiguous"
    elif s.reg in match_regs:
        level, why = 1, "it is a new address on the same domain as the known contact"
    else:
        level, why = 2, ("it is a free-mail address" if is_freemail(s.domain) else "it is on an unrelated domain")
    r.findings.append(Finding(
        "S4", Group.IDENTITY, ent, level, Basis.MAILBOX,
        claim=f"From \"{s.display}\", a person you've corresponded with",
        reality=f"You know {s.display} as {known}; this message comes from {s.address} ({why})",
        excerpt=s.address))
    return r


# ---------------------------------------------------------------- S5 Lookalike domain
def s5_lookalike(ctx: Context) -> SignalResult:
    r = SignalResult()
    s = ctx.sender
    if not s.reg:
        r.state = CheckState.UNAVAILABLE
        return r
    known = ctx.known_regs
    if s.reg in known:
        return r  # guard: a known correspondent is never its own lookalike
    cand = base_label(s.reg)
    references = [(d, "a domain you correspond with") for d in sorted(known)]
    references += [(d, f"{brand.title()}'s domain") for brand, owned in BRANDS.items() for d in sorted(owned)]

    if is_mixed_script(cand):
        r.findings.append(Finding(
            "S5", Group.IDENTITY, sender_entity(ctx), 3, Basis.OBSERVED,
            claim=f"Sender domain {s.reg}", reality="The domain mixes alphabets (e.g. Latin and Cyrillic), "
                                                  "a deliberate spoofing construct", excerpt=s.reg))
        return r

    best: tuple[int, str, str] | None = None
    for ref, why in references:
        ref_label = base_label(ref)
        if ref_label == cand:
            continue
        if skeleton(cand) == skeleton(ref_label):
            best = (3, ref, why)
            break
        if len(ref_label) >= 6:
            dist = edit_distance(cand, ref_label, cap=2)
            lvl = 2 if dist == 1 else 1 if dist == 2 else 0
            if lvl and (best is None or lvl > best[0]):
                best = (lvl, ref, why)
    if best:
        lvl, ref, why = best
        how = "uses look-alike characters" if lvl == 3 else f"differs by {3 - lvl} character(s)"
        basis = Basis.MAILBOX if ref in known else Basis.OBSERVED
        r.findings.append(Finding(
            "S5", Group.IDENTITY, sender_entity(ctx), lvl, basis,
            claim=f"Looks like {ref} ({why})", reality=f"Actually {s.reg}, which {how}", excerpt=s.reg))
    if ctx.req.relationship is None:
        r.state = CheckState.UNAVAILABLE  # brand list ran; the relationship half could not
        r.notes.append("S5 compared against the brand list only (relationship data unavailable)")
    return r


# ---------------------------------------------------------------- S7 Thread anomaly (level 1 only)
def s7_thread(ctx: Context) -> SignalResult:
    r = SignalResult()
    m, s = ctx.req.message, ctx.sender
    ent = sender_entity(ctx)
    if re.match(r"^\s*re\s*:", m.subject or "", re.IGNORECASE) and not (m.in_reply_to or m.references):
        r.findings.append(Finding(
            "S7", Group.DRIFT, ent, 1, Basis.OBSERVED, claim="Subject says it is a reply (\"Re:\")",
            reality="The message is not linked to any earlier message", excerpt=m.subject[:120]))
    thread = ctx.req.thread
    if not thread:
        return r
    seen = set()
    for t in thread:
        seen.add(Address.parse(t.from_header).address)
        seen.update(a.lower() for a in t.participants)
    if s.address and s.address not in seen:
        r.findings.append(Finding(
            "S7", Group.DRIFT, ent, 1, Basis.OBSERVED, claim="A message in an existing conversation",
            reality=f"{s.address} has not appeared anywhere earlier in this thread"))
    earlier_dkim = {registrable(d) for t in thread if Address.parse(t.from_header).address == s.address
                    for d in parse_topmost([t.auth_result] if t.auth_result else []).dkim_domains}
    if earlier_dkim and ctx.dkim_regs and not (earlier_dkim & ctx.dkim_regs):
        r.findings.append(Finding(
            "S7", Group.DRIFT, ent, 1, Basis.OBSERVED,
            claim="Same sender as earlier in this thread",
            reality=f"Signed by {', '.join(sorted(ctx.dkim_regs))} now, but by "
                    f"{', '.join(sorted(earlier_dkim))} earlier"))
    return r
