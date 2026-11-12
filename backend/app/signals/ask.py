"""Request and pressure signals: S13 high-impact request (A), S14 pressure/secrecy (P).

Patterns are a data-driven pack. Every pattern ships with examples that MUST match
and examples that MUST NOT match; the test suite runs them all (tests/test_patterns.py).
Inputs are length-capped and patterns use bounded quantifiers (no catastrophic backtracking).
"""

import re
from dataclasses import dataclass

from ..htmltext import FORWARD_MARKER, strip_quotes_and_signature
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
    P("bank_change", 3, "Change payment or bank details",
      rf"\b(?:bank(?:ing)?|payment|remittance|wire)\s+(?:account\s+)?(?:details|information|info|instructions)\b{W}"
      rf"\b(?:changed|updated|new|change|update)\b|\b(?:new|updated|different)\s+(?:bank\s+)?(?:account|iban|beneficiary|"
      rf"bank details|remittance details)\b{W}\b(?:pay|payment|payments|wire|transfer|send|use|remit)\b|"
      rf"\b(?:pay|payment|payments|wire|transfer|send|remit)\b{W}\b(?:new|updated|different)\s+(?:bank\s+)?(?:account|iban|beneficiary)\b|"
      r"\b(?:updated|new|revised|changed)\s+(?:remittance|payment|banking|bank|wire)\s+(?:instructions|details)\b|"
      r"\b(?:update|change|amend)\s+(?:the\s+|our\s+)?(?:beneficiary|payee|bank(?:ing)?\s+details|remittance\s+details|wire\s+instructions)\b",
      ["our bank details have changed, kindly wire the payment to our new account",
       "please send payments to our new bank account",
       "Updated remittance details: use our new IBAN",
       "please use the updated remittance instructions attached for future invoices",
       "please update the beneficiary on file before paying the invoice"],
      ["your account details were updated successfully", "we sent the payment to your account on file",
       "please update your account details in the profile page"]),
    P("gift_cards", 3, "Buy gift cards",
      rf"\b(?:buy|purchase|get|pick up|send|need|require|get me)\b{W}\bgift\s?cards?\b|\bgift\s?cards?\b{W}\b(?:scratch|codes?|photos?)\b",
      ["can you buy 5 Apple gift cards for me", "send me the gift card codes",
       "I need 6 Google Play gift cards for a client today"],
      ["thanks for the gift card you sent last year!", "Our gift card program launches in May"]),
    P("payroll", 3, "Change payroll or direct-deposit details",
      rf"\b(?:change|update|switch|redirect)\b{W}\b(?:direct deposit|payroll|salary)\b",
      ["I need to update my direct deposit before the next payroll"],
      ["payroll will run on Friday as usual"]),
    P("code_relay", 3, "Share a verification code",
      rf"\b(?:send|share|tell|give|forward|read|text)\b(?:\s+me|\s+us)?{W}\b(?:the\s+)?(?:code|otp|one[- ]time (?:code|password)|"
      rf"verification code|security code|2fa code)\b|\breply with\b{W}\bcode\b",
      ["please send me the code you just received", "reply with the 6-digit code"]),
    # (Code-delivery messages are excluded by a context guard in s13_s14, tested in test_signals.)
    P("remote_access", 3, "Install a remote-access tool",
      rf"\b(?:install|download|run|open)\b{W}\b(?:anydesk|teamviewer|screenconnect|connectwise|ultraviewer|"
      rf"supremo|rustdesk|logmein|quick ?assist|remote (?:access|support|desktop) (?:tool|app|software))\b",
      ["please install AnyDesk so I can fix your laptop"],
      ["we no longer support TeamViewer licenses"]),
    # ---- A = 2: elevated
    P("credentials", 2, "Sign in through a link",
      rf"\b(?:sign|log)\s?in\b{W}\b(?:verify|confirm|password|keep|restore|avoid|review)\b|"
      rf"\bverify\s+your\s+(?:account|password|identity|login|mailbox)\b|\benter your (?:password|credentials)\b|"
      rf"\b(?:email|account)\s+password\b|"
      r"\b(?:sign|log)\s?in\s+with\s+your\s+(?:email|work|office|microsoft|google|company)?\s*(?:account|password|credentials)\b",
      ["Please sign in to verify your account", "Log in with your email password to keep receiving mail",
       "If not, sign in and review your account activity",
       "You will need to sign in with your email account to view it"],
      ["You signed in from a new device."]),
    P("card_update", 2, "Update payment card details",
      rf"\bupdate\b{W}\b(?:credit card|card details|payment method|billing information)\b",
      ["Please update your credit card to avoid interruption"], ["Your card ending 4242 was charged"]),
    P("enable_content", 2, "Enable content in an attachment",
      r"\benable\s+(?:content|editing|macros)\b", ["Click Enable Content to view the invoice"]),
    P("channel_move", 2, "Continue the conversation off email",
      rf"\b(?:text|message|contact|reach|add)\b(?:\s+me)?{W}\b(?:whatsapp|telegram|signal app|my (?:personal|private) "
      rf"(?:email|number|cell)|my cell)\b",
      ["text me on WhatsApp, I'm in a meeting", "contact me on my personal email"],
      ["our WhatsApp channel is now live"]),
    P("favor_probe", 2, "Do an unexplained favor",
      r"\bare you (?:at your desk|available|around|free)\b|\b(?:quick|small|urgent) favou?r\b|\bdo me a favou?r\b",
      ["Are you at your desk? I need a quick favor", "can you do me a favor"],
      ["thanks for the favor yesterday"]),
    # ---- A = 1: generic call to action
    P("generic_cta", 1, "Follow a generic call to action",
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


# Explicit concealment from others (narrower than SECRECY: excludes a bare "confidential").
CONCEALMENT = re.compile(r"\b(?:keep (?:this|it) (?:between us|quiet)|don'?t (?:tell|mention|share this with)|"
                         r"be discreet|don'?t discuss)\b", re.IGNORECASE)
PRETEXT_IDS = {"favor_probe", "channel_move"}


@dataclass
class AskResult:
    level: int = 0
    pattern: Pattern | None = None
    excerpt: str = ""
    source: str = ""          # "Subject" or "Body": where the quoted text came from
    pretext_secrecy: bool = False  # F-19: pretext request + explicit concealment
    pressure: bool = False
    cues: list[str] | None = None
    note: str = ""


# Invisible characters inside words, and Cyrillic/Greek letters that look Latin, are used to split
# keywords so pattern matching fails. Matching runs on a normalized copy (RC2, Phase 3b).
_INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
_LOOKALIKE_LETTERS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Т": "T", "Н": "H", "К": "K", "М": "M", "В": "B",
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "τ": "t", "ι": "i", "κ": "k",
})


