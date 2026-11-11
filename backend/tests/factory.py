"""Small builders for signal-level tests."""

from app.engine import analyze
from app.schemas import AnalyzeRequest

PASS = lambda d, dkim=None: (f"mx.google.com; dkim=pass header.i=@{dkim or d} header.s=s1; spf=pass "
                             f"smtp.mailfrom={d}; dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from={d}")


def req(from_header="Acme <billing@acme.example>", *, html="<p>Hello</p>", auth="pass", reply_to=None,
        subject="Hello", attachments=(), bulk=False, thread=(), relationship=None, **msg):
    dom = from_header.rsplit("@", 1)[-1].rstrip(">")
    ar = [PASS(dom)] if auth == "pass" else ([auth] if auth else [])
    m = {"from_header": from_header, "reply_to": reply_to, "subject": subject, "html_body": html,
         "auth_results": ar, "list_unsubscribe": bulk, "attachments": list(attachments), **msg}
    return AnalyzeRequest.model_validate({"message": m, "thread": list(thread), "relationship": relationship})


def run(*a, **k):
    return analyze(req(*a, **k), "t")[0]


def sig(resp, signal):
    """Highest level for a signal across kept and also-observed findings (0 if absent)."""
    return max((f.level for f in resp.findings + resp.also_observed if f.signal == signal), default=0)


REL = {"known_domains": ["acme.example", "northwind.example"], "sender_sent_count": 0, "name_match_addresses": []}
