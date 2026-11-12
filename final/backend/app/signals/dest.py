"""Link signals: S9 link deception, S10 deceptive URL construction.

URLs are parsed, never fetched. Findings are keyed by the link's registrable domain,
so S9 and S10 on the same URL merge into one DEST finding (R1).
"""

import ipaddress
import re
from urllib.parse import unquote, urlsplit

from ..domains import BRANDS, ESP_TRACKERS, SHORTENERS, defang, normalize_domain, registrable
from ..model import Context, Finding, SignalResult
from ..schemas import Basis, CheckState, Group

_ZERO_WIDTH = re.compile("[​‌‍⁠﻿­]")
_DOMAINISH = re.compile(r"^(?:https?://)?(?:www\.)?([a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63})+)(?:[/:?#]\S*)?$",
                        re.IGNORECASE)
_BRAND_DOMAINS = {d for owned in BRANDS.values() for d in owned}
_BRAND_REGS = frozenset(_BRAND_DOMAINS)

# OAuth consent links that ask a third-party app for mailbox access (RC4, consent phishing).
# Legitimate "Sign in with Google/Microsoft" links request identity scopes, not mail.
_OAUTH_HOSTS = {"google.com", "microsoftonline.com", "live.com", "microsoft.com"}
_OAUTH_PATH = re.compile(r"/o/oauth2|/oauth2/(?:v2\.0/)?authorize", re.IGNORECASE)
_MAIL_SCOPE = re.compile(r"mail\.google\.com|/auth/gmail|\bMail\.(?:Read|ReadWrite|Send)|\bIMAP\.AccessAsUser", re.IGNORECASE)


def _host(href: str) -> tuple[str, str, int | None]:
    """Returns (host, userinfo, port) or ('', '', None) for non-http links."""
    try:
        parts = urlsplit(href.strip())
        if parts.scheme.lower() not in {"http", "https"}:
            return "", "", None
        netloc = parts.netloc
        userinfo = netloc.rsplit("@", 1)[0] if "@" in netloc else ""
        return normalize_domain(parts.hostname or ""), userinfo, parts.port
    except ValueError:
        return "", "", None


def _http_links(ctx: Context):
    for link in ctx.links:
        if ctx.trusted_forward and link.forwarded:
            continue  # reported content forwarded by a known, authenticated colleague (F-18)
        host, userinfo, port = _host(link.href)
        if host:
            yield link, host, userinfo, port


# Recognized file-sharing / e-signature services: a known contact sharing through these is normal.
FILE_SHARE = frozenset({"box.com", "wetransfer.com", "notion.so", "figma.com", "egnyte.com"}) | frozenset(
    d for owned in BRANDS.values() for d in owned)
_SHARE_WORDS = re.compile(r"\b(?:shared?|uploaded|sent you|review|view|open|access)\b[^.!?\n]{0,60}\b(?:file|document|proposal|"
                          r"contract|sow|invoice|statement|folder|pdf|deck|link)\b", re.IGNORECASE)


def known_contact_offsite_share(ctx: Context) -> bool:
    """Phase 5c: a KNOWN contact shares a document through an unrelated, never-seen, non-file-sharing domain
    (typical of a compromised mailbox). Familiar senders only; unknown senders' links are not evidence."""
    if ctx.familiarity != "0" or not _SHARE_WORDS.search(ctx.body.visible_text or ""):
        return False
    return any(reg not in FILE_SHARE for reg in offsite_links(ctx))


def offsite_links(ctx: Context) -> list[str]:
    """Visible links to a domain unrelated to the sender, its signing domain, known correspondents and ESPs."""
    related = {ctx.sender.reg} | set(ctx.dkim_regs) | set(ctx.known_regs) | set(ESP_TRACKERS)
    return [registrable(h) for l, h, _, _ in _http_links(ctx) if not l.hidden and registrable(h) not in related]


