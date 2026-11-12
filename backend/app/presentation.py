"""User-facing wording for the main card (Phase 2 v3, docs/UI_PROPOSAL.md).

Presentation only: everything here reads an existing Decision and never influences it
(tests/test_golden.py proves decisions are unchanged). Rules the wording follows:
- No raw addresses, URLs or header text: those stay in the technical evidence.
- Observed facts are stated plainly; inferred intent is hedged ("Possible ...", "could").
- Short: titles <= 5 words, one sentence per summary, so lines stay readable when right-aligned.
"""

from dataclasses import dataclass

from .decision import Decision
from .model import Finding
from .schemas import Basis, Verdict
from .signals.ask import AskResult, defang_text

BASIS_TAG = {Basis.OBSERVED: "Seen in this email", Basis.MAILBOX: "From your email history",
             Basis.HEURISTIC: "Based on the wording"}
LIMITED_TAG = "Limited evidence"


@dataclass(frozen=True)
class Reason:
    title: str
    summary: str
    basis: str


@dataclass(frozen=True)
class Action:
    title: str
    detail: str


# ---------------------------------------------------------------- findings: (title, summary) per kind
_FINDING_TEXT = {
    "auth_failed": ("Sender authentication failed",
                    "The sender's domain did not vouch for this message."),
    "reply_mid_thread": ("Reply address changed",
                         "Replies now go to a different address than earlier messages in this thread."),
    "reply_freemail": ("Replies go to a personal mailbox",
                       "Replies would reach a free email account, not the sender's organization."),
    "reply_other_domain": ("Different reply domain",
                           "Replies would go to a different domain than the sender's."),
    "display_embedded_address": ("Misleading sender name",
                                 "The sender's name shows an address that isn't the real sender."),
    "display_brand_mismatch": ("Brand name doesn't match sender",
                               "The sender uses a known brand's name but not its domain."),
    "display_role_only": ("Generic sender name",
                          "The sender is identified only by a role, such as a help desk."),
    "known_name_new_address": ("Known name, unfamiliar address",
                               "It uses the name of someone you email, from a different address."),
    "lookalike_mixed_script": ("Look-alike domain",
                               "The sender's domain mixes alphabets to imitate a familiar name."),
    "lookalike_domain": ("Look-alike domain",
                         "The sender's domain imitates one you know."),
    "thread_fake_reply": ("Looks like a reply, isn't one",
                          "The subject says \"Re:\" but the email isn't linked to an earlier message."),
    "thread_new_sender": ("New sender in this thread",
                          "This sender hasn't appeared earlier in the conversation."),
    "thread_signer_changed": ("Sender's signature changed",
                              "It is signed differently from this sender's earlier messages here."),
    "link_text_mismatch": ("Link doesn't go where it says",
                           "A link shows one website but opens a different one."),
    "link_userinfo_trick": ("Disguised link",
                            "A link uses a misleading format to hide its real destination."),
    "link_ip_host": ("Link to a raw IP address",
                     "A link points to a numeric address instead of a named website."),
    "link_brand_prefix": ("Misleading link domain",
                          "A link starts with a known brand name but leads to a different site."),
    "link_odd_port": ("Unusual link",
                      "A link uses an unusual network port."),
    "link_oauth_consent": ("Asks an app for mailbox access",
                           "A link opens a real sign-in consent screen that would give an app access to your email."),
    "link_shortener": ("Shortened link",
                       "A link hides its destination behind a URL shortener."),
    "attach_double_ext": ("Disguised program file",
                          "An attachment looks like a document but is a program."),
    "attach_executable": ("Executable attachment",
                          "An attachment is a file type that can run code."),
    "attach_html": ("Web-page attachment",
                    "An attached web page can imitate a sign-in screen."),
    "attach_macro": ("Macro-enabled document",
                     "An attached document can run macros."),
    "attach_protected_archive": ("Password-protected archive",
                                 "Its contents are hidden from security scanning."),
    "hidden_scanner_bait": ("Hidden text aimed at scanners",
                            "Invisible text tries to convince security tools the email is safe."),
    "hidden_block": ("Hidden content",
                     "The email contains a large block of text you can't see."),
    "obfuscated_text": ("Disguised wording",
                        "Words contain invisible or look-alike characters, a common way to slip past filters."),
    "hidden_zero_width": ("Hidden characters in a link",
                          "A link contains invisible characters often used to evade filters."),
}

