"""S1: authentication results.

Only the topmost Authentication-Results header is considered, and only if its
authserv-id is Google's. Anything below it may have been written by the sender
(RFC 8601 sections 5 and 7.1), so it is ignored.
"""

import re
from dataclasses import dataclass

TRUSTED_AUTHSERV_IDS = frozenset({"mx.google.com"})

_METHOD_RE = re.compile(r"\b(spf|dkim|dmarc)\s*=\s*([a-z]+)", re.IGNORECASE)
_DMARC_POLICY_RE = re.compile(r"\bdmarc\s*=\s*[a-z]+\s*\(([^)]{0,200})\)", re.IGNORECASE)
_POLICY_RE = re.compile(r"\bp\s*=\s*([a-z]+)", re.IGNORECASE)
_DKIM_DOMAIN_RE = re.compile(
    r"\bdkim\s*=\s*pass\b[^;]{0,300}?header\.(?:i|d)\s*=\s*(?:[^@\s;]{0,64}@)?([a-z0-9.-]{1,253})", re.IGNORECASE)


@dataclass(frozen=True)
class AuthResult:
    trusted: bool
    spf: str | None = None
    dkim: str | None = None
    dmarc: str | None = None
    dmarc_policy: str | None = None
    dkim_domains: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.trusted and self.dmarc == "pass"


def parse_topmost(headers: list[str]) -> AuthResult:
    """Parse the first Authentication-Results header, if Google wrote it."""
    if not headers:
        return AuthResult(trusted=False)
    top = headers[0][:8_000]
    authserv_id = top.split(";", 1)[0].strip().lower()
    if authserv_id not in TRUSTED_AUTHSERV_IDS:
        return AuthResult(trusted=False)

    results: dict[str, str] = {}
    for method, value in _METHOD_RE.findall(top):
        results.setdefault(method.lower(), value.lower())  # first occurrence wins

    policy = None
    if m := _DMARC_POLICY_RE.search(top):
        if p := _POLICY_RE.search(m.group(1)):
            policy = p.group(1).lower()

    dkim_domains = tuple(dict.fromkeys(d.lower().rstrip(".") for d in _DKIM_DOMAIN_RE.findall(top)))
    return AuthResult(trusted=True, spf=results.get("spf"), dkim=results.get("dkim"),
                      dmarc=results.get("dmarc"), dmarc_policy=policy, dkim_domains=dkim_domains)


def level(a: AuthResult) -> int:
    """Spec S1 levels. Missing/untrusted header is handled by the caller as 'unavailable'."""
    if a.dmarc == "fail":
        return 2 if a.dmarc_policy in {"quarantine", "reject"} else 1
    if a.dmarc in {None, "none"} and a.spf == "fail" and a.dkim == "fail":
        return 1
    return 0  # pass, SPF-only fail with DKIM pass (forwarding), softfail
