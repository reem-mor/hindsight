def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["catalog_services"] > 0
    assert "version" in body


def test_metrics_exposition(client):
    # generate one enrich so counters are non-trivial
    client.post("/enrich", json={"incident_title": "x", "summary": "minor blip"})
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "hindsight_uptime_seconds" in r.text
    assert "hindsight_documents_enriched_total" in r.text


def test_categories(client):
    r = client.get("/categories")
    assert r.status_code == 200
    body = r.json()
    assert "SEV1" in body["severities"]
    assert "security" in body["incident_types"]
    assert "confidential" in body["sensitivities"]
    assert len(body["teams"]) > 3


def test_service_catalog(client):
    r = client.get("/service-catalog")
    assert r.status_code == 200
    assert r.json()["service_count"] > 5


def test_correlation_id_roundtrip(client):
    r = client.post(
        "/enrich",
        json={"incident_title": "x", "summary": "y"},
        headers={"x-correlation-id": "test-cid-123"},
    )
    assert r.headers.get("x-correlation-id") == "test-cid-123"