# Level-specific wording where the meaning differs (title/summary must not overstate weak evidence).
_LEVEL_OVERRIDES = {
    ("auth_failed", 1): ("Weak sender authentication", "The sender's authentication checks did not fully pass."),
    ("known_name_new_address", 1): ("Known name, new address",
                                    "It uses a familiar name from a new address; this is often harmless."),
    ("lookalike_domain", 3): ("Look-alike domain",
                              "The sender's domain uses look-alike characters to imitate one you know."),
    ("lookalike_domain", 1): ("Similar domain", "The sender's domain is close to one you know."),
}


def finding_text(f: Finding) -> tuple[str, str]:
    return _LEVEL_OVERRIDES.get((f.kind, f.level)) or _FINDING_TEXT.get(f.kind) or (f.claim[:60], f.reality[:140])


# ---------------------------------------------------------------- requests: (title, summary) per pattern id
_REQUEST_TEXT = {
    "bank_change": ("Asks to change bank details", "It asks you to pay a new account."),
    "gift_cards": ("Asks you to buy gift cards", "Gift cards are a common way for scammers to get paid."),
    "payroll": ("Asks to change payroll details", "It asks you to redirect salary payments."),
    "code_relay": ("Asks for a verification code", "Sharing it could give someone access to your account."),
    "remote_access": ("Asks you to install remote access", "It would let someone control your computer."),
    "credentials": ("Asks you to sign in", "It links to a sign-in page."),
    "card_update": ("Asks for card details", "It asks you to update payment card details."),
    "enable_content": ("Asks you to enable content", "Enabling content in a document can run code."),
    "channel_move": ("Asks to move off email", "It asks you to continue on another channel."),
    "favor_probe": ("Unexplained favor request", "It asks if you're free for a favor without saying what."),
}

# ---------------------------------------------------------------- per archetype: category, summary, impact, actions
_CATEGORY = {
    "account_takeover": "Possible vendor impersonation",
    "payment_redirection": "Possible payment fraud",
    "gift_cards": "Possible gift-card scam",
    "code_theft": "Possible account-takeover attempt",
    "remote_access": "Possible remote-access scam",
    "impersonation": "Possible impersonation",
    "lookalike": "Look-alike sender domain",          # observed fact, not an inference
    "credential_phish": "Possible credential phishing",
    "consent_phish": "Possible consent phishing",
    "pretext": "Possible pretext for fraud",
    "malware": "Risky attachment",                    # observed fact
    "deception": "Deceptive email",
}
_SUMMARY = {
    "account_takeover": "A reply in a vendor thread asks you to send money to new bank details.",
    "payment_redirection": "This email asks you to send money to new bank details.",
    "gift_cards": "This email asks you to buy gift cards.",
    "code_theft": "This email asks you to share a verification code.",
    "remote_access": "This email asks you to install a remote-access tool.",
    "impersonation": "The sender's name doesn't match where the email really comes from.",
    "lookalike": "The sender's domain imitates one you correspond with.",
    "credential_phish": "This email asks you to sign in, and parts of it are deceptive.",
    "consent_phish": "A link asks you to give an app access to your email.",
    "pretext": "An unfamiliar sender asks for an unexplained favor and asks you to keep it secret.",
    "malware": "An attachment is a file type that can run code or imitate a sign-in page.",
    "deception": "Parts of this email misrepresent who sent it or where it leads.",
}
_IMPACT = {
    "account_takeover": "Payment could be redirected to an attacker-controlled account and may be difficult to recover.",
    "payment_redirection": "Payment could be redirected to an attacker-controlled account and may be difficult to recover.",
    "gift_cards": "Gift card codes could be spent immediately and are rarely refundable.",
    "code_theft": "Sharing the code could give someone access to your account.",
    "remote_access": "A remote-access tool could give someone control of your computer.",
    "impersonation": "Replying could lead to requests for money or sensitive information.",
    "lookalike": "Replies, payments or files could reach an impostor.",
    "credential_phish": "A password entered on the linked page could be stolen.",
    "consent_phish": "An app granted access could read and send your email, even without your password.",
    "pretext": "Messages like this may be a first step toward a request for money, gift cards or data.",
    "malware": "Opening the attachment could run harmful code or show a fake sign-in page.",
    "deception": "Acting on this email could expose you to fraud.",
}
_ACTIONS = {
    "account_takeover": [Action("Verify with the vendor", "Call a number you already trust before changing any payment details."),
                         Action("Don't reply to this email", "Replies may reach the attacker.")],
    "payment_redirection": [Action("Verify by phone", "Use contact details you already have, not ones in this email.")],
    "gift_cards": [Action("Don't buy gift cards", "Confirm the request with the person through a channel you trust.")],
    "code_theft": [Action("Don't share the code", "Legitimate services never ask for it by email.")],
    "remote_access": [Action("Don't install anything", "Contact your IT team through the usual channel.")],
    "impersonation": [Action("Contact the person directly", "Use an address or number you already have, not this email.")],
    "lookalike": [Action("Don't reply or open attachments", "Report the email to your security team.")],
    "credential_phish": [Action("Don't use the link", "If you need to sign in, type the site's address yourself."),
                         Action("Report it as phishing", "Use Gmail's \"Report phishing\" option.")],
    "malware": [Action("Don't open the attachment", "Report the email to your security team.")],
    "pretext": [Action("Verify the sender another way", "Contact the person through a channel you already trust before replying.")],
    "consent_phish": [Action("Don't grant access", "Don't approve the app on the consent screen."),
                      Action("Remove it if you already did", "Revoke the app in your account's security settings.")],
    "deception": [Action("Verify the sender another way", "Use a channel you already trust before acting.")],
}


