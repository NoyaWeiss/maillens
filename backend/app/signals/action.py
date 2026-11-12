"""Action-in-context layer (Phase 5d candidate). Suspicious only, never High.

Fires when ALL hold:
  1. the reader is asked to take a sensitive ACTION (credentials/MFA, payment, permission, financial or
     identity disclosure, out-of-band contact via a phone number in the email);
  2. the sender is VERIFIED unfamiliar (unknown familiarity never counts) and the mail is not bulk;
  3. at least one INDEPENDENT suspicious context: link to an unrelated domain, a call-back phone number,
     a risky attachment, pressure/threat wording, or a financial lure.
All existing guards apply to the action text (described, quoted, negated requests are ignored).
"""

import re

from ..model import Context
from .ask import URGENCY_CUES, SECRECY, is_reported_not_requested
from .dest import FILE_SHARE, offsite_links

W = r"[^.!?\n]{0,60}?"
ACTIONS = {
    "credentials": re.compile(rf"\b(?:sign|log)\s?in\b{W}\b(?:to|with)\b|\bre-?authenticate\b|\bverify\s+your\s+(?:identity|account|login)\b", re.I),
    "mfa": re.compile(rf"\b(?:approve|accept)\b{W}\b(?:prompt|request|notification)\b|\b(?:read|send|share|tell)\b{W}\bcode\b", re.I),
    "payment": re.compile(rf"\b(?:pay|wire|transfer|remit|donate|purchase|buy|deposit)\b{W}\b(?:invoice|balance|fee|amount|"
                          rf"payment|funds|check|donation|gift|cards?|link|portal|today|now|below)\b|\bsend\b{W}\b(?:the\s+)?(?:balance|rest)\b", re.I),
    "permission": re.compile(rf"\b(?:install|download|run|enable|grant|authori[sz]e|allow)\b{W}\b(?:app|tool|agent|software|installer|"
                             rf"access|macros?|content|update|extension|documents?|files?)\b", re.I),
    "disclosure": re.compile(rf"\b(?:submit|upload|confirm|provide|send|enter|update|verify|reply with|share)\b{W}\b(?:bank(?:ing)?\s+"
                             rf"(?:details|information|account)|account number|card (?:number|details)|passport|id (?:copy|card)|"
                             rf"tax id|date of birth|social security|ssn|identity)\b", re.I),
    "out_of_band": re.compile(r"\b(?:call|phone|text|ring)\b[^.!?\n]{0,40}?\+?\(?\d[\d\s().-]{7,}\d", re.I),
}
PHONE = re.compile(r"\+?\(?\d{1,3}\)?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
LURE = re.compile(r"\b(?:refund|prize|won|winner|reward|claim|eligible|overcharg\w*|bonus|congratulations|selected|"
                  r"unclaimed|compensation)\b", re.I)
THREAT = re.compile(r"\b(?:legal action|subpoena|lawsuit|court|penalt(?:y|ies)|arrest|suspend\w*|terminat\w*|"
                    r"final notice|within \d+ (?:hours|days))\b", re.I)


def action_in_context(ctx: Context, scan_text: str, risky_attachment: bool) -> tuple[bool, str, list[str]]:
    """Returns (fires, action_class, contexts). Never fires for familiar/unknown senders or bulk mail."""
    if ctx.familiarity != "1" or ctx.is_bulk:
        return False, "", []
    action = ""
    for name, rx in ACTIONS.items():
        for m in rx.finditer(scan_text):
            if not is_reported_not_requested(scan_text, m.start(), m.end()):
                action = name
                break
        if action:
            break
    if not action:
        return False, "", []
    contexts = []
    # Major brands' own domains (e.g. accounts.google.com for "Sign in with Google") aren't attacker
    # infrastructure; consent abuse on them is covered separately by S10.
    if any(reg not in FILE_SHARE for reg in offsite_links(ctx)):
        contexts.append("link to an unrelated domain")
    if PHONE.search(scan_text):
        contexts.append("call-back phone number")
    if risky_attachment:
        contexts.append("risky attachment")
    if THREAT.search(scan_text) or SECRECY.search(scan_text) or any(re.search(rx, scan_text, re.I) for rx in URGENCY_CUES.values()):
        contexts.append("pressure or threat")
    if LURE.search(scan_text):
        contexts.append("financial lure")
    if action == "out_of_band":  # the phone number is the action's own target, not independent context
        contexts = [c for c in contexts if c != "call-back phone number"]
    return bool(contexts), action, contexts
