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
from .signals.ask import AskResult

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
    return {"category": _CATEGORY.get(arch, _CATEGORY["deception"]),
            "summary": _SUMMARY.get(arch, _SUMMARY["deception"]),
            "reasons": reasons[:2], "impact": _IMPACT.get(arch, _IMPACT["deception"]),
            "actions": _ACTIONS.get(arch, _ACTIONS["deception"])[:2]}