def s9_link_deception(ctx: Context) -> SignalResult:
    r = SignalResult()
    links = list(_http_links(ctx))
    if not links:
        r.state = CheckState.NOT_APPLICABLE
        return r
    trusted = {ctx.sender.reg} | set(ctx.dkim_regs)
    for link, host, _, _ in links:
        href_reg = registrable(host)
        m = _DOMAINISH.match(link.text.strip())
        if not m:
            continue  # guard: anchor text that isn't a URL ("Read more") is ignored
        shown_reg = registrable(m.group(1))
        if shown_reg == href_reg:
            continue
        # Text showing a well-known brand's domain that the sender doesn't own is impersonation wherever the
        # link really goes, so neither the own-domain guard nor bulk leniency applies to it (Phase 5b).
        brand_text = shown_reg in _BRAND_REGS and ctx.sender.reg not in _BRAND_REGS
        if (href_reg in trusted or href_reg in ESP_TRACKERS) and not brand_text:
            r.notes.append(f"S9 skipped {href_reg}: signing domain or known email provider")
            continue
        level = 1 if ctx.is_bulk and not brand_text else 2
        if ctx.is_bulk and not brand_text:
            r.notes.append("S9 downgraded to level 1: bulk mail")
        r.findings.append(Finding.of("link_text_mismatch", 
            "S9", Group.DEST, f"domain:{href_reg}", level, Basis.OBSERVED,
            claim=f"Link text shows {defang(shown_reg)}",
            reality=f"The link actually opens {defang(host)}", excerpt=defang(link.href[:150])))
    return r


def s10_url_construction(ctx: Context) -> SignalResult:
    r = SignalResult()
    links = list(_http_links(ctx))
    if not links:
        r.state = CheckState.NOT_APPLICABLE
        return r
    for link, host, userinfo, port in links:
        reg = registrable(host)
        ent, ex = f"domain:{reg}", defang(link.href[:150])
        if userinfo and re.search(r"[a-z0-9-]+\.[a-z]{2,}", userinfo, re.IGNORECASE):
            r.findings.append(Finding.of("link_userinfo_trick", 
                "S10", Group.DEST, ent, 3, Basis.OBSERVED, claim=f"Link appears to point to {defang(userinfo)}",
                reality=f"Everything before '@' is ignored; it really opens {defang(host)}", excerpt=ex))
            continue
        try:
            ipaddress.ip_address(host.strip("[]"))
            r.findings.append(Finding.of("link_ip_host", "S10", Group.DEST, ent, 2, Basis.OBSERVED, claim="A web link",
                                      reality=f"Points to a raw IP address ({defang(host)}), not a named site",
                                      excerpt=ex))
            continue
        except ValueError:
            pass
        sub = host[: -len(reg)].rstrip(".") if reg and host.endswith(reg) else ""
        hit = next((b for b in _BRAND_DOMAINS if sub and re.search(rf"(?:^|\.){re.escape(b)}(?:\.|$)", sub)), None)
        if hit and reg not in {registrable(hit)}:
            r.findings.append(Finding.of("link_brand_prefix", 
                "S10", Group.DEST, ent, 2, Basis.OBSERVED, claim=f"Link looks like {hit}",
                reality=f"{hit} is only a prefix; the site is really {defang(reg)}", excerpt=ex))
            continue
        if reg in _OAUTH_HOSTS and _OAUTH_PATH.search(link.href) and _MAIL_SCOPE.search(unquote(link.href)):
            r.findings.append(Finding.of("link_oauth_consent",
                "S10", Group.DEST, ent, 2, Basis.OBSERVED, claim="A document or sign-in link",
                reality="It opens a consent screen asking an app for access to your email", excerpt=ex))
            continue
        if port and port not in {80, 443}:
            r.findings.append(Finding.of("link_odd_port", "S10", Group.DEST, ent, 2, Basis.OBSERVED, claim="A web link",
                                      reality=f"Uses an unusual port ({port})", excerpt=ex))
            continue
        if reg in SHORTENERS:
            if ctx.is_bulk:
                r.notes.append("S10 shortener ignored: bulk mail")
                continue
            r.findings.append(Finding.of("link_shortener", "S10", Group.DEST, ent, 1, Basis.OBSERVED, claim="A web link",
                                      reality=f"Hidden behind a URL shortener ({reg})", excerpt=ex))
    return r


def zero_width_in_links(ctx: Context) -> list[str]:
    return [link.href for link in ctx.links if _ZERO_WIDTH.search(link.href) or _ZERO_WIDTH.search(link.text)]
