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
    "malware": "Opening the file can run attacker code or show a fake sign-in page.",
    "deception": "The message misrepresents who sent it or where its links lead.",
}

ACTIONS = {
    "account_takeover": [
        "Do not change any payment details or reply to this message.",
        "Call the vendor on a phone number you already have (not one from this email) to verify.",
        "Report the message to your security or finance team.",
    ],
    "payment_redirection": [
        "Verify the change by phone using contact details you already have, not ones from this email.",
        "Do not send any payment to the new account until it is confirmed.",
    ],
    "gift_cards": ["Do not buy or send any gift cards.",
                   "Contact the supposed sender through a channel you already trust."],
    "code_theft": ["Never share a verification code; legitimate services never ask for one.",
                   "If you already shared it, change your password and review account sessions."],
    "remote_access": ["Do not install the tool.", "Contact your IT team through the usual channel."],
    "impersonation": ["Do not reply. Contact the person through an address or number you already have.",
                      "Report the message to your security team."],
    "lookalike": ["Compare the sender's domain carefully with the real one.",
                  "Do not open attachments or reply; report the message."],
    "credential_phish": ["Do not click the link or enter your password.",
                         "To check your account, type the site's address yourself.",
                         "Report the message as phishing."],
    "malware": ["Do not open the attachment.", "Report the message to your security team."],
    "deception": ["Treat the message with caution and verify the sender through another channel."],
}

SUMMARY = {
    "account_takeover": "Someone is using your conversation with this vendor to redirect a payment.",
    "payment_redirection": "This email asks you to send money to new bank details.",
    "gift_cards": "This email asks you to buy gift cards, a common scam payout.",
    "code_theft": "This email asks for a verification code that protects your account.",
    "remote_access": "This email asks you to give someone remote control of your computer.",
    "impersonation": "Someone is posing as a person or organization you know.",
    "lookalike": "The sender's domain imitates one you trust.",
    "credential_phish": "This email tries to get your password through a deceptive link.",
    "malware": "The attachment could run code or show a fake sign-in page.",
    "deception": "This email misrepresents who sent it or where it leads.",
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


def actions(d: Decision, ask: AskResult, arch: str) -> list[str]:
    if d.verdict is Verdict.INCONCLUSIVE:
        return ["Don't act on the request until you've confirmed the sender another way.",
                "If you need to sign in somewhere, type the site's address yourself."]
    if arch == "none":
        if ask.level >= 2:
            return ["If you need to act, go to the site directly instead of using the link."]
        return ["No action needed."]
    return ACTIONS.get(arch, ACTIONS["deception"])


def headline(d: Decision, ask: AskResult, arch: str) -> str:
    """One sentence that summarizes; the Why rows carry the specifics, so this never repeats them."""
    asks = ask.pattern.label[0].lower() + ask.pattern.label[1:] if ask.pattern else ""
    if d.verdict is Verdict.INCONCLUSIVE:
        what = f"it asks you to {asks}" if ask.pattern and ask.level >= 2 else "it shows an anomaly"
        return f"We can't verify who sent this, and {what}."
    if d.verdict is Verdict.LOW:
        return "Nothing in this email contradicts what it claims."
    if d.gate == "S-A":
        return "A known sender with no red flags, but the request is irreversible."
    return SUMMARY.get(arch, SUMMARY["deception"])
