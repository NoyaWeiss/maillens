"""Request and pressure signals: S13 high-impact request (A), S14 pressure/secrecy (P).

Patterns are a data-driven pack. Every pattern ships with examples that MUST match
and examples that MUST NOT match; the test suite runs them all (tests/test_patterns.py).
Inputs are length-capped and patterns use bounded quantifiers (no catastrophic backtracking).
"""

import re
from dataclasses import dataclass

from ..htmltext import strip_quotes_and_signature
from ..model import Context

MAX_SCAN = 20_000


@dataclass(frozen=True)
class Pattern:
    id: str
    level: int
    label: str
    regex: re.Pattern
    should_match: tuple[str, ...]
    should_not_match: tuple[str, ...] = ()


def P(id, level, label, rx, yes, no=()):
    return Pattern(id, level, label, re.compile(rx, re.IGNORECASE), tuple(yes), tuple(no))


W = r"[^.!?\n]{0,60}?"  # bounded "same sentence" window between verb and object

REQUEST_PATTERNS = [
    # ---- A = 3: irreversible or high-impact
    P("bank_change", 3, "Change of payment or bank details",
      rf"\b(?:bank(?:ing)?|payment|remittance|wire)\s+(?:account\s+)?(?:details|information|info|instructions)\b{W}"
      rf"\b(?:changed|updated|new|change|update)\b|\b(?:new|updated|different)\s+(?:bank\s+)?(?:account|iban|beneficiary|"
      rf"bank details|remittance details)\b{W}\b(?:pay|payment|payments|wire|transfer|send|use|remit)\b|"
      rf"\b(?:pay|payment|payments|wire|transfer|send|remit)\b{W}\b(?:new|updated|different)\s+(?:bank\s+)?(?:account|iban|beneficiary)\b",
      ["our bank details have changed, kindly wire the payment to our new account",
       "please send payments to our new bank account",
       "Updated remittance details: use our new IBAN"],
      ["your account details were updated successfully", "we sent the payment to your account on file"]),
    P("gift_cards", 3, "Purchase of gift cards",
      rf"\b(?:buy|purchase|get|pick up|send)\b{W}\bgift\s?cards?\b|\bgift\s?cards?\b{W}\b(?:scratch|codes?|photos?)\b",
      ["can you buy 5 Apple gift cards for me", "send me the gift card codes"],
      ["thanks for the gift card you sent last year!"]),
    P("payroll", 3, "Payroll / direct-deposit redirection",
      rf"\b(?:change|update|switch|redirect)\b{W}\b(?:direct deposit|payroll|salary)\b",
      ["I need to update my direct deposit before the next payroll"],
      ["payroll will run on Friday as usual"]),
    P("code_relay", 3, "Relay of a verification / MFA code",
      rf"\b(?:send|share|tell|give|forward|read|text)\b(?:\s+me|\s+us)?{W}\b(?:the\s+)?(?:code|otp|one[- ]time (?:code|password)|"
      rf"verification code|security code|2fa code)\b|\breply with\b{W}\bcode\b",
      ["please send me the code you just received", "reply with the 6-digit code"]),
    # (Code-delivery messages are excluded by a context guard in s13_s14, tested in test_signals.)
    P("remote_access", 3, "Installation of a remote-access tool",
      rf"\b(?:install|download|run|open)\b{W}\b(?:anydesk|teamviewer|screenconnect|connectwise|ultraviewer|"
      rf"supremo|rustdesk|logmein|quick ?assist|remote (?:access|support|desktop) (?:tool|app|software))\b",
      ["please install AnyDesk so I can fix your laptop"],
      ["we no longer support TeamViewer licenses"]),
    # ---- A = 2: elevated
    P("credentials", 2, "Sign in / enter credentials via a link",
      rf"\b(?:sign|log)\s?in\b{W}\b(?:verify|confirm|password|keep|restore|avoid|review)\b|"
      rf"\bverify\s+your\s+(?:account|password|identity|login|mailbox)\b|\benter your (?:password|credentials)\b|"
      rf"\b(?:email|account)\s+password\b",
      ["Please sign in to verify your account", "Log in with your email password to keep receiving mail",
       "If not, sign in and review your account activity"],
      ["You signed in from a new device."]),
    P("card_update", 2, "Update payment card",
      rf"\bupdate\b{W}\b(?:credit card|card details|payment method|billing information)\b",
      ["Please update your credit card to avoid interruption"], ["Your card ending 4242 was charged"]),
    P("enable_content", 2, "Open an attachment and enable content",
      r"\benable\s+(?:content|editing|macros)\b", ["Click Enable Content to view the invoice"]),
    P("channel_move", 2, "Move the conversation off email",
      rf"\b(?:text|message|contact|reach|add)\b(?:\s+me)?{W}\b(?:whatsapp|telegram|signal app|my (?:personal|private) "
      rf"(?:email|number|cell)|my cell)\b",
      ["text me on WhatsApp, I'm in a meeting", "contact me on my personal email"],
      ["our WhatsApp channel is now live"]),
    P("favor_probe", 2, "Undisclosed favor or availability probe",
      r"\bare you (?:at your desk|available|around|free)\b|\b(?:quick|small|urgent) favou?r\b|\bdo me a favou?r\b",
      ["Are you at your desk? I need a quick favor", "can you do me a favor"],
      ["thanks for the favor yesterday"]),
    # ---- A = 1: generic call to action
    P("generic_cta", 1, "Generic call to action",
      r"\b(?:click here|pay (?:the )?invoice|confirm your (?:email|subscription)|view (?:the )?(?:invoice|document))\b",
      ["Pay invoice", "click here to view"]),
]

