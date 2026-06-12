import pytest
from fastapi.testclient import TestClient
from tryops.api import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_api_history_requires_auth(client):
    response = client.get("/api/history")
    assert response.status_code == 200 # Returns 200 structured error actually
    data = response.json()
    assert data.get("error", {}).get("code") == "unauthorized_admin_action"

def test_api_dashboard_requires_auth(client):
    response = client.get("/api/dashboard")
    data = response.json()
    assert data.get("error", {}).get("code") == "unauthorized_admin_action"

def test_payload_too_large(client):
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/llm/generate", headers={"content-length": "20000000"}, json={"prompt": "test"})
    assert response.status_code == 413
    assert response.json().get("error", {}).get("code") == "payload_too_large"

