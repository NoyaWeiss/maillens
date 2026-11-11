"""Test helper: turns raw RFC 822 demo messages into AnalyzeRequests.

Mirrors what the add-on does (addon/Extract.js, addon/Relationship.js) so the
engine can be tested against the exact emails seeded into the demo mailbox.
"""

import importlib.util
import sys
from email import message_from_string, policy
from email.utils import getaddresses, parseaddr
from pathlib import Path

from app.domains import registrable
from app.schemas import AnalyzeRequest

OWNER = "demo.owner@example.com"
_spec = importlib.util.spec_from_file_location("build_seed", Path(__file__).resolve().parents[2] / "demo" / "build_seed.py")
build_seed = importlib.util.module_from_spec(_spec)
sys.modules["build_seed"] = build_seed
_spec.loader.exec_module(build_seed)


def demo_messages() -> dict[str, dict]:
    return {m["key"]: {**m, "raw": m["raw"].replace("{{OWNER}}", OWNER)} for m in build_seed.MESSAGES}


def _parts(msg):
    html = text = ""
    atts = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        fn = part.get_filename()
        if fn:
            atts.append({"name": fn, "content_type": part.get_content_type(),
                         "size": len(part.get_payload(decode=True) or b"")})
        elif part.get_content_type() == "text/html" and not html:
            html = part.get_content()
        elif part.get_content_type() == "text/plain" and not text:
            text = part.get_content()
    return html, text, atts


def relationship_from(sent_raws: list[str], from_header: str) -> dict:
    """Same rules as the add-on: contacts = recipients of the owner's sent mail."""
    by_name: dict[str, set[str]] = {}
    addrs: dict[str, int] = {}
    for raw in sent_raws:
        msg = message_from_string(raw, policy=policy.default)
        for name, addr in getaddresses([str(msg.get("To", ""))]):
            addr = addr.lower()
            addrs[addr] = addrs.get(addr, 0) + 1
            key = " ".join(name.casefold().split())
            if len(key.split()) >= 2:
                by_name.setdefault(key, set()).add(addr)
    name, addr = parseaddr(from_header)
    key = " ".join(name.casefold().split())
    return {
        "known_domains": sorted({registrable(a.rsplit("@", 1)[1]) for a in addrs if "@" in a})[:100],
        "sender_sent_count": addrs.get(addr.lower(), 0),
        "name_match_addresses": sorted(by_name.get(key, set()))[:10],
    }


def request_for(raw: str, *, thread_raws=(), sent_raws=None, relationship=True) -> AnalyzeRequest:
    msg = message_from_string(raw, policy=policy.default)
    html, text, atts = _parts(msg)
    get = lambda h: str(msg[h]) if msg[h] is not None else None
    thread = []
    for t in thread_raws:
        tm = message_from_string(t, policy=policy.default)
        ar = tm.get_all("Authentication-Results") or []
        thread.append({"from_header": str(tm["From"]), "reply_to": str(tm["Reply-To"]) if tm["Reply-To"] else None,
                       "auth_result": str(ar[0]) if ar else None,
                       "participants": [a for _, a in getaddresses([str(tm.get("To", "")), str(tm.get("Cc", ""))])][:30]})
    payload = {
        "message": {
            "from_header": get("From") or "", "reply_to": get("Reply-To"), "subject": get("Subject") or "",
            "in_reply_to": get("In-Reply-To"), "references": get("References"),
            "auth_results": [str(h) for h in (msg.get_all("Authentication-Results") or [])],
            "list_unsubscribe": msg["List-Unsubscribe"] is not None, "precedence": get("Precedence"),
            "html_body": html, "text_body": text, "attachments": atts,
        },
        "thread": thread[-5:],
        "thread_message_count": len(thread) + 1,
        "relationship": relationship_from(sent_raws or [], get("From") or "") if relationship else None,
    }
    return AnalyzeRequest.model_validate(payload)