SECRECY = re.compile(
    r"\b(?:keep (?:this|it) (?:between us|confidential|quiet)|don'?t (?:tell|mention|share this with)|"
    r"strictly confidential|be discreet|don'?t discuss)\b", re.IGNORECASE)
URGENCY_CUES = {
    "urgent": r"\burgent(?:ly)?\b|\basap\b",
    "immediately": r"\bimmediately\b|\bright away\b",
    "deadline": r"\bwithin \d{1,2} hours\b|\bby (?:end of day|eod|today)\b|\btoday\b",
    "threat": r"\b(?:suspen(?:d|ded|sion)|terminat(?:e|ed|ion)|locked|legal action|penalt(?:y|ies))\b",
    "authority": r"\b(?:ceo|cfo|director|managing partner|president)\b",
    "final": r"\bfinal (?:notice|warning|reminder)\b",
}


@dataclass
class AskResult:
    level: int = 0
    pattern: Pattern | None = None
    excerpt: str = ""
    pressure: bool = False
    cues: list[str] | None = None
    note: str = ""


def _scan_text(ctx: Context) -> str:
    text = ctx.body.visible_text or ctx.req.message.text_body
    text = strip_quotes_and_signature(text[:MAX_SCAN])
    return f"{ctx.req.message.subject}\n{text}"


def s13_s14(ctx: Context) -> AskResult:
    text = _scan_text(ctx)
    out = AskResult(cues=[])
    for p in REQUEST_PATTERNS:  # ordered by level, highest first
        if p.level <= out.level:
            continue
        for m in p.regex.finditer(text):
            window = text[max(0, m.start() - 80): m.end() + 80]
            if p.id == "code_relay" and re.search(r"never share|do not share|don'?t share|your (?:\w+ )?code is",
                                                  window, re.IGNORECASE):
                continue  # guard: messages that deliver a code are not requests for one
            out.level, out.pattern = p.level, p
            out.excerpt = " ".join(text[max(0, m.start() - 40): m.end() + 40].split())
            break

    if ctx.is_bulk:
        out.note = "S14 pressure cues ignored: bulk mail"
        return out
    secrecy = bool(SECRECY.search(text))
    out.cues = [name for name, rx in URGENCY_CUES.items() if re.search(rx, text, re.IGNORECASE)]
    if secrecy:
        out.cues.insert(0, "secrecy")
    out.pressure = secrecy or len(out.cues) >= 2
    return out
