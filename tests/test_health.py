from fastapi.testclient import TestClient
from app.core.config import settings


def test_health_check_success(client: TestClient):
    """Test that health check endpoint returns 200 and indicates database connected."""
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