def _request_reason(ask: AskResult) -> Reason | None:
    if not ask.pattern or ask.level < 2:
        return None
    title, summary = _REQUEST_TEXT.get(ask.pattern.id, (ask.pattern.label, ""))
    return Reason(title, summary or ask.pattern.label + ".", BASIS_TAG[Basis.HEURISTIC])


def build(d: Decision, ask: AskResult, arch: str, checks_ran: int) -> dict:
    """Returns category, summary, reasons (<=2), impact and actions (<=2) for the main card."""
    req = _request_reason(ask)
    strongest = sorted(d.kept, key=lambda f: (-f.level, f.signal))

    if d.verdict is Verdict.LOW:
        actions = [Action("Go to the site directly", "Open the site yourself instead of using the link in the email.")] \
            if req else []
        return {"category": f"{checks_ran} checks ran", "summary": "Nothing in this email contradicts what it claims.",
                "reasons": [], "impact": "", "actions": actions}

    if d.verdict is Verdict.INCONCLUSIVE:
        reasons = [Reason("Sender can't be verified",
                          "No authentication results were found, which is common for forwarded mail.", LIMITED_TAG)]
        reasons.append(req or Reason(*finding_text(strongest[0]), BASIS_TAG[strongest[0].basis]))
        asks = f"it asks you to {ask.pattern.label[0].lower() + ask.pattern.label[1:]}" \
            if req else "something in it looks unusual"
        impact = ("If this is phishing, a password entered on the linked page could be stolen."
                  if ask.pattern and ask.pattern.id == "credentials"
                  else "If this email isn't genuine, acting on it could expose you to fraud.")
        act = "signing in" if ask.pattern and ask.pattern.id == "credentials" else "acting on it"
        return {"category": "Sender could not be verified",
                "summary": f"We can't confirm who sent this, and {asks}.",
                "reasons": reasons[:2], "impact": impact,
                "actions": [Action("Confirm with the sender", f"Use a channel you already trust before {act}.")]}

    # HIGH and SUSPICIOUS
    if d.gate == "S-A":  # irreversible request, nothing else wrong
        reasons = [r for r in (req, Reason("Sender is known to you", "Nothing else in the email looks wrong.",
                                           BASIS_TAG[Basis.MAILBOX]) if d.N == "0" else None) if r]
        return {"category": _CATEGORY.get(arch, "Possible payment fraud"),
                "summary": "A known sender asks for a payment change that is hard to undo." if d.N == "0"
                else "This email asks for a change that is hard to undo.",
                "reasons": reasons[:2],
                "impact": "If the request isn't genuine, payments could go to the wrong account.",
                "actions": _ACTIONS.get(arch, _ACTIONS["payment_redirection"])[:1]}

    reasons = [Reason(*finding_text(strongest[0]), BASIS_TAG[strongest[0].basis])] if strongest else []
    if req:
        reasons.append(req)
    elif len(strongest) > 1:
        reasons.append(Reason(*finding_text(strongest[1]), BASIS_TAG[strongest[1].basis]))
    summary = _SUMMARY.get(arch, _SUMMARY["deception"])
    if arch == "credential_phish" and not (ask.pattern and ask.pattern.id == "credentials"):
        summary = "A link in this email is not what it appears to be."
    return {"category": _CATEGORY.get(arch, _CATEGORY["deception"]),
            "summary": summary,
            "reasons": reasons[:2], "impact": _IMPACT.get(arch, _IMPACT["deception"]),
            "actions": _ACTIONS.get(arch, _ACTIONS["deception"])[:2]}


