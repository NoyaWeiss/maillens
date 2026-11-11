"""Payload signals: S11 risky attachment (metadata only), S12 obfuscation / scanner targeting."""

import re

from ..model import Context, Finding, SignalResult
from ..schemas import Basis, CheckState, Group
from .dest import zero_width_in_links

EXECUTABLE = {"exe", "scr", "com", "bat", "cmd", "msi", "ps1", "vbs", "vbe", "js", "jse", "wsf", "hta", "jar",
              "lnk", "iso", "img", "vhd", "vhdx", "dmg", "pif", "cpl", "reg", "app", "apk", "msix", "appx"}
HTML_LIKE = {"html", "htm", "shtml", "xhtml", "svg", "mht", "mhtml"}
MACRO_OFFICE = {"docm", "xlsm", "pptm", "dotm", "xltm", "xlam", "ppsm"}
ARCHIVE = {"zip", "rar", "7z"}
# Second-to-last extensions that make a double extension deceptive (invoice.pdf.exe).
DECOY = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "txt", "csv", "ppt", "pptx", "zip"}


def _exts(name: str) -> list[str]:
    parts = name.lower().strip().rstrip(".").split(".")
    return parts[1:] if len(parts) > 1 else []


def s11_attachments(ctx: Context) -> SignalResult:
    r = SignalResult()
    atts = ctx.req.message.attachments
    if not atts:
        r.state = CheckState.NOT_APPLICABLE
        return r
    body = ctx.body.visible_text.lower()
    for a in atts:
        exts = _exts(a.name)
        if not exts:
            continue
        last, ent = exts[-1], f"file:{a.name.lower()[:120]}"
        if last in EXECUTABLE and len(exts) >= 2 and exts[-2] in DECOY:
            r.findings.append(Finding.of("attach_double_ext", "S11", Group.PAYLOAD, ent, 3, Basis.OBSERVED,
                                      claim=f"Looks like a .{exts[-2]} document", excerpt=a.name,
                                      reality=f"It is really a .{last} program disguised with a double extension"))
        elif last in EXECUTABLE:
            r.findings.append(Finding.of("attach_executable", "S11", Group.PAYLOAD, ent, 2, Basis.OBSERVED, claim="An attachment",
                                      reality=f"A .{last} file can run code on your computer", excerpt=a.name))
        elif last in HTML_LIKE:
            risky = ctx.familiarity == "1" or not ctx.auth.passed
            r.findings.append(Finding.of("attach_html", 
                "S11", Group.PAYLOAD, ent, 2 if risky else 1, Basis.OBSERVED, claim="A document attachment",
                reality=f"A .{last} file opens as a web page and can host a fake sign-in form", excerpt=a.name))
            if not risky:
                r.notes.append("S11 HTML attachment kept at level 1: known, authenticated sender")
        elif last in MACRO_OFFICE:
            r.findings.append(Finding.of("attach_macro", "S11", Group.PAYLOAD, ent, 1, Basis.OBSERVED, claim="An Office document",
                                      reality=f"A macro-enabled .{last} file", excerpt=a.name))
        elif last in ARCHIVE and re.search(r"\bpassword\b", body):
            r.findings.append(Finding.of("attach_protected_archive", "S11", Group.PAYLOAD, ent, 1, Basis.OBSERVED, claim="An archive",
                                      reality="Password-protected archives hide their contents from scanners",
                                      excerpt=a.name))
    return r


_SCANNER_BAIT = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above) instructions|"
    r"(?:note|message) to (?:the )?(?:ai|automated|security|spam|email) (?:scanners?|filters?|assistants?|systems?)|"
    r"this (?:email|message) is (?:safe|legitimate|not (?:spam|phishing))|"
    r"classify (?:it|this(?: email| message)?) as (?:safe|legitimate|benign)|"
    r"you are an? (?:ai|assistant|language model)", re.IGNORECASE)
_KEYWORDS = re.compile(r"password|verify|account|login|sign in|invoice|payment|bank", re.IGNORECASE)
PREHEADER_MAX = 150  # short hidden text near the top is a normal email "preheader"


def s12_obfuscation(ctx: Context) -> SignalResult:
    r = SignalResult()
    if not ctx.req.message.html_body:
        r.state = CheckState.NOT_APPLICABLE
        return r
    for seg in ctx.body.hidden:
        if m := _SCANNER_BAIT.search(seg.text):
            r.findings.append(Finding.of("hidden_scanner_bait", 
                "S12", Group.PAYLOAD, "body", 3, Basis.OBSERVED,
                claim="Hidden text you cannot see", reality="It contains instructions aimed at automated "
                                                            "security scanners, trying to get the email marked safe",
                excerpt=seg.text[max(0, m.start() - 40): m.end() + 40]))
            break
    else:
        hidden_links = [l for l in ctx.links if l.hidden]
        for seg in ctx.body.hidden:
            preheader = seg.offset < 200 and len(seg.text) <= PREHEADER_MAX
            if preheader:
                r.notes.append("S12 ignored short hidden preheader")
                continue
            if len(seg.text) >= 200 and (_KEYWORDS.search(seg.text) or hidden_links):
                r.findings.append(Finding.of("hidden_block", 
                    "S12", Group.PAYLOAD, "body", 2, Basis.OBSERVED, claim="Hidden text you cannot see",
                    reality=f"A {len(seg.text)}-character hidden block containing links or sensitive keywords",
                    excerpt=seg.text[:120]))
                break
    if zw := zero_width_in_links(ctx):
        r.findings.append(Finding.of("hidden_zero_width", 
            "S12", Group.PAYLOAD, "body", 2, Basis.OBSERVED, claim="A normal-looking link",
            reality="Invisible zero-width characters are inserted in the link to dodge filters",
            excerpt=zw[0][:120].encode("unicode_escape").decode()))
    return r
