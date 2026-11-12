"""Archetype, Attack Story, recommendations and headline, from fixed templates (no LLM).

All text is built from our own templates plus short, length-capped excerpts. The
add-on HTML-escapes every string at render time.
"""

from .decision import Decision
from .model import Finding
from .schemas import Group, Verdict
from .signals.ask import AskResult

ARCHETYPES = {
    "account_takeover": "Vendor account takeover",
    "payment_redirection": "Payment redirection",
    "gift_cards": "Gift-card scam",
    "code_theft": "Verification-code theft",
    "remote_access": "Remote-access scam",
    "impersonation": "Impersonation (BEC)",
    "lookalike": "Look-alike domain impersonation",
    "credential_phish": "Credential phishing",
    "consent_phish": "Consent phishing",
    "pretext": "Pretext request",
    "malware": "Malicious attachment",
    "deception": "Deceptive message",
    "none": "No attack pattern",
}

CONSEQUENCE = {
    "account_takeover": "If you pay, the money goes to the attacker and is usually unrecoverable.",
    "payment_redirection": "If the change is fraudulent, payments go to the attacker and are usually unrecoverable.",
    "gift_cards": "Gift-card codes are as good as cash and cannot be traced or refunded.",
    "code_theft": "Sharing the code hands over your account even if your password is strong.",
    "remote_access": "A remote-access tool gives the sender full control of your computer.",
    "impersonation": "The next message usually asks for money, gift cards or sensitive data.",
    "lookalike": "Anything you send or open goes to an attacker-controlled domain.",
    "credential_phish": "A password typed into the linked page goes straight to the attacker.",
    "consent_phish": "An app granted access could read and send your email without your password.",
    "pretext": "Pretext messages like this often lead to a request for money, gift cards or data.",
    "malware": "Opening the file can run attacker code or show a fake sign-in page.",
    "deception": "The message misrepresents who sent it or where its links lead.",
}


_REQUEST_ARCHETYPE = {"bank_change": "payment_redirection", "payroll": "payment_redirection",
                      "gift_cards": "gift_cards", "code_relay": "code_theft", "remote_access": "remote_access"}


def archetype(d: Decision, ask: AskResult) -> str:
    if d.verdict is Verdict.LOW:
        return "none"
    sigs = {f.signal: f for f in d.kept}
    req = ask.pattern.id if ask.pattern else ""
    if req in {"bank_change", "payroll"} and "S2" in sigs and sigs["S2"].level >= 2 and \
            "existing thread" in sigs["S2"].claim:
        return "account_takeover"
    if req in _REQUEST_ARCHETYPE:
        return _REQUEST_ARCHETYPE[req]
    if d.gate == "S-P":
        return "pretext"
    if any(f.kind == "link_oauth_consent" for f in d.kept):
        return "consent_phish"
    if "S5" in sigs and sigs["S5"].level >= 2:
        return "lookalike"
    if req == "credentials" or any(f.group is Group.DEST for f in d.kept):
        return "credential_phish"
    if any(f.signal in {"S3", "S4"} for f in d.kept):
        return "impersonation"
    if "S11" in sigs:
        return "malware"
    return "deception"


def _top(d: Decision) -> Finding | None:
    order = {Group.IDENTITY: 0, Group.AUTH: 1, Group.DEST: 2, Group.PAYLOAD: 3, Group.DRIFT: 4}
    return min(d.kept, key=lambda f: (-f.level, order.get(f.group, 9)), default=None)


def story(d: Decision, ask: AskResult, arch: str) -> list[str]:
    if arch == "none":
        lines = ["Nothing in this message contradicts what it claims about itself."]
        if ask.level >= 2 and ask.pattern:
            lines.append(f"It does ask you to {ask.pattern.label[0].lower() + ask.pattern.label[1:]}. That is common "
                         "in legitimate mail, but it is also what attackers ask for.")
        return lines
    lines = []
    top = _top(d)
    if top:
        lines.append(f"The email claims: {top.claim}.")
        lines.append(f"In reality: {top.reality}.")
    if ask.pattern and ask.level >= 2:
        lines.append(f"It then asks you to {ask.pattern.label[0].lower() + ask.pattern.label[1:]}.")
    if ask.pressure and ask.cues:
        lines.append(f"It adds pressure ({', '.join(ask.cues)}) to rush you past checking.")
    if arch in CONSEQUENCE:
        lines.append(CONSEQUENCE[arch])
    return lines
