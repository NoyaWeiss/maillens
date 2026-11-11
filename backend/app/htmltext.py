"""Bounded, dependency-free HTML analysis of attacker-controlled email bodies.

Produces visible text, hidden text segments (with their position), and links
(href + anchor text). Never executes or fetches anything. Input is capped before
parsing, and per-collection limits bound memory use.
"""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

MAX_HTML = 200_000
MAX_LINKS = 200
MAX_TEXT = 100_000
MAX_DEPTH = 256  # deeper nesting is not tracked structurally (bounds work per tag)

_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?![.\d]*[1-9])|"
    r"max-height\s*:\s*0(?![.\d]*[1-9])|opacity\s*:\s*0(?![.\d]*[1-9])|"
    r"color\s*:\s*(?:#fff(?:fff)?|white)\b[^;]*;?[^\"]*background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white)",
    re.IGNORECASE,
)
_VOID = {"br", "img", "hr", "meta", "link", "input", "area", "base", "col", "embed", "source", "wbr"}
_SKIP = {"script", "style", "head", "title"}
_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table", "blockquote"}


@dataclass
class Link:
    href: str
    text: str
    hidden: bool


@dataclass
class HiddenSegment:
    text: str
    offset: int  # characters of visible text that preceded it (0 = top of message)


@dataclass
class ParsedBody:
    visible_text: str = ""
    hidden: list[HiddenSegment] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []  # (tag, hidden)
        self.hidden_depth = 0  # number of hidden elements currently open: O(1) visibility check
        self.overflow = 0  # open tags beyond MAX_DEPTH
        self.skip_depth = 0
        self.visible: list[str] = []
        self.visible_len = 0
        self.hidden_buf: list[str] = []
        self.hidden_start = 0
        self.hidden: list[HiddenSegment] = []
        self.links: list[Link] = []
        self.anchor: dict | None = None

    @property
    def is_hidden(self) -> bool:
        return self.hidden_depth > 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip_depth += 1
            return
        a = {k: (v or "") for k, v in attrs}
        hidden = bool(_HIDDEN_STYLE.search(a.get("style", ""))) or "hidden" in a
        was_hidden = self.is_hidden
        if tag in _BLOCK:
            self._text(" \n")
        if tag not in _VOID:
            if len(self.stack) >= MAX_DEPTH:
                self.overflow += 1
            else:
                self.stack.append((tag, hidden))
                self.hidden_depth += hidden
        if not was_hidden and self.is_hidden:
            self.hidden_start = self.visible_len
        if tag == "a" and len(self.links) < MAX_LINKS:
            self.anchor = {"href": a.get("href", "")[:2048], "text": [], "hidden": self.is_hidden}

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag == "a" and self.anchor is not None:
            self.links.append(Link(self.anchor["href"], " ".join("".join(self.anchor["text"]).split())[:500],
                                   self.anchor["hidden"]))
            self.anchor = None
        was_hidden = self.is_hidden
        if self.overflow:
            self.overflow -= 1
        else:
            # Tolerate unbalanced HTML, but only look a bounded distance down the stack.
            for i in range(len(self.stack) - 1, max(-1, len(self.stack) - 33), -1):
                if self.stack[i][0] == tag:
                    self.hidden_depth -= sum(h for _, h in self.stack[i:])
                    del self.stack[i:]
                    break
        if was_hidden and not self.is_hidden:
            self._flush_hidden()
        if tag in _BLOCK:
            self._text(" \n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.anchor is not None:
            self.anchor["text"].append(data)
        self._text(data)

    def _text(self, data: str) -> None:
        if self.is_hidden:
            if sum(map(len, self.hidden_buf)) < MAX_TEXT:
                self.hidden_buf.append(data)
        elif self.visible_len < MAX_TEXT:
            self.visible.append(data)
            self.visible_len += len(data)

    def _flush_hidden(self) -> None:
        text = " ".join("".join(self.hidden_buf).split())
        if text:
            self.hidden.append(HiddenSegment(text[:5000], self.hidden_start))
        self.hidden_buf = []


def parse_html(html: str) -> ParsedBody:
    p = _Parser()
    try:
        p.feed(html[:MAX_HTML])
        p.close()
    except Exception:  # malformed markup: keep whatever was parsed so far
        pass
    if p.hidden_buf:
        p._flush_hidden()
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.visible))
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    return ParsedBody(visible_text=text[:MAX_TEXT], hidden=p.hidden[:50], links=p.links)


_URL_RE = re.compile(r"https?://[^\s<>\"')]{1,2048}", re.IGNORECASE)


def links_from_text(text: str) -> list[Link]:
    return [Link(u, u, False) for u in _URL_RE.findall(text[:MAX_TEXT])][:MAX_LINKS]


_QUOTE_MARKERS = re.compile(
    r"^(?:On .{0,200} wrote:|-{2,} ?Original Message ?-{2,}|From: .{0,200}\nSent: )", re.MULTILINE)
_SIG_MARKER = re.compile(r"^(?:-- ?$|Sent from my )", re.MULTILINE)


def strip_quotes_and_signature(text: str) -> str:
    """Drop quoted replies and signatures so old thread content can't drive request detection."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    text = "\n".join(lines)
    if m := _QUOTE_MARKERS.search(text):
        text = text[: m.start()]
    if m := _SIG_MARKER.search(text):
        text = text[: m.start()]
    return text