_SPACED = re.compile(r"\b(?:[A-Za-z] ){2,}[A-Za-z]\b")


def normalize_for_matching(text: str) -> str:
    text = _INVISIBLE.sub("", text).translate(_LOOKALIKE_LETTERS)
    return _SPACED.sub(lambda m: m.group(0).replace(" ", ""), text)


def _scan_text(ctx: Context) -> str:
    text = ctx.body.visible_text or ctx.req.message.text_body
    if ctx.trusted_forward and (fm := FORWARD_MARKER.search(text)):
        text = text[: fm.start()]  # only the forwarder's own words are requests to the reader (F-18)
    text = strip_quotes_and_signature(text[:MAX_SCAN])
    return normalize_for_matching(f"{ctx.req.message.subject}\n{text}")


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
            if is_reported_not_requested(text, m.start(), m.end()):
                out.note = "S13 ignored a described, quoted or negated request"
                continue
            out.level, out.pattern = p.level, p
            subj_len = len(ctx.req.message.subject)
            if m.start() < subj_len:  # quote the body instead when it contains the same request
                m = next((b for b in p.regex.finditer(text, subj_len + 1)), m)
            out.source, out.excerpt = quote(text, m.start(), m.end(), subj_len)
            break

    if out.level < 3:
        _two_sentence_bank_change(text, out)
    if ctx.is_bulk:
        out.note = "S14 pressure cues ignored: bulk mail"
        return out
    secrecy = bool(SECRECY.search(text))
    out.pretext_secrecy = bool(out.pattern and out.pattern.id in PRETEXT_IDS and CONCEALMENT.search(text))
    out.cues = [name for name, rx in URGENCY_CUES.items() if re.search(rx, text, re.IGNORECASE)]
    if secrecy:
        out.cues.insert(0, "secrecy")
    out.pressure = secrecy or len(out.cues) >= 2
    return out


# ---------------------------------------------------------------- two-sentence bank change (Phase 5b)
_ACCOUNT_CHANGED = re.compile(r"\b(?:bank|banking|account|iban|beneficiary)\b[^.!?\n]{0,60}\b(?:closed|changed|frozen|moved|"
                              r"switched|no longer)\b|\b(?:new|different)\s+(?:bank|account|iban)\b", re.IGNORECASE)
_PAY_INSTRUCTION = re.compile(r"\b(?:send|pay|wire|remit|transfer)\b[^.!?\n]{0,60}\b(?:new|this|it|them|below|following|"
                              r"instead)\b", re.IGNORECASE)


def _two_sentence_bank_change(text: str, out) -> None:
    """A bank change announced in one sentence and the payment instruction in the next."""
    sents = [(m.start(), m.end()) for m in re.finditer(r"[^.!?\n]+[.!?]?", text)]
    for (a1, b1), (a2, b2) in zip(sents, sents[1:]):
        if _ACCOUNT_CHANGED.search(text, a1, b1) and (m := _PAY_INSTRUCTION.search(text, a2, b2)):
            if is_reported_not_requested(text, m.start(), m.end()) or _THREAT_ACTOR.search(text, a1, b1):
                continue  # described scam ("Scammers say ... They then ask you to ...")
            pat = next(p for p in REQUEST_PATTERNS if p.id == "bank_change")
            out.level, out.pattern = 3, pat
            out.source, out.excerpt = quote(text, a1, b2, text.find("\n") if "\n" in text else 0)
            return


