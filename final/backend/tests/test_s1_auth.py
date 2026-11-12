from app.signals.auth import parse_topmost

PASS = ("mx.google.com; dkim=pass header.i=@acme.example header.s=s1 header.b=abc; "
        "spf=pass (google.com: domain of x@acme.example designates 1.2.3.4) smtp.mailfrom=x@acme.example; "
        "dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=acme.example")


def test_parses_google_header():
    r = parse_topmost([PASS])
    assert r.trusted and (r.spf, r.dkim, r.dmarc, r.dmarc_policy) == ("pass", "pass", "pass", "reject")
    assert r.dkim_domains == ("acme.example",)


def test_forged_non_google_header_ignored():
    forged = "evil.example; dmarc=pass (p=REJECT) header.from=bank.example"
    assert not parse_topmost([forged, PASS]).trusted


def test_missing_header_is_unavailable_not_fail():
    r = parse_topmost([])
    assert not r.trusted and r.dmarc is None


def test_dmarc_fail_policy_none():
    h = "mx.google.com; spf=softfail smtp.mailfrom=x.example; dmarc=fail (p=NONE sp=NONE dis=NONE) header.from=x.example"
    r = parse_topmost([h])
    assert (r.dmarc, r.dmarc_policy) == ("fail", "none")
