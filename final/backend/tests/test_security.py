"""Hostile-input tests: size, nesting, Unicode, forged headers."""

import time

from tests.factory import run


def timed(**k):
    t = time.perf_counter()
    r = run(**k)
    return r, time.perf_counter() - t


def test_max_size_deeply_nested_html_is_fast():
    html = ("<div>" * 20000 + "x" + "</div>" * 20000)[:200_000]
    r, dt = timed(html=html)
    assert dt < 2 and r.verdict in {"LOW", "SUSPICIOUS", "HIGH", "INCONCLUSIVE"}


def test_many_links_bounded():
    html = '<a href="https://evil.example/x">bank.example</a>' * 4000
    r, dt = timed(html=html[:200_000])
    assert dt < 2 and len(r.findings) <= 5


def test_malformed_html_and_bidi_unicode_do_not_crash():
    html = "<a href='https://‮example.com'>‮bank.example</a><div style='display:none'><p>" + "\x00" * 100
    r, _ = timed(html=html)
    assert r.verdict


def test_excerpts_are_capped_and_links_defanged():
    r, _ = timed(html='<a href="https://evil.example/' + "a" * 5000 + '">bank.example</a>')
    f = next(f for f in r.findings if f.signal == "S9")
    assert len(f.excerpt) <= 160 and "hxxps://" in f.excerpt and "https://" not in f.excerpt


def test_forged_lower_auth_header_cannot_override_google():
    google_fail = ("mx.google.com; spf=fail smtp.mailfrom=bank.example; "
                   "dmarc=fail (p=REJECT sp=REJECT dis=NONE) header.from=bank.example")
    r, _ = timed(auth=None, auth_results=[google_fail, "mx.google.com; dmarc=pass header.from=bank.example"],
                 **{"from_header": "Bank <x@bank.example>"})
    assert any(f.signal == "S1" and f.level == 2 for f in r.findings)