# ---------------------------------------------------------------- reported-speech guard (RC5, F-16)
_THREAT_ACTOR = re.compile(r"\b(?:scammers?|fraudsters?|attackers?|criminals?|cyber ?criminals?|phishers?|hackers?|"
                           r"impostors?|imposters?|con artists?)\b", re.IGNORECASE)
_EXAMPLE_CUE = re.compile(r"\b(?:scam|phishing|fraud|example|says|typical|such as|warning|fake)\b", re.IGNORECASE)
_NEGATED_ASK = re.compile(r"\b(?:never|not|n't)\s+(?:\w+\s+){0,2}(?:ask|request|email|contact)\w*\s+(?:\w+\s+){0,2}$",
                          re.IGNORECASE)
_DIRECT_ADDRESS = re.compile(r"\b(?:please|kindly|you must|you need to|can you|could you|I need you to|go ahead and)\b",
                             re.IGNORECASE)
_QUOTED = re.compile(r"\"[^\"]{1,400}\"|“[^”]{1,400}”")


def _sentence(text: str, start: int, end: int) -> tuple[int, int]:
    left = max((m.end() for m in _SENTENCE_END.finditer(text, 0, start)), default=0)
    right_m = _SENTENCE_END.search(text, end)
    return left, right_m.end() if right_m else len(text)


def is_reported_not_requested(text: str, start: int, end: int) -> bool:
    """True when a request match is described, quoted as an example, or negated, not asked of the reader.

    Never true if the same sentence also addresses the reader directly outside quotation marks, so an
    attacker can't hide a real instruction behind "scammers..." or quotes (tests: test_reported_speech_*).
    """
    a, b = _sentence(text, start, end)
    sentence, ms, me = text[a:b], start - a, end - a
    quotes = [(q.start(), q.end()) for q in _QUOTED.finditer(sentence)]
    outside = "".join(ch for i, ch in enumerate(sentence) if not any(qs <= i < qe for qs, qe in quotes))
    if _DIRECT_ADDRESS.search(outside):
        return False
    in_quote = any(qs <= ms and me <= qe for qs, qe in quotes)
    if in_quote and _EXAMPLE_CUE.search(sentence):
        return True
    if _THREAT_ACTOR.search(sentence[:ms]):
        return True
    return bool(_NEGATED_ASK.search(sentence[:ms]))


# ---------------------------------------------------------------- quotes (presentation only)
QUOTE_MAX = 220
_SENTENCE_END = re.compile(r"[.!?](?=\s)|\n")
_URL = re.compile(r"\b(?:https?|ftp)://[^\s<>\"']+", re.IGNORECASE)
_HOST = re.compile(r"\b(?:[a-z0-9-]{1,63}\.)+[a-z]{2,24}\b", re.IGNORECASE)


def defang_text(text: str) -> str:
    """Neutralizes URLs and host names inside quoted email text so nothing can render as a link."""
    def url(m: re.Match) -> str:
        u = m.group(0).rstrip(".,;:!?)")
        return u.replace("http", "hxxp", 1).replace("ftp", "fxp", 1).replace(".", "[.]") + m.group(0)[len(u):]
    text = _URL.sub(url, text)
    return _HOST.sub(lambda m: m.group(0).replace(".", "[.]"), text)


def quote(text: str, start: int, end: int, subject_len: int) -> tuple[str, str]:
    """Quotes the whole sentence(s) around a match, from the Subject OR the Body, never both.

    `text` is "subject\nbody" as scanned by detection; detection itself is unchanged.
    Long quotes are cut at a word boundary with an ellipsis instead of mid-word.
    """
    if start < subject_len:
        source, seg_start, seg_end = "Subject", 0, subject_len
    else:
        source, seg_start, seg_end = "Body", subject_len + 1, len(text)
    seg = text[seg_start:seg_end]
    a, b = start - seg_start, end - seg_start
    left = max((m.end() for m in _SENTENCE_END.finditer(seg, 0, a)), default=0)
    right_m = _SENTENCE_END.search(seg, b)
    right = right_m.end() if right_m else len(seg)
    nxt = _SENTENCE_END.search(seg, right)
    if nxt and len(" ".join(seg[left:nxt.end()].split())) <= QUOTE_MAX:
        right = nxt.end()
    q = " ".join(seg[left:right].split())
    if len(q) > QUOTE_MAX:
        cut = q[:QUOTE_MAX].rsplit(" ", 1)[0]
        q = cut.rstrip(",;:") + " …"
    if left > 0:
        q = "… " + q
    return source, defang_text(q)
