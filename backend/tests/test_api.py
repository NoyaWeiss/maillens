GOOGLE_PASS = ("mx.google.com; dkim=pass header.i=@acme.example header.s=s1; "
               "spf=pass smtp.mailfrom=acme.example; dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=acme.example")


def payload(**msg):
    base = {"from_header": "Acme <billing@acme.example>", "subject": "Invoice"}
    base.update(msg)
    return {"schema_version": 1, "message": base}


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_rejects_missing_and_wrong_key(client):
    assert client.post("/v1/analyze", json=payload()).status_code == 401
    assert client.post("/v1/analyze", json=payload(), headers={"X-API-Key": "nope"}).status_code == 401


def test_analyze_happy_path(client, headers):
    r = client.post("/v1/analyze", json=payload(auth_results=[GOOGLE_PASS]), headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "LOW"
    assert {c["id"]: c["state"] for c in body["checks"]}["S1"] == "ran"


def test_unknown_fields_rejected_without_echoing_values(client, headers):
    p = payload()
    p["message"]["evil"] = "<script>alert(1)</script>"
    r = client.post("/v1/analyze", json=p, headers=headers)
    assert r.status_code == 422
    assert "<script>" not in r.text


def test_oversized_body_rejected(client, headers):
    r = client.post("/v1/analyze", content=b"x" * (1100 * 1024),
                    headers={**headers, "content-type": "application/json"})
    assert r.status_code == 413


def test_oversized_field_rejected(client, headers):
    r = client.post("/v1/analyze", json=payload(subject="a" * 5000), headers=headers)
    assert r.status_code == 422


def test_dev_probe_endpoint_disabled_by_default(client, headers):
    assert client.post("/v1/dev/probe-report", json=[], headers=headers).status_code == 404