# ================================================================ Detailed analysis (v4)
_DECISION = {
    "H-A": "One deliberate deception technique was found. On its own, that is enough for High risk.",
    "H-B": "A strong warning sign appeared together with a risky request. Together, they make this High risk.",
    "H-B2": "Strong warning signs were found in two separate parts of the email. Together, they make this High risk.",
    "H-C": "The email asks for something hard to undo, and other signals support the concern. That makes it High risk.",
    "S-D": "One strong warning sign was found, but nothing else confirms it. That makes it Suspicious.",
    "S-A": "The email asks for something hard to undo. Nothing else looks wrong, but the request alone deserves verification.",
    "S-P": "An unfamiliar sender asks for an unexplained favor and asks you to keep it secret. That combination is a common opening for fraud.",
    "INC": "The sender couldn't be verified, and the email contains a risky request or an anomaly. "
           "Rating it Low would be misleading, so the result is Inconclusive.",
    None: "No check found a contradiction between what the email claims and what was observed.",
}


def decision_explanation(d: Decision) -> str:
    key = "H-B2" if d.gate == "H-B" and d.A < 2 else d.gate
    return _DECISION.get(key, _DECISION[None])


CHECK_LABEL = {
    "S1": "Sender authentication", "S2": "Reply address", "S3": "Display name", "S4": "Known contacts",
    "S5": "Look-alike domains", "S6": "Sender familiarity", "S7": "Thread consistency",
    "S9": "Link text vs. destination", "S10": "Link construction", "S11": "Attachments",
    "S12": "Hidden content", "S13": "Request wording", "S14": "Pressure language",
}
_NOT_APPLICABLE = {"S3": "no sender name", "S9": "no links in this email", "S10": "no links in this email",
                   "S11": "no attachments"}
_UNAVAILABLE = {"S1": "no authentication results, which is common for forwarded mail",
                "S4": "relationship checks are off", "S6": "relationship checks are off",
                "S5": "compared with known brands only; relationship checks are off"}


def check_note(check_id: str, state: str) -> str:
    if state == "not_applicable":
        return _NOT_APPLICABLE.get(check_id, "")
    if state == "unavailable":
        return _UNAVAILABLE.get(check_id, "")
    return ""


