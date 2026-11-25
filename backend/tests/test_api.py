from fastapi.testclient import TestClient
from app.main import app, rate


def test_external_site_cannot_trigger_ingestion():
    rate.clear()
    response = TestClient(app).post('/api/ingest', headers={'origin': 'https://untrusted.example'}, json={'source': 'gbif'})
    assert response.status_code == 403


def test_invalid_inputs_are_rejected_before_database():
    rate.clear()
    client = TestClient(app)
    assert client.post('/api/ask', json={'question': 'a'}).status_code == 422
    assert client.post('/api/ingest', json={'source': 'shell', 'limit': 100}).status_code == 422
    assert client.post('/api/ingest', json={'source': 'gbif', 'limit': 999999}).status_code == 422


def test_dns_rebinding_host_is_rejected():
    response = TestClient(app).get('/api/health', headers={'host': 'attacker.example'})
    assert response.status_code == 400