# Guard notes are produced from fixed templates (signals/*.py); map each to plain language.
_SAFEGUARDS = [
    ("S3 ignored 'via'", "A sending-platform name (\"via …\") was not treated as impersonation."),
    ("S12 ignored short hidden preheader", "A short hidden preview line, common in newsletters, was ignored."),
    ("S14 pressure cues ignored", "Urgency wording was ignored because this is bulk mail."),
    ("S9 downgraded", "Link mismatches count less in bulk mail."),
    ("S9 skipped", "Links to the sender's own signing domain or a known email provider were trusted."),
    ("S2 mid-thread change capped", "A reply-address change counts less in bulk mail."),
    ("S2 corporate-to-freemail", "A personal reply address counts less in bulk mail."),
    ("S2 different-domain", "A different reply domain was treated as weak evidence, since help desks often use one."),
    ("S4 skipped", "Known-contact matching needs a full name, so a single name was not compared."),
    ("S5 compared against the brand list only", "Look-alike domains were compared with known brands only."),
    ("S1 SPF failure ignored", "An SPF failure was ignored because the message passed DKIM and DMARC, as forwarded mail often does."),
    ("S10 shortener ignored", "Shortened links were not flagged in bulk mail."),
    ("S13 ignored a described", "Wording that describes, quotes or rules out a request (for example in a warning) "
                                "was not treated as a request to you."),
    ("S11 HTML attachment kept", "A web-page attachment from a known, authenticated sender was treated as weak evidence."),
]


def safeguards(notes: list[str]) -> list[str]:
    out = []
    for n in notes:
        text = next((t for prefix, t in _SAFEGUARDS if n.startswith(prefix)), None)
        if text and text not in out:
            out.append(text)
    return out


LIMITATIONS_SUMMARY = ("MailLens analyzes the opened email and, when you allow it, your sent-mail history "
                       "to recognize people you know.")
LIMITATIONS = [
    "Relationship checks need read access to your mailbox. MailLens uses it to read the recipients of mail "
    "you've sent and the headers of earlier messages in the open thread.",
    "No threat-intelligence or website reputation lookups are made.",
    "Attachments are not opened; only their names and types are checked.",
    "Text inside images is not read.",
    "Request detection works in English only.",
    "A known contact means someone you emailed in the last 180 days.",
    "A well-made attack from a new sender with valid authentication can look clean.",
]


def _m(pattern: str, text: str) -> str:
    import re
    m = re.search(pattern, text)
    return m.group(1) if m else ""


def evidence_details(f: Finding, ctx) -> list[tuple[str, str]]:
    """Label/value pairs for one finding, from data the engine already holds (no detection changes)."""
    s, rt = ctx.sender, ctx.reply_to
    k = f.kind
    if k == "auth_failed":
        pairs = [("From domain", s.domain), ("Result", f.reality.removeprefix("Authentication failed: "))]
    elif k.startswith("reply_"):
        pairs = [("From", s.address), ("Reply-To", rt.address if rt else "")]
        if k == "reply_mid_thread":
            pairs.append(("Earlier messages from this From address", "no Reply-To or a different one"))
    elif k == "display_embedded_address":
        pairs = [("Display name", f.excerpt), ("From address", s.address)]
    elif k == "display_brand_mismatch":
        pairs = [("Display name", s.display), ("From domain", s.reg)]
    elif k == "display_role_only":
        pairs = [("Display name", s.display), ("From address", s.address)]
    elif k == "known_name_new_address":
        known = sorted((ctx.req.relationship.name_match_addresses if ctx.req.relationship else []))[:2]
        pairs = [("Display name", s.display), ("Known address for this name", ", ".join(known)),
                 ("From address (this email)", s.address)]
    elif k.startswith("lookalike_"):
        pairs = [("Resembles", _m(r"^Looks like (\S+)", f.claim)), ("From domain", s.reg)]
    elif k == "thread_fake_reply":
        pairs = [("Subject", f.excerpt)]
    elif k == "thread_new_sender":
        pairs = [("From address", s.address)]
    elif k == "thread_signer_changed":
        pairs = [("Signature", f.reality)]
    elif k == "link_text_mismatch":
        pairs = [("Link text shows", _m(r"^Link text shows (\S+)", f.claim)),
                 ("Link opens", _m(r"actually opens (\S+)", f.reality))]
    elif k.startswith("link_"):
        pairs = [("Link", f.excerpt)]
    elif k.startswith("attach_"):
        pairs = [("File", f.excerpt)]
    elif k == "obfuscated_text":
        pairs = [("Example (escaped)", f.excerpt)]
    elif k.startswith("hidden_"):
        pairs = [("Hidden text", defang_text(f.excerpt))]
    else:
        pairs = []
    return [(label, value[:160]) for label, value in pairs if value]
